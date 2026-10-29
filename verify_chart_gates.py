"""Read-only regular-session chart cross-check; no alerts/history writes."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from chart_engine import get_price_history, get_chart_score, _secondary_candles, HEADERS
for code in ('066570','267260','009150','009540','089030'):
    cache={}
    rows=get_price_history(code,cache=cache)
    assert rows, f'{code}: primary chart unavailable'
    chart=get_chart_score({'code':code},price_cache=cache)
    response=requests.get('https://fchart.stock.naver.com/sise.nhn',params={'symbol':code,'timeframe':'day','count':300,'requestType':0},headers=HEADERS,timeout=10)
    response.raise_for_status()
    secondary=_secondary_candles(response.text,code)
    matches=[(r,secondary[r['date']]) for r in rows if r['date'] in secondary]
    differences=[{'date':r['date'],'primary_close':r['close'],'secondary_close':s['close'],'primary_high':r['high'],'secondary_high':s['high'],'primary_volume':r['volume'],'secondary_volume':s['volume']} for r,s in matches if r['close']!=s['close'] or r['high']!=s['high']]
    high=max((r for r in rows if r['high']), key=lambda r:r['high'])
    print('LIVE CHART AUDIT:',json.dumps({'code':code,'details':chart['details'],'secondary_peak_same_day':secondary.get(high['date']), 'comparison_basis':'auxiliary_session_scope_unverified_not_auto_correction','largest_high_row':high,'last_rows':rows[-3:],'comparison_rows':len(matches),'difference_count':len(differences),'differences':differences[:12]},ensure_ascii=False),flush=True)
