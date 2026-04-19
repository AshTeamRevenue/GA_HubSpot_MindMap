import time
import csv
import json
import datetime
import urllib.request
import urllib.parse
import sys

print("Loading external JSON taxonomy...")
try:
    with open("taxonomy.json", "r", encoding="utf-8") as f:
        library_structure = json.load(f)
except FileNotFoundError:
    print("CRITICAL: taxonomy.json not found! Exiting.")
    exit(1)

print("Loading semantic dictionary...")
try:
    with open("dictionary.json", "r", encoding="utf-8") as f:
        semantic_dict = json.load(f)
except FileNotFoundError:
    print("Warning: dictionary.json not found. Using empty dictionary.")
    semantic_dict = {}

print("Initiating ULTIMATE Data Mine (VPs + Directors + Field Reps)...")
csv_path = "GA_Reference_Library_V2.csv"
js_path = "data.js"

with open(csv_path, "w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["ID", "Name", "Parent", "URL", "Summary"])
    
    total_mapped = 0
    for vp, directors in library_structure.items():
        for director, topics in directors.items():
            for topic in topics:
                topic_id = f"{vp[:3]}-{director[:3]}".upper().replace(" ", "")
                encoded_query = urllib.parse.quote(topic)
                req_url = f"https://knowledge.hubspot.com/_hcms/search?term={encoded_query}"
                
                try:
                    req = urllib.request.Request(req_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
                    response = urllib.request.urlopen(req)
                    data = json.loads(response.read().decode('utf-8'))
                    
                    results = data.get('results', [])[:6]
                    for i, r in enumerate(results):
                        title = r.get('title', '').strip()
                        url = r.get('url', '')
                        summary = r.get('description', '').replace('"', "'").replace("\n", " ").strip()
                        
                        blocked_langs = ['/es/', '/fr/', '/de/', '/pt/', '/nl/', '/ja/', '/it/', '/sv/', '/da/', '/fi/', '/pl/', '/zh-cn/', '/zh-tw/', '/ko/']
                        if "knowledge.hubspot.com" in url and not any(x in url for x in blocked_langs):
                            writer.writerow([f"{topic_id}-{i+1}", title, director, url, summary])
                            total_mapped += 1
                    print(f"Verified cluster for: {topic}")
                except Exception as e:
                    print(f"Error: {e}")
                time.sleep(0.5)

if total_mapped == 0:
    print("\n[CRITICAL ERROR] Only mapped 0 articles.")
    print("DuckDuckGo has temporarily shadowbanned the GitHub server for speed limits.")
    print("ABORTING sync to protect the existing database from being erased!")
    sys.exit(1)

print("\n--- MASTER LIBRARY V4 COMPLETE ---")

print("Generating live Javascript data module with semantic payload...")
last_synced = datetime.datetime.now(datetime.timezone.utc).strftime("%B %d, %Y")

with open(csv_path, "r", encoding="utf-8") as f:
    csv_content = f.read()

with open(js_path, "w", encoding="utf-8") as f:
    f.write(f"const sheetData = {repr(csv_content.strip())};\n")
    f.write(f"const lastSynced = '{last_synced}';\n")
    f.write(f"const semanticDictionary = {json.dumps(semantic_dict)};\n")

print("D3 Component (data.js) updated successfully!")
