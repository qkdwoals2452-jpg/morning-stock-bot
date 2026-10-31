import os
from collections import Counter
from event_understanding_engine import classify_article_role
from news_quality_engine import filter_core_news
from event_engine import build_events
from event_audit_engine import print_event_audit
from sector_filter_engine import pass_theme_sector_filter
from company_verify_engine import verify_company_theme, verify_direct_company_event
from config import *
from news_engine import get_us_news, get_korea_news
from theme_engine import extract_themes, expand_theme_words, build_event_analysis_themes
from stock_engine import load_korean_stocks, find_related_stocks, build_analysis_routes
from company_engine import get_company_match_score
from impact_engine import get_news_impact_score, assess_company_event_relation
from market_engine import get_market_score
from chart_engine import get_chart_score, pass_long_term_trend, chart_rejection_evidence
from scoring_engine import make_stock_result, sort_results, make_grade
from memory_engine import save_today_result, get_project_status
from backtest_engine import save_recommendations, update_backtest_prices
from memory_learning_engine import get_learning_score, save_prediction
from telegram_bot import send_telegram
from pre_news_activity_engine import get_pre_news_activity
from supply_chain_engine import build_supply_chain_watch


def run(news_override=None, notify=True, track_history=True):
    if not os.path.exists("corp_code.csv"):
        print("corp_code.csv 없음 → DART 기업코드 생성")
        from build_corp_db import build_corp_db
        build_corp_db()

    # 재무 모듈은 기업코드 CSV를 읽으므로 생성 후 가져온다.
    from finance_engine import get_finance_score

    stocks = load_korean_stocks()
    if not stocks:
        raise RuntimeError("KRX 종목 목록 확인불가 → 추천·운영 기록·전송 중단")
    regular_price_cache = {}
    if track_history:
        update_backtest_prices(stocks, price_cache=regular_price_cache)

    us_news = get_us_news() if news_override is None else [a for a in news_override if a.get('market') != 'KR']
    kr_news = get_korea_news() if news_override is None else [a for a in news_override if a.get('market') == 'KR']

    news = us_news + kr_news

    print("미국 뉴스 수:", len(us_news))
    print("\n===== 미국 원본 뉴스 TOP20 =====")

    for article in us_news[:20]:
        print(
            article.get("source", ""),
            "|",
            article.get("published_at", ""),
            "|",
            article.get("title", "")
        )
    print("한국 뉴스 수:", len(kr_news))
    print("전체 뉴스 수:", len(news))
    roles = Counter(classify_article_role(article.get("title", ""), article.get("summary", ""))
                    for article in news)
    print("기사 성격 집계 (후보는 확정 사건 아님):", dict(roles))

    event_decisions = []
    events = build_events(news, decisions=event_decisions)
    print_event_audit(event_decisions, len(events))
    supply_chain_watch = build_supply_chain_watch(events, stocks)
    print("미국 사건→국내 공급망 관찰(점수 반영 없음):", supply_chain_watch)

    print("생성된 사건 수:", len(events))

    print("\n===== 핵심 사건 TOP10 =====")

    for event in events[:10]:

        print(

            event.get("event_grade", ""),

            event.get("event_score", 0),

            event.get("event_type", ""),

            event.get("event_title", "")

        )

        print(

            "식별 출처 수:",

            event.get("source_count", 0),

            "| 보도 기사 수:", len(event.get("articles", [])),
            "| 교차보도 가산:", event.get("source_bonus", 0),

            "| 돈의 흐름:",

            event.get("money_flow", [])

        )

    # 기존 시스템은 아직 유지
    # =====================================================
    # ORION EVENT QUALITY HARD GATE
    # S/A급 실제 사건의 원본 기사만 추천 엔진으로 전달
    # =====================================================

    important_events = [
        event
        for event in events
        if event.get("event_score", 0) >= 70
    ]
    analysis_status = {'news_count': len(news), 'event_count': len(events),
                       'strong_event_count': len(important_events), 'excluded': []}
    analyzed_codes = set()

    def reject(stock, stage, reason, evidence=None):
        reason = reason or '검증 기준 미달'
        analysis_status['excluded'].append({
            'name': stock['name'], 'code': stock['code'],
            'stage': stage, 'reason': reason})
        if evidence:
            analysis_status['excluded'][-1]['evidence'] = evidence
        print('제외:', stock['name'], reason)

    event_news = []
    seen = set()

    for event in important_events:
        for article in event.get("articles", []):
            key = (
                article.get("link", "")
                or article.get("title", "")
            )

            if key in seen:
                continue

            seen.add(key)
            event_news.append(article)

    news = event_news
    # =====================================================
    # ORION EVENT → DIRECT COMPANY TEST
    # 중요한 사건에서 기사에 직접 등장한 한국 상장사 확인
    # 아직 실제 추천에는 사용하지 않음
    # =====================================================

    print("\n===== EVENT → DIRECT COMPANY TEST =====")

    for event in important_events:

        event_articles = event.get("articles", [])

        test_theme = {
            "name": event.get("event_type", "EVENT"),
            "score": event.get("event_score", 0),
            "articles": event_articles
        }

        direct_candidates = find_related_stocks(
            test_theme,
            stocks,
            event_articles
        )

        print(
            event.get("event_grade", ""),
            event.get("event_score", 0),
            event.get("event_type", ""),
            event.get("event_title", "")
        )

        print(
            "직접 연결 한국종목:",
            [
                stock["name"]
                for stock in direct_candidates
            ]
        )

        print("-----")
    print("핵심 뉴스 수:", len(news))
    print("\n===== 핵심 뉴스 TOP10 =====")
    for article in news[:10]:
        print(
            article.get("market", ""),
            article.get("quality_score", 0),
            article.get("title", "")
        )
    themes = extract_themes(news)

    print("뉴스 개수:", len(news))
    print("테마 개수:", len(themes))
    # print(themes[:5])
    for t in themes[:10]:
        

        print("테마순위:", t["name"], t["score"])
    # =====================================================
    # EVENT → ANALYSIS OBJECT TEST
    # Event를 기존 종목 검증엔진과 연결하기 위한 중간 구조
    # 아직 실제 추천에는 사용하지 않음
    # =====================================================

    event_analysis_objects = []

    for event in important_events:

        event_articles = event.get("articles", [])

        event_object = {
            "name": event.get("event_type", "EVENT"),
            "score": event.get("event_score", 0),
            "articles": event_articles,

            # Event 고유 정보
            "event_title": event.get("event_title", ""),
            "event_type": event.get("event_type", "NO_EVENT"),
            "money_flow": event.get("money_flow", {}),
            "source_count": event.get("source_count", 0),
            "evidence_strength": event.get("evidence_strength", "WEAK"),
            "evidence_reason": event.get("evidence_reason", ""),
        }

        event_analysis_objects.append(event_object)


    print("\n===== EVENT ANALYSIS OBJECTS =====")
    print("\n===== EVENT ANALYSIS OBJECTS =====")

    for obj in event_analysis_objects:
        print(
            obj["event_type"],
            obj["score"],
            obj["event_title"],
            "기사수:",
            len(obj["articles"]),
            "| EVIDENCE:",
            obj.get("evidence_strength", ""),
            "|",
            obj.get("evidence_reason", "")
        )

    for obj in event_analysis_objects:
        print(
            obj["event_type"],
            obj["score"],
            obj["event_title"],
            "기사수:",
            len(obj["articles"])
        )
    # 키워드 빈도 대신 실제 사건 점수를 검증 입력으로 사용한다.
    themes = build_event_analysis_themes(important_events, themes)
    final_results = []
    pre_news_cache = {}
    # 동일한 분석 개수 안에서 국내 직접 후보가 있는 사건을 먼저 검증한다.
    # 후보 발견은 추천 자격이 아니며 아래 당사자·재무·차트 검증을 모두 거친다.
    themes = build_analysis_routes(important_events, themes, stocks, news, TOP_THEME_COUNT)
    print("실제 분석 테마 수:", len(themes))
    
    for theme in themes:
        print("테마 확인:", theme["name"], "점수:", theme["score"], "통과기준:", MIN_THEME_SCORE)
        print("사건 점수:", theme["event_score"], "키워드 빈도 점수:", theme["frequency_score"])
        print("THEME KEYS:", theme.keys())

        articles = theme.get("articles", [])

        print("ARTICLE COUNT:", len(articles))

        if articles:

            print("ARTICLE KEYS:", articles[0].keys())

            print("FIRST ARTICLE:", articles[0])
        if theme["score"] < MIN_THEME_SCORE:
            continue

        candidates = find_related_stocks(
            theme,
            stocks,
            news
        )
        if theme.get('analysis_route') == 'DIRECT_EVENT':
            candidates = [stock for stock in candidates
                          if stock['code'] in theme['candidate_codes']]
        candidates = candidates[:10]
        print("실제 정밀분석 종목 수:", len(candidates))
        theme_words = ([] if theme.get('analysis_route') == 'DIRECT_EVENT'
                       else expand_theme_words(theme['name']))

        ranked = []

        for stock in candidates:
            analyzed_codes.add(stock['code'])
            if stock["name"] in ["SG"]:
                reject(stock, 'policy', '운영 제외 종목')
                continue
            connection = assess_company_event_relation(stock, articles)
            if not connection["pass"]:
                reject(stock, 'connection', connection['reason'])
                continue
            print("사건 연결 근거:", stock["name"], connection)
            verified_connection = {
                'name': stock['name'], 'code': stock['code'],
                'role': connection['role'], 'evidence': connection.get('evidence', [])[:1]}
            if verified_connection not in analysis_status.setdefault('connections', []):
                analysis_status['connections'].append(verified_connection)
            if stock['code'] in {'005930', '000660', '034730', '402340'}:
                reject(stock, 'policy', '대형주·지주사 참고용 제외')
                continue
            verify = (verify_direct_company_event(stock, articles)
                      if theme.get('analysis_route') == 'DIRECT_EVENT'
                      else verify_company_theme(stock, theme['name']))
            print('기업 검증:', stock['name'], verify)

            if not verify["pass"]:
                reject(stock, 'business', verify.get('memo', '사업내용 검증 미달'))
                continue

            finance = get_finance_score(stock)
            print('재무 검증:', stock['name'], finance)
            if finance.get('model_coverage') == 'UNSUPPORTED_FINANCIAL_SECTOR':
                reject(stock, 'finance_model', finance['exclude_reason'])
                continue
            if finance.get("op_margin") is None or finance.get("debt_ratio") is None:
                reject(stock, 'finance', '핵심 재무 데이터 확인불가')
                continue
            if finance.get("exclude"):

                reject(stock, 'finance', finance.get('exclude_reason', '재무 기준 미달'))

                continue
            market = get_market_score(stock, price_cache=regular_price_cache)
            chart = get_chart_score(stock, price_cache=regular_price_cache)
            learning = get_learning_score(stock)
            if theme.get('analysis_route') == 'DIRECT_EVENT':
                # 이 경로는 해당 회사 자신의 사건이다. AI 등 다른 분야의
                # 검색 키워드 점수로 기업 카드를 만들거나 추천을 배제하지 않는다.
                company = {
                    'score': 0, 'exclude': not verify['pass'],
                    'memo': verify['memo'], 'exclude_reason': verify['memo'],
                    'matched': {'business': verify['matched']},
                    'source': verify['source'],
                }
            else:
                company = get_company_match_score(stock, theme_words)
            impact = get_news_impact_score(

                stock=stock,

                theme=theme,

                articles=articles,

                company=company

            )

            print("impact:", impact)
            # =====================================================
            # 기사 ↔ 종목 직접 관계성 HARD GATE
            # =====================================================

            if impact.get("exclude") is True:

                reject(stock, 'connection', impact.get(
                    'exclude_reason', '기사와 기업의 직접 연결 근거 부족'))

                continue

            
            ok, reason = pass_theme_sector_filter(

                theme["name"],

                stock,

                company

            )
            print("SECTOR FILTER:", stock["name"], ok, reason)
            if not ok:

                reject(stock, 'sector', reason)

                continue
            
            print("==========")
            print(stock["name"])
            print("verify:", verify)
            print("company:", company)
            print("finance:", finance)
            print("market:", market)
            print("chart:", chart)
            # 추천 제외 필터

            if finance.get("exclude") == True:

                reject(stock, 'finance', finance.get('exclude_reason'))

                continue
            if company.get("exclude") == True:
                reject(stock, 'business', company.get('exclude_reason'))
                continue
            

            if chart.get("details", {}).get("high_52w_gap") is None:
                reject(stock, 'chart', '52주 고점 대비 낙폭 확인불가', chart_rejection_evidence(chart))
                continue

            if chart.get("details", {}).get("high_52w_gap") is not None:

                if chart["details"]["high_52w_gap"] <= -60:

                    reject(stock, 'chart', '52주 고점 대비 -60% 이하', chart_rejection_evidence(chart))

                    continue

            trend_ok, trend_reason = pass_long_term_trend(chart)
            if not trend_ok:
                reject(stock, 'chart', trend_reason, chart_rejection_evidence(chart))
                continue

            if market.get("trading_value") is None:
                reject(stock, 'market', '거래대금 확인불가')
                continue
            else:
                if market["trading_value"] < 30_0000_0000:
                    reject(stock, 'market', '거래대금 30억 미만')
                    continue
            result = make_stock_result(
                stock=stock,
                # 사건 점수는 분석 진입·우선순위에 사용한다.
                # 빈도는 감사용으로 보존하되 최종 정렬 점수에는 가산하지 않는다.
                theme_score=theme["frequency_score"],
                finance=finance,
                market=market,
                verify=verify,
                company=company,
                chart=chart,
                learning=learning,
                impact=impact,
                event_score=theme["event_score"]
            )
            result["event_connection"] = connection
            ranked.append(result)
        ranked = sort_results(ranked)

        if not ranked:
            continue

        top_ranked = ranked[:TOP_STOCK_COUNT]
        for stock in ranked[TOP_STOCK_COUNT:]:
            reject(stock, 'rank_limit', '검증 통과 후 표시 개수 제한')
        print(
            "추가됨:",
            theme["name"],
            "종목수:",
            len(top_ranked)
        )
        final_results.append({
            "theme": theme,
            "ranked": top_ranked
        })

        for stock in top_ranked:
            stock["pre_news_activity"] = get_pre_news_activity(
                stock, stock.get("event_connection", {}), cache=pre_news_cache)
            print("뉴스 이전 거래활동:", stock["name"], stock["pre_news_activity"])
            if track_history:
                save_prediction(theme["name"], stock, stock["final_score"])

    if track_history:
        save_today_result(final_results)
        save_recommendations(final_results)
        update_backtest_prices(stocks, price_cache=regular_price_cache)
    project_status = get_project_status()
    project_status['supply_chain_watch'] = supply_chain_watch
    selected_codes = {stock['code'] for block in final_results for stock in block['ranked']}
    analysis_status['analyzed_count'] = len(analyzed_codes)
    analysis_status['selected_count'] = len(selected_codes)
    analysis_status['excluded'] = [item for item in analysis_status['excluded']
                                   if item['code'] not in selected_codes]
    project_status['analysis_status'] = analysis_status
    print('운영 분석 결과:', analysis_status)

    if notify:
        send_telegram(final_results, project_status)
    return final_results, project_status


if __name__ == "__main__":
    run()
