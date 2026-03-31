import requests
import re

headers = {'User-Agent': 'Mozilla/5.0'}
url = "https://www.vlaanderen.be/onderwijs-en-vorming/wat-mag-en-moet-op-school/schoolvakanties-vrije-dagen-en-afwezigheden/schoolvakanties"
r = requests.get(url, headers=headers, timeout=10)
if r.status_code == 200:
    # Zoek naar koppen die schooljaren aanduiden, bijv. 2025-2026
    headers = re.findall(r'<h[23][^>]*>(.*?)(\d{4}-\d{4}).*?</h[23]>', r.text)
    print("Gevonden schooljaar headers:")
    for h in headers:
        print(f"Header: {h[0]}{h[1]}")
    
    # Toon een stukje van de lijst onder zo'n header
    pos = r.text.find("2025-2026")
    if pos != -1:
        print("\nSnippet rond 2025-2026:")
        print(r.text[pos:pos+2000])
