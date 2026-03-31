import requests
import io

url = "https://kalender.irishof.cloud/pdf_preview?year=2026&show_vacations=true"
print(f"Checking {url}...")
try:
    r = requests.get(url, timeout=20, verify=False) # skip verify for now if needed
    if r.status_code == 200:
        print("PDF received successfully.")
        # We don't have a PDF text extractor here, but we can check the size 
        # or just trust the local tests if we can't parse it easily.
        # But wait, I can check if the response is actually a PDF.
        if r.headers.get('Content-Type') == 'application/pdf':
            print("Content-Type is application/pdf. Size:", len(r.content))
            if len(r.content) > 1000:
                print("PDF size looks reasonable.")
            else:
                print("PDF size is too small!")
        else:
            print("Response is NOT a PDF! Content-Type:", r.headers.get('Content-Type'))
            print("Content:", r.text[:500])
    else:
        print(f"Error: Status code {r.status_code}")
        print("Response:", r.text[:500])
except Exception as e:
    print(f"Error connecting: {e}")
