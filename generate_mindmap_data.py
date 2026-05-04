import csv
import datetime
import json
import re
from collections import Counter
from pathlib import Path


SOURCE_CSV = Path("HubSpot_Total_Mastery_Library.csv")
OUTPUT_JS = Path("data.js")
DICTIONARY_JSON = Path("dictionary.json")

FIELDS = ["ID", "Name", "Hub", "Parent", "URL", "Summary", "Functions"]

HUB_RULES = [
    (
        "Marketing Hub",
        {
            "ads",
            "blog",
            "calls-to-action",
            "campaigns",
            "ctas",
            "email",
            "forms",
            "lead capture",
            "marketing",
            "marketing email",
            "social",
            "sms",
            "tracking",
        },
    ),
    (
        "Sales Hub",
        {
            "calling",
            "commerce",
            "deal",
            "forecast",
            "meetings",
            "playbooks",
            "prospecting",
            "quotes",
            "sales",
            "sequences",
            "snippets",
            "tasks",
            "templates",
        },
    ),
    (
        "Service Hub",
        {
            "calling",
            "customer agent",
            "customer portal",
            "feedback",
            "help desk",
            "inbox",
            "knowledge base",
            "service",
            "sla",
            "surveys",
            "tickets",
        },
    ),
    (
        "Content Hub",
        {
            "blog",
            "brand",
            "cms",
            "content",
            "design",
            "domains",
            "files",
            "hubdb",
            "landing pages",
            "seo",
            "website",
            "website pages",
        },
    ),
    (
        "Operations Hub",
        {
            "data",
            "data management",
            "data quality",
            "data sync",
            "datasets",
            "imports",
            "integrations",
            "properties",
            "workflows",
        },
    ),
    (
        "Commerce Hub",
        {
            "billing",
            "commerce",
            "credit memos",
            "invoices",
            "line items",
            "payments",
            "products",
            "subscriptions",
            "tax",
        },
    ),
    (
        "Core CRM",
        {
            "associations",
            "companies",
            "contacts",
            "crm",
            "deals",
            "leads",
            "lists",
            "objects",
            "pipelines",
            "records",
            "segments",
        },
    ),
    (
        "Reporting",
        {
            "analytics",
            "attribution",
            "dashboards",
            "forecasting",
            "goals",
            "reports",
            "reporting",
        },
    ),
    (
        "Account & Governance",
        {
            "account",
            "account management",
            "account security",
            "approvals",
            "billing",
            "permissions",
            "privacy",
            "security",
            "settings",
            "users",
        },
    ),
    (
        "AI & Breeze",
        {
            "agents",
            "ai",
            "breeze",
            "copilot",
        },
    ),
]

PATH_OVERRIDES = {
    "account-management": "Account & Governance",
    "account-security": "Account & Governance",
    "ads": "Marketing Hub",
    "ai": "AI & Breeze",
    "blog": "Content Hub",
    "calling": "Sales Hub",
    "campaigns": "Marketing Hub",
    "commerce": "Commerce Hub",
    "content": "Content Hub",
    "customer-agent": "Service Hub",
    "customer-agent-and-copilot": "AI & Breeze",
    "data-management": "Operations Hub",
    "email": "Marketing Hub",
    "forms": "Marketing Hub",
    "help-desk": "Service Hub",
    "invoices": "Commerce Hub",
    "knowledge-base": "Service Hub",
    "payments": "Commerce Hub",
    "products": "Commerce Hub",
    "quotes": "Commerce Hub",
    "records": "Core CRM",
    "reports": "Reporting",
    "sequences": "Sales Hub",
    "social": "Marketing Hub",
    "subscriptions": "Commerce Hub",
    "tickets": "Service Hub",
    "website-and-landing-pages": "Content Hub",
    "workflows": "Operations Hub",
}

HUB_ORDER = [
    "Core CRM",
    "Marketing Hub",
    "Sales Hub",
    "Service Hub",
    "Content Hub",
    "Operations Hub",
    "Commerce Hub",
    "Reporting",
    "Account & Governance",
    "AI & Breeze",
]


