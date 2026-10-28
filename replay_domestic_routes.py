"""Replay an actual stored event with live KRX/finance/price data, without alerts/history writes."""
import argparse
import json
from event_engine import build_events
from stock_engine import load_korean_stocks, build_analysis_routes
from impact_engine import assess_company_event_relation

TITLE = '하나·우리금융, 3분기 순이익 1조 돌파'
TARGETS = [(TITLE, {'086790', '316140'}),
           ('소마젠, 50억 규모 저커버그 재단 세포 분석 사업 추가 수주', {'950200'}),
           ('HD한국조선해양, 3분기 영업이익 1조 4472억원…전년比 37.3% 증가', {'009540'})]


def replay(path):
    state = json.loads(open(path, encoding='utf-8').read())
    stocks = load_korean_stocks()
    from build_corp_db import ensure_corp_db
    ensure_corp_db()
    from main import run
    for title, expected in TARGETS:
        records = [r for r in state['records'] if r['event']['event_title'] == title]
        if len(records) != 1:
            raise RuntimeError('실제 저장 기사 식별 실패: 가상 기사로 대체하지 않습니다')
        articles = records[0]['event']['articles']
        if not articles or any(not a.get('link') or not a.get('published_at') for a in articles):
            raise RuntimeError('원문·발행 시각 없는 기사 재실행 금지')
        routes = build_analysis_routes(build_events(articles), [], stocks, [], 3)
        linked = {code for route in routes for code in route['candidate_codes']}
        if linked != expected:
            raise RuntimeError(f'실제 KRX 연결 불일치: {sorted(linked)}')
        for stock in stocks:
            if stock['code'] in linked:
                if not assess_company_event_relation(stock, articles)['pass']:
                    raise RuntimeError('당사자 관계 검증 실패')
                print('LIVE KRX EVENT ACTOR:', stock['name'], stock['code'])
        results, status = run(news_override=articles, notify=False, track_history=False)
        analysis = status['analysis_status']
        decisions = {x['code'] for x in analysis['excluded']} | {
            x['code'] for block in results for x in block['ranked']}
        if not expected <= decisions:
            raise RuntimeError('대상 종목의 실제 검증·제외 경로 진입 실패')
        if title == TITLE:
            if (analysis['selected_count'] != 0 or len(analysis['excluded']) != 2
                    or any(item['stage'] != 'finance_model' for item in analysis['excluded'])):
                raise RuntimeError('금융회사 전용 모델 보류 사유 검증 실패')
        elif any(x['code'] in expected and x['stage'] == 'finance_model' for x in analysis['excluded']):
            raise RuntimeError('비금융 회사가 금융업으로 보류됨')
        print('LIVE STORED EVENT REPLAY:', title, json.dumps(analysis, ensure_ascii=False))
    print('원문 발행 시점의 과거 신호 재현이 아니라 현재 외부 데이터로 연결·제외 경로를 검증한 결과입니다.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('state')
    replay(parser.parse_args().state)
