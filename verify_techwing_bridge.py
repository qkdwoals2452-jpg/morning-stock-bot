"""Read primary contract without sending alerts or writing recommendation data."""
from config import DART_API_KEY
from dart_document_engine import fetch_contract_document
import json
for receipt in ['20261028900224']:
    doc = fetch_contract_document(receipt, '테크윙', DART_API_KEY)
    assert all(v in doc['text'] for v in ['Micron Semiconductor Technology India', '9,497,217,450', '반도체 검사장비'])
    print('TECHWING PRIMARY:', json.dumps(doc, ensure_ascii=False), flush=True)
from stock_engine import load_korean_stocks
from news_engine import get_us_news
from event_engine import build_events
from supply_chain_engine import build_supply_chain_watch
stocks=load_korean_stocks()
assert any(s['code']=='089030' and s['name']=='테크윙' for s in stocks), 'Live KRX listing mismatch'
news=get_us_news(limit=None)
assert news, 'No live US news collected'
watch=build_supply_chain_watch(build_events(news), stocks)
assert watch['status']=='ok'
print('LIVE BRIDGE:', json.dumps({'news_count':len(news),'events_checked':watch['us_events_checked'], 'paths':[{'path':p['path'],'code':p['code'],'new_order_confirmed':p['new_order_confirmed'],'recommendation_eligible':p['recommendation_eligible']} for p in watch['paths']]},ensure_ascii=False),flush=True)
