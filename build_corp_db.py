import zipfile
import xml.etree.ElementTree as ET
import requests
import pandas as pd

from config import DART_API_KEY

url = "https://opendart.fss.or.kr/api/corpCode.xml"

params = {
    "crtfc_key": DART_API_KEY
}

print("Downloading DART corp code...")

res = requests.get(url, params=params, timeout=60)

with open("corp.zip", "wb") as f:
    f.write(res.content)

with zipfile.ZipFile("corp.zip") as z:
    xml_name = z.namelist()[0]
    z.extract(xml_name)

tree = ET.parse(xml_name)
root = tree.getroot()

rows = []

for item in root.findall("list"):

    stock = item.findtext("stock_code")

    if stock is None:
        continue

    stock = stock.strip()

    if stock == "":
        continue

    rows.append({
        "stock_code": stock,
        "corp_code": item.findtext("corp_code"),
        "corp_name": item.findtext("corp_name")
    })

df = pd.DataFrame(rows)

df.to_csv("corp_code.csv", index=False, encoding="utf-8-sig")

print(df.head())
print("Saved:", len(df))
