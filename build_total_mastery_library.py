import argparse
import csv
import datetime as dt
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


BASE_URL = "https://knowledge.hubspot.com"
USER_AGENT = "Mozilla/5.0 (compatible; HubSpotTotalMasteryLibrary/1.0)"
CSV_COLUMNS = ["Article Name", "Topic", "Functions Spanned", "Live Link"]
DEFAULT_OUTPUT_CSV = "HubSpot_Total_Mastery_Library.csv"
DEFAULT_OUTPUT_XLSX = "HubSpot_Total_Mastery_Library.xlsx"
STATE_PATH = ".total_mastery_crawl_state.json"

BLOCKED_PATH_PARTS = (
    "/_hcms/",
    "/hs/",
    "/wt-assets/",
    "/academy/",
)

BLOCKED_LANG_PREFIXES = (
    "/da/",
    "/de/",
    "/es/",
    "/fi/",
    "/fr/",
    "/id/",
    "/it/",
    "/ja/",
    "/ko/",
    "/nl/",
    "/no/",
    "/pl/",
    "/pt/",
    "/ru/",
    "/sv/",
    "/th/",
    "/tr/",
    "/vi/",
    "/zh-cn/",
    "/zh-tw/",
)

NON_ARTICLE_PATH_PARTS = (
    "/topic/",
    "/topics",
    "/search",
    "/all-products",
)

TOOL_KEYWORDS = {
    "Account & Setup": [
        "account settings",
        "account",
        "business units",
        "brand domains",
        "billing",
        "domains",
        "login",
        "notifications",
        "permissions",
        "security",
        "subscription",
        "teams",
        "users",
    ],
    "AI": ["breeze", "copilot", "agents", "content remix", "ai assistant", "ai assistants"],
    "Automation": [
        "workflow",
        "workflows",
        "branches",
        "delays",
        "enrollment",
        "re-enrollment",
        "automation",
    ],
    "Commerce": [
        "payments",
        "payment links",
        "invoices",
        "subscriptions",
        "quotes",
        "products",
        "line items",
    ],
    "Content": [
        "blog",
        "cms",
        "content",
        "domains",
        "landing pages",
        "website pages",
        "knowledge base",
        "hubdb",
    ],
    "CRM": [
        "contacts",
        "companies",
        "deals",
        "tickets",
        "records",
        "properties",
        "associations",
        "pipelines",
        "lists",
    ],
    "Data": [
        "data quality",
        "data sync",
        "imports",
        "exports",
        "deduplicate",
        "duplicate",
        "operations",
        "datasets",
    ],
    "Marketing": [
        "ads",
        "campaigns",
        "calls-to-action",
        "ctas",
        "email",
        "forms",
        "leads",
        "marketing email",
        "social",
    ],
    "Reporting": [
        "analytics",
        "attribution",
        "dashboards",
        "forecast",
        "goals",
        "reports",
        "custom report builder",
    ],
    "Sales": [
        "calling",
        "forecast",
        "meetings",
        "playbooks",
        "prospecting",
        "sales workspace",
        "sequences",
        "snippets",
        "tasks",
        "templates",
    ],
    "Service": [
        "chatflows",
        "conversations inbox",
        "customer portal",
        "feedback surveys",
        "help desk",
        "inbox",
        "knowledge base",
        "slas",
        "tickets",
    ],
}


def fetch(url, timeout=30):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace"), response.headers.get_content_type()


def normalize_url(url, base=BASE_URL):
    absolute = urllib.parse.urljoin(base, html.unescape(url))
    parsed = urllib.parse.urlparse(absolute)
    if parsed.netloc.lower() != "knowledge.hubspot.com":
        return ""
    path = re.sub(r"/+", "/", parsed.path).rstrip("/")
    if not path:
        path = "/"
    if any(path.lower().startswith(prefix) for prefix in BLOCKED_LANG_PREFIXES):
        return ""
    if any(part in path.lower() for part in BLOCKED_PATH_PARTS):
        return ""
    return urllib.parse.urlunparse(("https", parsed.netloc.lower(), path, "", "", ""))


def is_probable_article_url(url):
    path = urllib.parse.urlparse(url).path
    if path == "/" or any(part == path or part in path for part in NON_ARTICLE_PATH_PARTS):
        return False
    parts = [part for part in path.split("/") if part]
    return len(parts) >= 2


def strip_tags(value):
    value = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def extract_links(page_html, base_url):
    links = set()
    for match in re.finditer(r"""href=["']([^"']+)["']""", page_html, flags=re.I):
        normalized = normalize_url(match.group(1), base_url)
        if normalized:
            links.add(normalized)
    return links


