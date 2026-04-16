import time
import csv
from ddgs import DDGS

library_structure = {
    "CEO": {
        "Executive Strategy": ["HubSpot reporting dashboards for executives", "calculating ROI", "Business Units overview"]
    },
    "REVOPS": {
        "Data Governance": ["HubSpot properties guide", "Data quality command center", "custom objects", "data sync"],
        "Revenue Insights": ["Custom report builder", "multi-touch revenue attribution", "forecasting tool", "goals tool"],
        "Portal Health & Security": ["HubSpot audit log", "Property health tool", "API limits overview", "SSO setup", "2FA enforcement"]
    },
    "MARKETING": {
        "Marketing Ops": ["Marketing contacts billing", "GDPR compliance", "Preference centers", "Asset partitioning"],
        "Demand Gen": ["Lead scoring", "Ads attribution", "Smart content", "Progressive profiling"],
        "Content Execution": ["Social media tool", "Breeze AI content remix", "HubSpot mobile social app", "Asset manager"]
    },
    "SALES": {
        "Sales Ops": ["Deal pipelines", "Weighted forecast", "Line items and products", "Quotes and CPQ"],
        "Field Sales (Outside)": ["HubSpot mobile app features", "Scan business cards", "Logging mobile calls", "QR code business cards"],
        "Inside Sales (SDR/BDR)": ["Prospecting workspace", "Task queues", "Sequences", "LinkedIn Sales Navigator integration", "HubSpot calling tool"],
        "Enablement": ["Sales playbooks", "Sales templates snippets", "Meeting tool config"]
    },
    "CUSTOMER SUCCESS": {
        "Service Ops": ["Help desk setup", "SLA management", "Ticket pipelines", "Customer portal"],
        "Agent Enablement": ["Omnichannel inbox", "Chat snippets", "Knowledge base article insertion", "Mobile service app"],
        "Retention Strategy": ["Customer health scoring", "Renewal workflows", "NPS CSAT surveys"]
    }
}

print("Initiating ULTIMATE Data Mine (VPs + Directors + Field Reps)...")
csv_path = "GA_Reference_Library_V2.csv"
js_path = "data.js"

with open(csv_path, "w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["ID", "Name", "Parent", "URL"])
    
    with DDGS() as ddgs:
        for vp, directors in library_structure.items():
            for director, topics in directors.items():
                for topic in topics:
                    topic_id = f"{vp[:3]}-{director[:3]}".upper().replace(" ", "")
                    query = f"site:knowledge.hubspot.com {topic}"
                    try:
                        results = list(ddgs.text(query, max_results=6)) # Pulling 6 for even more depth
                        for i, r in enumerate(results):
                            title = r['title'].split('|')[0].strip()
                            url = r['href']
                            blocked_langs = ['/es/', '/fr/', '/de/', '/pt/', '/nl/', '/ja/', '/it/', '/sv/', '/da/', '/fi/', '/pl/', '/zh-cn/', '/zh-tw/', '/ko/']
                            if "knowledge.hubspot.com" in url and not any(x in url for x in blocked_langs):
                                writer.writerow([f"{topic_id}-{i+1}", title, director, url])
                        print(f"Verified cluster for: {topic}")
                    except Exception as e:
                        print(f"Error: {e}")
                    time.sleep(2)


print("\n--- MASTER LIBRARY V2 COMPLETE ---")

print("Generating live Javascript data module for local D3 rendering...")
with open(csv_path, "r", encoding="utf-8") as f:
    csv_content = f.read()

with open(js_path, "w", encoding="utf-8") as f:
    f.write(f"const sheetData = {repr(csv_content.strip())};")

print("D3 Component (data.js) updated successfully!")
