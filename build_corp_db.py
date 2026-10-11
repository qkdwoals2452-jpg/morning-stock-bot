import zipfile
import xml.etree.ElementTree as ET
import requests
import pandas as pd

from config import DART_API_KEY

url = "https://opendart.fss.or.kr/api/corpCode.xml"

params = {
    "crtfc_key": DART_API_KEY
}


def build_corp_db():
    print("Downloading DART corp code...")

    try:
        res = requests.get(url, params=params, timeout=60)
        res.raise_for_status()
    except requests.RequestException as exc:
        # requests 예외에는 API 키가 포함된 요청 URL이 들어갈 수 있다.
        raise RuntimeError(f"DART 기업코드 연결 실패 ({type(exc).__name__})") from None

    # OpenDART 오류 응답은 ZIP 대신 XML로 올 수 있다.
    # API 키나 요청 URL을 로그에 출력하지 않는다.
    import io

    if not zipfile.is_zipfile(io.BytesIO(res.content)):
        try:
            error_root = ET.fromstring(res.content)
            fields = {node.tag.rsplit("}", 1)[-1].lower(): node.text
                      for node in error_root.iter()}
            status = fields.get("status") or "unknown"
            message = fields.get("message")
            if not message:
                # 오류 XML이 아닌 차단/점검 페이지도 원인을 남긴다.
                summary = " ".join(error_root.itertext()).strip()
                message = f"root={error_root.tag}, response={summary[:200]}"
            message = message.replace(DART_API_KEY, "[REDACTED]") if DART_API_KEY else message
            raise RuntimeError(
                f"DART 기업코드 다운로드 실패 (status={status}, message={message})"
            )
        except ET.ParseError:
            raise RuntimeError(
                f"DART 기업코드 응답이 ZIP이 아닙니다 (HTTP {res.status_code}, "
                f"Content-Type: {res.headers.get('Content-Type', 'unknown')})."
            )

    with zipfile.ZipFile(io.BytesIO(res.content)) as z:
        xml_files = [name for name in z.namelist() if name.lower().endswith(".xml")]
        if not xml_files:
            raise RuntimeError("DART 기업코드 ZIP에 XML 파일이 없습니다.")
        with z.open(xml_files[0]) as xml_file:
            root = ET.parse(xml_file).getroot()

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

    if not rows:
        raise RuntimeError("DART 기업코드 XML에 상장 종목이 없습니다. CSV 저장을 중단합니다.")

    df = pd.DataFrame(rows)

    df.to_csv("corp_code.csv", index=False, encoding="utf-8-sig")

    print(df.head())
    print("Saved:", len(df))


if __name__ == "__main__":
    build_corp_db()
