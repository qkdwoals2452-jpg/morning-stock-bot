"""Actual stored articles + live KRX identities. No sending or history writes."""
import json,re,sys
from stock_engine import load_korean_stocks,find_direct_mentions
from impact_engine import assess_company_event_relation
from build_corp_db import ensure_corp_db
state=json.load(open(sys.argv[1],encoding='utf-8'))
fixtures=json.load(open('fixtures/issuer_actual_articles.json',encoding='utf-8'))
articles=list({a['link']:a for a in ([a for r in state['records'] for a in r['event']['articles']]+fixtures)}.values())
stocks=load_korean_stocks()
english=[s for s in stocks if re.fullmatch(r'[A-Za-z][A-Za-z0-9& .-]*',s['name'])]
new=next(s for s in stocks if s['code']=='160550')
observed=[a for a in articles if a.get('market')=='US' and re.search(r'\bnew\b',a.get('title','')+' '+a.get('summary',''),re.I)]
assert observed, 'Actual NEW-word cases unavailable'
for a in observed:
    assert not find_direct_mentions({'articles':[a]},[new],[]), a['title']
    assert not assess_company_event_relation(new,[a])['pass'], a['title']
connections=[]
for a in articles:
    m=find_direct_mentions({'articles':[a]},english,[])
    for s in english:
        if s['name'] in m:
            assert assess_company_event_relation(s,[a])['pass']
            connections.append({'code':s['code'],'name':s['name'],'title':a['title']})
# Exact original Samsung CAPEX article retained from the reported production log.
samsung=next(a for a in fixtures if a['title'].startswith('삼성전자, 설비투자 84조'))
ensure_corp_db()
from main import run
results,status=run(news_override=[samsung],notify=False,track_history=False)
excluded=status['analysis_status']['excluded']
assert any(x['code']=='005930' and x['stage']=='policy' for x in excluded), excluded
assert not any(x['code']=='160550' for x in excluded), excluded
print('ACTUAL IDENTITY AUDIT:',json.dumps({'krx_english_named_issuers':len(english),'stored_articles':len(articles),'actual_new_word_articles':len(observed),'false_NEW_candidates':0,'verified_english_name_connections':connections,'samsung_decision':excluded,'telegram_sent':False,'tracking_written':False},ensure_ascii=False),flush=True)
