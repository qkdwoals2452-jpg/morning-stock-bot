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

# The operational store expires old stories. Select existing articles, never synthetic ones.
advice=[r['event'] for r in records if any(phrase in r['event']['event_title'] for phrase in
    ("Here's How Much You'd Need to Invest", "If I Only Had $500 to Invest",
     "Best Way to Invest in Anthropic and OpenAI"))]
assert advice, 'Actual stored investment advice unavailable'
for event in advice:
    for article in event['articles']:
        assert not understand_event(article)['is_real_event']
    assert not headline_action(event)
stocks=load_korean_stocks()
selected=None
for code in ('005380', '009150', '000270', '011210'):
    stock=next((s for s in stocks if s['code']==code),None)
    if not stock:
        continue
    candidates=[r['event'] for r in records if
        any(stock['name'] in a.get('title','') for a in r['event']['articles'])
        and assess_company_event_relation(stock,r['event']['articles'])['pass']]
    if candidates:
        selected=candidates[-1]
        break
assert selected, 'Actual listed actor event unavailable'
print('ACTUAL KRX IDENTITY:', stock['name'], stock['code'], flush=True)
routes=build_analysis_routes(build_events(selected['articles']),[],stocks,[],3)
assert stock['code'] in {c for r in routes for c in r['candidate_codes']}
from build_corp_db import ensure_corp_db
ensure_corp_db()
from main import run
results,status=run(news_override=selected['articles'],notify=False,track_history=False)
a=status['analysis_status']
decisions={x['code'] for x in a['excluded']} | {s['code'] for b in results for s in b['ranked']}
assert stock['code'] in decisions
print('ACTUAL LABEL REPLAY:',json.dumps({'investment_advice_blocked':len(advice),'listed_actor':stock['name'],'analyzed':a['analyzed_count'],'selected':a['selected_count'],'excluded':a['excluded'],'basis':'current_external_data_not_historical_signal_reproduction'},ensure_ascii=False),flush=True)
