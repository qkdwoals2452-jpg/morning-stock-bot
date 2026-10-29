"""Replay actual stored articles against current external data; never send/history-write."""
import json
import sys
from event_engine import build_events
from event_understanding_engine import understand_event
from stock_engine import load_korean_stocks, build_analysis_routes
from impact_engine import assess_company_event_relation
from breaking_event_gate import headline_action

state=json.load(open(sys.argv[1],encoding='utf-8'))
records=state['records']
records=list(records.values()) if isinstance(records,dict) else records

def actual(title):
    found=[r['event'] for r in records if r['event']['event_title']==title]
    assert len(found)==1, 'Actual stored event unavailable; do not fabricate'
    return found[0]

hyundai=actual('[속보] 현대차 3분기 영업이익 2조6772억…연간 판매 목표는 하향')
cola=actual("Here's How Much You'd Need to Invest in Coca-Cola to Generate $1,000 in Yearly Dividends")
for article in cola['articles']:
    assert not understand_event(article)['is_real_event']
assert not headline_action(cola)
stocks=load_korean_stocks()
stock=next(s for s in stocks if s['code']=='005380')
assert assess_company_event_relation(stock,hyundai['articles'])['pass']
routes=build_analysis_routes(build_events(hyundai['articles']),[],stocks,[],3)
assert '005380' in {c for r in routes for c in r['candidate_codes']}
from build_corp_db import ensure_corp_db
ensure_corp_db()
from main import run
results,status=run(news_override=hyundai['articles'],notify=False,track_history=False)
a=status['analysis_status']
decisions={x['code'] for x in a['excluded']} | {s['code'] for b in results for s in b['ranked']}
assert '005380' in decisions
print('ACTUAL LABEL REPLAY:',json.dumps({'cola_explainer_blocked':True,'hyundai_actor':stock['name'],'analyzed':a['analyzed_count'],'selected':a['selected_count'],'excluded':a['excluded'],'basis':'current_external_data_not_historical_signal_reproduction'},ensure_ascii=False),flush=True)
