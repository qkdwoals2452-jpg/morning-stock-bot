"""Replay an actual stored event with live KRX/finance/price data, without alerts/history writes."""
import argparse
import json
from event_engine import build_events
from stock_engine import load_korean_stocks, build_analysis_routes
from impact_engine import assess_company_event_relation

TITLE = '하나·우리금융, 3분기 순이익 1조 돌파'


def replay(path):
    state = json.loads(open(path, encoding='utf-8').read())
    records = [r for r in state['records'] if r['event']['event_title'] == TITLE]
    if len(records) != 1:
        raise RuntimeError('실제 저장 기사 식별 실패: 가상 기사로 대체하지 않습니다')
    articles = records[0]['event']['articles']
    if not articles or any(not a.get('link') or not a.get('published_at') for a in articles):
        raise RuntimeError('원문·발행 시각 없는 기사 재실행 금지')
    stocks = load_korean_stocks()
    routes = build_analysis_routes(build_events(articles), [], stocks, [], 3)
    linked = {code for route in routes for code in route['candidate_codes']}
    if linked != {'086790', '316140'}:
        raise RuntimeError(f'실제 KRX 연결 불일치: {sorted(linked)}')
    for stock in stocks:
        if stock['code'] in linked:
            if not assess_company_event_relation(stock, articles)['pass']:
                raise RuntimeError('당사자 관계 검증 실패')
            print('LIVE KRX EVENT ACTOR:', stock['name'], stock['code'])
    from build_corp_db import ensure_corp_db
    ensure_corp_db()
    from main import run
    results, status = run(news_override=articles, notify=False, track_history=False)
    analysis = status['analysis_status']
    if analysis['analyzed_count'] != 2:
        raise RuntimeError('두 종목의 실제 검증 경로 진입 실패')
    print('LIVE STORED EVENT REPLAY:', json.dumps(analysis, ensure_ascii=False))
    print('원문 발행 시점의 과거 신호 재현이 아니라 현재 외부 데이터로 연결·제외 경로를 검증한 결과입니다.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('state')
    replay(parser.parse_args().state)
