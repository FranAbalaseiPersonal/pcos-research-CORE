import os
import json
import requests
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import httplib2
from googleapiclient.discovery import build

# === CONFIGURATION ===
CORE_API_KEY = os.environ["CORE_API_KEY"]
QUERY = '("polycystic ovary syndrome" OR PCOS) AND (' \
        'metabol OR ferti OR infertil OR ovulat OR lifestyle OR diet OR nutrition OR exercise OR intervention OR treatment OR therapy OR medication OR drug OR supplement OR ' \
        'hormone OR hormonal OR androgen OR testosterone OR LH OR FSH OR estradiol OR estrogen OR progesterone OR AMH OR SHBG OR cortisol OR DHEA OR insulin OR glucose OR thyroid OR TSH OR prolactin OR ' \
        'genetic OR gene OR genes OR DNA OR genomics OR SNP OR SNPs OR "single nucleotide polymorphism" OR ' \
        'physiology OR psychology OR mental OR stress OR mood OR population OR cohort OR prevalence OR epidemiology' \
        ')'
DAYS_BACK = 180
MAX_RESULTS = 25
GOOGLE_FOLDER_ID = "1FONoocyFTphDdX1C5ccC0_ZvcvzyTphb"  # <-- Replace with your actual folder ID

# === DATE SETUP ===
end_date = datetime.now().date()
start_date = end_date - timedelta(days=DAYS_BACK)

# === CORE API CALL ===
core_url = "https://api.core.ac.uk/v3/search/works"
headers = {
    "Authorization": f"Bearer {CORE_API_KEY}",
    "Content-Type": "application/json"
}
params = {
    "q": QUERY,
    "limit": MAX_RESULTS,
    "offset": 0,
    "sort": "publishedDate:desc",
    "filter": {
        "publishedDate": {
            "from": start_date.isoformat(),
            "to": end_date.isoformat()
        }
    }
}

response = requests.post(core_url, headers=headers, json=params)
data = response.json()
articles = []

for result in data.get("results", []):
    title = result.get("title", "No title")
    authors_list = result.get("authors", [])
    authors = ", ".join(
        [a.get("name", "") if isinstance(a, dict) else str(a) for a in authors_list]
    ) if authors_list else "Unknown"
    doi = result.get("doi")
    url = f"https://doi.org/{doi}" if doi else result.get("url", "No link available")
    abstract = result.get("abstract", "No abstract available")
    articles.append({
        "Title": title,
        "Authors": authors,
        "Link": url,
        "Abstract": abstract
    })

# === GOOGLE SHEETS AUTH + WRITE ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
json_creds = json.loads(os.environ["GOOGLE_SERVICE_JSON"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(json_creds, scope)
client = gspread.authorize(creds)

# Create spreadsheet
sheet_name = f"PCOS Research – {end_date}"
spreadsheet = client.create(sheet_name)
sheet = spreadsheet.sheet1
sheet.clear()

if not articles:
    print("⚠️ No PCOS-related articles found. Skipping sheet update.")
else:
    sheet.update([list(articles[0].keys())] + [list(a.values()) for a in articles])
    print(f"✅ Sheet updated with {len(articles)} articles.")

# Move to specified Drive folder
spreadsheet_id = spreadsheet.id
drive_service = creds.authorize(httplib2.Http())
drive = build('drive', 'v3', http=drive_service)
file = drive.files().get(fileId=spreadsheet_id, fields='parents').execute()
previous_parents = ",".join(file.get('parents'))
drive.files().update(
    fileId=spreadsheet_id,
    addParents=GOOGLE_FOLDER_ID,
    removeParents=previous_parents,
    fields='id, parents'
).execute()

print(f"✅ Uploaded {len(articles)} articles to Google Sheets: {sheet_name}")

