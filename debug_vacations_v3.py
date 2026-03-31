import requests

headers = {'User-Agent': 'Mozilla/5.0'}
url = "https://onderwijs.vlaanderen.be/nl/schoolvakanties"

r = requests.get(url, headers=headers, timeout=10)
if r.status_code == 200:
    content = r.text
    print(f"Searching for 'vakantie' in content...")
    import re
    matches = list(re.finditer(r'vakantie', content, re.IGNORECASE))
    print(f"Found {len(matches)} matches for 'vakantie'.")
    for m in matches[:5]:
        start = max(0, m.start() - 50)
        end = min(len(content), m.end() + 200)
        print(f"Context: {content[start:end]}\n")