def extract_title(page_html):
    h1 = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", page_html)
    if h1:
        return strip_tags(h1.group(1))
    og = re.search(r"""(?is)<meta[^>]+property=["']og:title["'][^>]+content=["']([^"']+)["']""", page_html)
    if og:
        return html.unescape(og.group(1)).strip()
    title = re.search(r"(?is)<title[^>]*>(.*?)</title>", page_html)
    if title:
        return strip_tags(title.group(1)).replace(" | Knowledge Base", "").strip()
    return ""


def extract_json_ld_topic(page_html):
    for block in re.findall(r'(?is)<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', page_html):
        try:
            data = json.loads(html.unescape(block).strip())
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("@type") == "BreadcrumbList":
                names = []
                for crumb in item.get("itemListElement", []):
                    name = crumb.get("name") or crumb.get("item", {}).get("name")
                    if name:
                        names.append(str(name))
                useful = [name for name in names if name.lower() not in {"home", "knowledge base"}]
                if useful:
                    return useful[0]
    return ""


def extract_visible_headings(page_html):
    headings = []
    for match in re.finditer(r"(?is)<h[2-3][^>]*>(.*?)</h[2-3]>", page_html):
        heading = strip_tags(match.group(1))
        if heading and len(heading) <= 90:
            headings.append(heading)
    return headings


def title_case_slug(slug):
    return slug.replace("-", " ").replace("_", " ").strip().title()


def normalize_topic(topic):
    replacements = {
        "Acccount Management": "Account Management",
        "Account Management": "Account Management",
        "Website Pages": "CMS & Website Pages",
        "Knowledge Base": "Service Knowledge Base",
    }
    return replacements.get(topic, topic)


def infer_topic(url, page_html, title):
    breadcrumb_topic = extract_json_ld_topic(page_html)
    if breadcrumb_topic:
        return breadcrumb_topic
    path_parts = [part for part in urllib.parse.urlparse(url).path.split("/") if part]
    if path_parts:
        return normalize_topic(title_case_slug(path_parts[0]))
    return infer_topic_from_text(title)


def infer_topic_from_text(text):
    text_l = text.lower()
    scores = {}
    for topic, keywords in TOOL_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in text_l)
        if score:
            scores[topic] = score
    if scores:
        return sorted(scores.items(), key=lambda item: (-item[1], item[0]))[0][0]
    return "General"


def infer_functions(title, headings, url):
    path_text = title_case_slug(urllib.parse.urlparse(url).path)
    haystack = " ".join([title] + headings + [path_text]).lower()
    matches = []
    for keywords in TOOL_KEYWORDS.values():
        for keyword in keywords:
            if keyword in haystack:
                matches.append(title_case_slug(keyword))
    for heading in headings[:8]:
        if re.search(r"\b(create|manage|set up|connect|import|export|use|configure|customize|analyze|automate)\b", heading, re.I):
            matches.append(heading)
    deduped = []
    seen = set()
    for item in matches:
        clean = re.sub(r"\s+", " ", item).strip()
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            deduped.append(clean)
    return "; ".join(deduped[:12]) or "General HubSpot functionality"


def looks_like_article(page_html):
    text = strip_tags(page_html).lower()
    return "last updated" in text and ("was this article helpful" in text or "available with any of the following subscriptions" in text)


def discover_from_sitemaps():
    queue = deque([f"{BASE_URL}/sitemap.xml"])
    seen_sitemaps = set()
    urls = set()
    while queue:
        sitemap = queue.popleft()
        if sitemap in seen_sitemaps:
            continue
        seen_sitemaps.add(sitemap)
        try:
            content, _ = fetch(sitemap)
        except Exception:
            continue
        try:
            root = ET.fromstring(content.encode("utf-8"))
        except ET.ParseError:
            continue
        for loc in root.findall(".//{*}loc"):
            if not loc.text:
                continue
            normalized = normalize_url(loc.text)
            if not normalized:
                continue
            if normalized.endswith(".xml"):
                queue.append(normalized)
            elif is_probable_article_url(normalized):
                urls.add(normalized)
    return urls


def map_article(url, delay=0.0):
    try:
        page_html, content_type = fetch(url)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, f"Fetch skipped: {url} ({exc})"
    finally:
        if delay:
            time.sleep(delay)
    if "html" not in content_type:
        return None, None
    if not looks_like_article(page_html):
        return None, None
    title = extract_title(page_html)
    if not title:
        return None, None
    headings = extract_visible_headings(page_html)
    return {
        "Article Name": title,
        "Topic": infer_topic(url, page_html, title),
        "Functions Spanned": infer_functions(title, headings, url),
        "Live Link": url,
    }, None


