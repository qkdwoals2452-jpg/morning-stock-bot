import zipfile
import xml.etree.ElementTree as ET
import requests
import pandas as pd
import io
import os
import tempfile
import time
import csv
import re

from config import DART_API_KEY

url = "https://opendart.fss.or.kr/api/corpCode.xml"

params = {
    "crtfc_key": DART_API_KEY
}

DOWNLOAD_TIMEOUT = (5, 20)
DOWNLOAD_BUDGET_SECONDS = 240
MAX_DOWNLOAD_BYTES = 32 * 1024 * 1024


def valid_corp_csv(path):
    """캐시/완성 CSV만 검증한다. CSV 내용이나 인증 정보를 로그에 남기지 않는다."""
    try:
        with open(path, encoding="utf-8-sig", newline="") as source:
            rows = list(csv.DictReader(source))
        return bool(rows) and all(
            # 실제 DART 신규 상장 코드에는 영문 대문자도 포함된다. 숫자로 강제 변환하지 않는다.
            re.fullmatch(r"[0-9A-Z]{6}", row.get("stock_code") or "")
            and re.fullmatch(r"[0-9]{8}", row.get("corp_code") or "")
            and (row.get("corp_name") or "").strip() for row in rows)
    except (OSError, UnicodeError, csv.Error):
        return False


def ensure_corp_db():
    """같은 주에서 복원된 CSV는 검증 후 재사용; 무효 파일은 성공 시에만 교체."""
    if not valid_corp_csv("corp_code.csv"):
        build_corp_db()
    if not valid_corp_csv("corp_code.csv"):
        raise RuntimeError("DART 기업코드 CSV 확인불가")
    print("DART CSV READY: validated")


def _download_corp_bytes():
    started = time.monotonic()
    response = None
    try:
        response = requests.get(url, params=params, timeout=DOWNLOAD_TIMEOUT, stream=True)
        response.raise_for_status()
        content = bytearray()
        last_report = started
        # timeout은 전체 다운로드 시간이 아니라 소켓 대기 시간이다.
        # 예산은 청크 수신 시 검사하며 DNS/청크 내부 대기의 강제 종료 타이머는 아니다.
        for chunk in response.iter_content(chunk_size=64 * 1024):
            now = time.monotonic()
            if now - started > DOWNLOAD_BUDGET_SECONDS:
                raise RuntimeError("DART 기업코드 다운로드 시간 예산 초과")
            content.extend(chunk)
            if len(content) > MAX_DOWNLOAD_BYTES:
                raise RuntimeError("DART 기업코드 다운로드 크기 제한 초과")
            if now - last_report >= 15:
                print(f"DART 다운로드 진행: {len(content)} bytes / {now - started:.1f}초")
                last_report = now
        if time.monotonic() - started > DOWNLOAD_BUDGET_SECONDS:
            raise RuntimeError("DART 기업코드 다운로드 시간 예산 초과")
        print(f"DART 다운로드 완료: {len(content)} bytes / {time.monotonic() - started:.1f}초")
        return bytes(content)
    except requests.RequestException as exc:
        raise RuntimeError(f"DART 기업코드 연결 실패 ({type(exc).__name__})") from None
    finally:
        if response is not None:
            response.close()


def build_corp_db():
    print("Downloading DART corp code...")

    content = _download_corp_bytes()

    # OpenDART 오류 응답은 ZIP 대신 XML로 올 수 있다.
    # API 키나 요청 URL을 로그에 출력하지 않는다.
    if not zipfile.is_zipfile(io.BytesIO(content)):
        try:
            error_root = ET.fromstring(content)
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
                "DART 기업코드 응답이 ZIP/XML이 아닙니다."
            )

    with zipfile.ZipFile(io.BytesIO(content)) as z:
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

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=".", prefix="corp_code.", suffix=".tmp", delete=False) as tmp:
            temp_path = tmp.name
        df.to_csv(temp_path, index=False, encoding="utf-8-sig")
        if not valid_corp_csv(temp_path):
            raise RuntimeError("DART 기업코드 CSV 검증 실패. 기존 CSV를 보존합니다.")
        os.replace(temp_path, "corp_code.csv")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

    print(df.head())
    print("Saved:", len(df))


if __name__ == "__main__":
    build_corp_db()
