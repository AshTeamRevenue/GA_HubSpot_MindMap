import time
import csv
import json
import datetime
import os
from duckduckgo_search import DDGS

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

# Write to a TEMPORARY file first so we don't destroy the DB if banned!
temp_csv = "TEMP_GA_Reference_Library_V2.csv"
csv_path = "GA_Reference_Library_V2.csv"
js_path = "data.js"
article_count = 0

with open(temp_csv, "w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["ID", "Name", "Parent", "URL", "Summary"])
    
    with DDGS() as ddgs:
        for vp, directors in library_structure.items():
            for director, topics in directors.items():
                for topic in topics:
                    topic_id = f"{vp[:3]}-{director[:3]}".upper().replace(" ", "")
                    query = f"site:knowledge.hubspot.com {topic}"
                    try:
                        # Use html backend to bypass heavy API robot-blocks
                        results = list(ddgs.text(query, max_results=5, backend="html")) 
                        for i, r in enumerate(results):
                            title = r.get('title', '').split('|')[0].strip()
                            url = r.get('href', '')
                            summary = r.get('body', '').replace('"', "'").replace("\n", " ").strip()
                            
                            blocked_langs = ['/es/', '/fr/', '/de/', '/pt/', '/nl/', '/ja/', '/it/', '/sv/', '/da/', '/fi/', '/pl/', '/zh-cn/', '/zh-tw/', '/ko/']
                            if "knowledge.hubspot.com" in url and not any(x in url for x in blocked_langs):
                                writer.writerow([f"{topic_id}-{i+1}", title, director, url, summary])
                                article_count += 1
                        print(f"Verified cluster for: {topic}")
                    except Exception as e:
                        print(f"Error scraping {topic}: {e}")
                        
                    # Throttle heavily to mimic human speed and avoid locks
                    time.sleep(4)

# ==========================================
# DATABASE PROTECTION FAILSAFE
# ==========================================
if article_count < 20:
    print(f"\n[CRITICAL ERROR] Only mapped {article_count} articles.")
    print("DuckDuckGo has temporarily shadowbanned the GitHub server for speed limits.")
    print("ABORTING sync to protect the existing database from being erased!")
    os.remove(temp_csv)
    exit(1)

# If it passed protection, overwrite the real CSV database securely
import shutil
shutil.move(temp_csv, csv_path)

print("\n--- MASTER LIBRARY V4 COMPLETE ---")

print("Generating live Javascript data module with semantic payload...")
last_synced = datetime.datetime.now(datetime.timezone.utc).strftime("%B %d, %Y")

with open(csv_path, "r", encoding="utf-8") as f:
    csv_content = f.read()

with open(js_path, "w", encoding="utf-8") as f:
    f.write(f"const sheetData = {repr(csv_content.strip())};\n")
    f.write(f"const lastSynced = '{last_synced}';\n")
    f.write(f"const semanticDictionary = {json.dumps(semantic_dict)};\n")

print("D3 Component (data.js) successfully armed and updated!")