def crawl_sitemap_articles(max_pages=None, delay=0.0, workers=8):
    urls = sorted(discover_from_sitemaps())
    if max_pages:
        urls = urls[:max_pages]
    rows_by_url = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        future_to_url = {executor.submit(map_article, url, delay): url for url in urls}
        for index, future in enumerate(as_completed(future_to_url), start=1):
            url = future_to_url[future]
            row, error = future.result()
            if error:
                print(error, flush=True)
            if row:
                rows_by_url[url] = row
                print(f"[{index}/{len(urls)}] Article mapped: {row['Article Name']}", flush=True)
            elif not error:
                print(f"[{index}/{len(urls)}] Non-article skipped: {url}", flush=True)
    return [rows_by_url[url] for url in sorted(rows_by_url)]


def crawl_site(max_pages=None, delay=0.25, follow_links=False):
    discovered = discover_from_sitemaps()
    queue = deque(sorted(discovered) or [BASE_URL])
    seen = set()
    rows_by_url = {}

    while queue:
        url = queue.popleft()
        if url in seen:
            continue
        if max_pages and len(seen) >= max_pages:
            break
        seen.add(url)
        try:
            page_html, content_type = fetch(url)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"Fetch skipped: {url} ({exc})")
            continue
        if "html" not in content_type:
            continue
        if follow_links:
            for link in extract_links(page_html, url):
                if link not in seen and (is_probable_article_url(link) or "/topics" in link or "/topic/" in link):
                    queue.append(link)
        if is_probable_article_url(url) and looks_like_article(page_html):
            title = extract_title(page_html)
            if not title:
                continue
            headings = extract_visible_headings(page_html)
            rows_by_url[url] = {
                            "Article Name": title,
                            "Topic": infer_topic(url, page_html, title),
                            "Functions Spanned": infer_functions(title, headings, url),
                            "Live Link": url,
            }
            print(f"Article mapped: {title}", flush=True)
        time.sleep(delay)

    return [rows_by_url[url] for url in sorted(rows_by_url)]


def write_csv(rows, path):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def xml_escape(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def col_name(index):
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def write_xlsx(rows, path):
    all_rows = [CSV_COLUMNS] + [[row[column] for column in CSV_COLUMNS] for row in rows]
    sheet_rows = []
    for row_index, row in enumerate(all_rows, start=1):
        cells = []
        for col_index, value in enumerate(row, start=1):
            ref = f"{col_name(col_index)}{row_index}"
            cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{xml_escape(value)}</t></is></c>')
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<cols><col min="1" max="1" width="55"/><col min="2" max="2" width="24"/>'
        '<col min="3" max="3" width="75"/><col min="4" max="4" width="80"/></cols>'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="HubSpot Total Mastery" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    app_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Codex</Application></Properties>'
    )
    core_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<dc:title>HubSpot Total Mastery Library</dc:title>'
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{dt.datetime.now(dt.timezone.utc).isoformat()}</dcterms:created>'
        "</cp:coreProperties>"
    )

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml)
        archive.writestr("_rels/.rels", rels_xml)
        archive.writestr("docProps/app.xml", app_xml)
        archive.writestr("docProps/core.xml", core_xml)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def main():
    parser = argparse.ArgumentParser(description="Build a line-by-line HubSpot Knowledge Base curriculum spreadsheet.")
    parser.add_argument("--output-csv", default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--output-xlsx", default=DEFAULT_OUTPUT_XLSX)
    parser.add_argument("--max-pages", type=int, default=None, help="Optional cap for smoke tests. Omit for full crawl.")
    parser.add_argument("--delay", type=float, default=0.25, help="Delay between page requests.")
    parser.add_argument("--follow-links", action="store_true", help="Follow Knowledge Base page links in addition to sitemap URLs.")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent article fetches for sitemap mode.")
    args = parser.parse_args()

    if args.follow_links:
        rows = crawl_site(max_pages=args.max_pages, delay=args.delay, follow_links=True)
    else:
        rows = crawl_sitemap_articles(max_pages=args.max_pages, delay=args.delay, workers=args.workers)
    if not rows:
        raise SystemExit("No HubSpot Knowledge Base articles were mapped.")

    write_csv(rows, args.output_csv)
    write_xlsx(rows, args.output_xlsx)
    Path(STATE_PATH).write_text(
        json.dumps(
            {
                "last_run_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "article_count": len(rows),
                "csv": args.output_csv,
                "xlsx": args.output_xlsx,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Complete: {len(rows)} articles written to {args.output_csv} and {args.output_xlsx}.")


if __name__ == "__main__":
    main()