def normalize_space(value):
    return re.sub(r"\s+", " ", (value or "").strip())


def get_path_area(url):
    match = re.search(r"knowledge\.hubspot\.com/([^/?#]+)", url or "")
    return match.group(1).lower() if match else ""


def infer_hub(row):
    path_area = get_path_area(row.get("Live Link", ""))
    if path_area in PATH_OVERRIDES:
        return PATH_OVERRIDES[path_area]

    haystack = " ".join(
        [
            row.get("Topic", ""),
            row.get("Article Name", ""),
            row.get("Functions Spanned", ""),
            path_area.replace("-", " "),
        ]
    ).lower()
    scores = Counter()
    for hub, keywords in HUB_RULES:
        for keyword in keywords:
            if keyword in haystack:
                scores[hub] += len(keyword)
    if scores:
        return scores.most_common(1)[0][0]
    return "Account & Governance"


def make_id(hub, topic, index):
    hub_part = re.sub(r"[^A-Z0-9]+", "", hub.upper())[:4] or "HUB"
    topic_part = re.sub(r"[^A-Z0-9]+", "", topic.upper())[:4] or "TOP"
    return f"{hub_part}-{topic_part}-{index:04d}"


def build_rows():
    with SOURCE_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        source_rows = list(csv.DictReader(f))

    output_rows = []
    seen_urls = set()
    for index, row in enumerate(source_rows, start=1):
        title = normalize_space(row.get("Article Name"))
        topic = normalize_space(row.get("Topic")) or "General"
        functions = normalize_space(row.get("Functions Spanned"))
        url = normalize_space(row.get("Live Link"))
        if not title or not url or url in seen_urls:
            continue
        seen_urls.add(url)
        hub = infer_hub(row)
        summary = functions or f"{topic} documentation"
        output_rows.append(
            {
                "ID": make_id(hub, topic, len(output_rows) + 1),
                "Name": title,
                "Hub": hub,
                "Parent": topic,
                "URL": url,
                "Summary": summary,
                "Functions": functions,
            }
        )

    return sorted(
        output_rows,
        key=lambda r: (
            HUB_ORDER.index(r["Hub"]) if r["Hub"] in HUB_ORDER else len(HUB_ORDER),
            r["Parent"].lower(),
            r["Name"].lower(),
        ),
    )


def write_data_js(rows):
    csv_lines = []
    from io import StringIO

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    csv_content = buffer.getvalue().strip()

    if DICTIONARY_JSON.exists():
        semantic_dict = json.loads(DICTIONARY_JSON.read_text(encoding="utf-8"))
    else:
        semantic_dict = {}

    for row in rows:
        topic_key = row["Parent"].lower()
        semantic_dict.setdefault(topic_key, [])
        for value in [row["Hub"], row["Parent"], row["Functions"]]:
            if value and value not in semantic_dict[topic_key]:
                semantic_dict[topic_key].append(value)

    hub_counts = Counter(row["Hub"] for row in rows)
    topic_counts = Counter((row["Hub"], row["Parent"]) for row in rows)
    metadata = {
        "articleCount": len(rows),
        "topicCount": len(topic_counts),
        "hubCount": len(hub_counts),
        "hubs": dict(sorted(hub_counts.items(), key=lambda item: HUB_ORDER.index(item[0]) if item[0] in HUB_ORDER else 999)),
    }

    last_synced = datetime.datetime.now(datetime.timezone.utc).strftime("%B %d, %Y")
    OUTPUT_JS.write_text(
        f"const sheetData = {csv_content!r};\n"
        f"const lastSynced = {last_synced!r};\n"
        f"const libraryMetadata = {json.dumps(metadata, ensure_ascii=False)};\n"
        f"const semanticDictionary = {json.dumps(semantic_dict, ensure_ascii=False)};\n",
        encoding="utf-8",
    )


def main():
    rows = build_rows()
    if not rows:
        raise SystemExit("No rows found. Run build_total_mastery_library.py first.")
    write_data_js(rows)
    print(f"Updated {OUTPUT_JS} with {len(rows)} articles.")


if __name__ == "__main__":
    main()
