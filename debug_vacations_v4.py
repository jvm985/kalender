import requests
import re

headers = {'User-Agent': 'Mozilla/5.0'}
url = "https://onderwijs.vlaanderen.be/nl/onderwijs-en-vorming/wat-mag-en-moet-op-school/schoolvakanties-vrije-dagen-en-afwezigheden/schoolvakanties"

print(f"Fetching {url}...")
r = requests.get(url, headers=headers, timeout=10)
if r.status_code == 200:
    content = r.text
    print(f"Content length: {len(content)}")
    
    # Search for "Herfstvakantie" and context
    pos = content.find("Herfstvakantie")
    if pos != -1:
        print(f"\nFound 'Herfstvakantie' at {pos}")
        print("Context (1000 chars):")
        print(content[max(0, pos-100):pos+900])
    else:
        print("\n'Herfstvakantie' NOT found in content.")
        
    # Search for tables
    if "<table" in content:
        print("\nFound tables in content.")
        table_pos = content.find("<table")
        print("Table snippet:")
        print(content[table_pos:table_pos+1500])
else:
    print(f"Failed to fetch: {r.status_code}")
