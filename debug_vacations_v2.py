import requests
import re

headers = {'User-Agent': 'Mozilla/5.0'}
url = "https://onderwijs.vlaanderen.be/nl/schoolvakanties"

r = requests.get(url, headers=headers, timeout=10)
if r.status_code == 200:
    content = r.text
    print("Content head (1000 chars):")
    print(content[:1000])
    
    # Let's search for "Herfstvakantie" and some context
    pos = content.find("Herfstvakantie")
    if pos != -1:
        print(f"\nFound 'Herfstvakantie' at {pos}")
        print("Context (500 chars around):")
        print(content[max(0, pos-100):pos+400])
    else:
        print("\n'Herfstvakantie' NOT found in content.")
        
    # Search for any table tags as data often lives there
    if "<table" in content:
        print("\nFound tables in content.")
        # Print a snippet of a table
        table_pos = content.find("<table")
        print(content[table_pos:table_pos+1000])
else:
    print(f"Failed to fetch: {r.status_code}")
