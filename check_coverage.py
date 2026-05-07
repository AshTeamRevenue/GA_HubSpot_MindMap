import csv
import json
import sys


CSV_PATH = "GA_Reference_Library_V2.csv"
REQUIRED_PATH = "required_articles.json"


def normalize_url(url):
    return url.split("#")[0].split("?")[0].rstrip("/")


with open(REQUIRED_PATH, "r", encoding="utf-8") as f:
    required_articles = json.load(f)

with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

by_url = {normalize_url(row["URL"]): row for row in rows}
missing = []
misplaced = []

for article in required_articles:
    required_url = normalize_url(article["url"])
    row = by_url.get(required_url)
    if not row:
        missing.append(article)
        continue

    expected_parent = article["parent"]
    if row["Parent"] != expected_parent:
        misplaced.append((article, row["Parent"]))

if missing or misplaced:
    for article in missing:
        print(f"MISSING: {article['name']} <{article['url']}>")
    for article, actual_parent in misplaced:
        print(
            f"MISPLACED: {article['name']} expected "
            f"{article['parent']}, found {actual_parent}"
        )
    sys.exit(1)

print(f"Coverage OK: {len(required_articles)} required articles present.")
