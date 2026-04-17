import time
import csv
import json
import datetime
from duckduckgo_search import DDGS

print("Loading external JSON taxonomy...")
try:
    with open("taxonomy.json", "r", encoding="utf-8") as f:
        library_structure = json.load(f)
except FileNotFoundError:
    print("CRITICAL: taxonomy.json not found! Exiting.")
    exit(1)

print("Initiating ULTIMATE Data Mine (VPs + Directors + Field Reps)...")
csv_path = "GA_Reference_Library_V2.csv"
js_path = "data.js"

with open(csv_path, "w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["ID", "Name", "Parent", "URL", "Summary"])
    
    with DDGS() as ddgs:
        for vp, directors in library_structure.items():
            for director, topics in directors.items():
                for topic in topics:
                    topic_id = f"{vp[:3]}-{director[:3]}".upper().replace(" ", "")
                    query = f"site:knowledge.hubspot.com {topic}"
                    try:
                        results = list(ddgs.text(query, max_results=6)) 
                        for i, r in enumerate(results):
                            title = r.get('title', '').split('|')[0].strip()
                            url = r.get('href', '')
                            summary = r.get('body', '').replace('"', "'").replace("\n", " ").strip()
                            
                            blocked_langs = ['/es/', '/fr/', '/de/', '/pt/', '/nl/', '/ja/', '/it/', '/sv/', '/da/', '/fi/', '/pl/', '/zh-cn/', '/zh-tw/', '/ko/']
                            if "knowledge.hubspot.com" in url and not any(x in url for x in blocked_langs):
                                writer.writerow([f"{topic_id}-{i+1}", title, director, url, summary])
                        print(f"Verified cluster for: {topic}")
                    except Exception as e:
                        print(f"Error: {e}")
                    time.sleep(2)

print("\n--- MASTER LIBRARY V3 COMPLETE ---")

print("Generating live Javascript data module with freshness stamp...")
last_synced = datetime.datetime.now(datetime.UTC).strftime("%B %d, %Y")

with open(csv_path, "r", encoding="utf-8") as f:
    csv_content = f.read()

with open(js_path, "w", encoding="utf-8") as f:
    f.write(f"const sheetData = {repr(csv_content.strip())};\n")
    f.write(f"const lastSynced = '{last_synced}';\n")

print("D3 Component (data.js) updated successfully!")
