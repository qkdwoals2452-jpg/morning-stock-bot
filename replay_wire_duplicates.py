"""Read-only replay of actual persisted duplicate records; never sends or saves state."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import sys
from breaking_news import scan, equivalent
from event_engine import build_events
from event_identity_engine import duplicate_article
state=json.load(open(sys.argv[1],encoding='utf-8'))
records=[r for r in state['records'] if r['event']['event_title']=='Coveo Acquires Anglera to Make Product Data a Competitive Advantage in AI-Powered eCommerce']
assert len(records)==2, 'Actual duplicate pair unavailable; no synthetic replacement'
a,b=[r['event']['articles'][0] for r in records]
assert a['link']!=b['link'] and duplicate_article(a,b)
events=build_events(deepcopy([a,b]))
assert len(events)==1 and events[0]['source_bonus']==0
assert equivalent(records[0]['event'],records[1]['event'])
now=datetime.now(timezone.utc)
existing=deepcopy(state)
existing['records']=[deepcopy(records[0])]
assert scan(existing,[deepcopy(b)],now)==(0,0)
assert existing['records'][0]==records[0], 'Existing delivery evidence was changed'
new={'version':1,'records':[],'initialized_at':state['initialized_at'],'activation':{'phase':'sent'}}
assert scan(new,deepcopy([a,b]),now)==(1,0)
print('ACTUAL WIRE REPLAY:',json.dumps({'stored_duplicates':len(records),'merged_events':len(events),'source_bonus':events[0]['source_bonus'],'already_sent_copy_requeued':False,'fresh_records':len(new['records']),'live_state_modified':False,'telegram_sent':False}),flush=True)
