"""Read primary contract without sending alerts or writing recommendation data."""
from config import DART_API_KEY
from dart_document_engine import fetch_contract_document
import json
for receipt in ['20261028900224']:
    doc = fetch_contract_document(receipt, '테크윙', DART_API_KEY)
    assert all(v in doc['text'] for v in ['Micron Semiconductor Technology India', '9,497,217,450', '반도체 검사장비'])
    print('TECHWING PRIMARY:', json.dumps(doc, ensure_ascii=False), flush=True)
