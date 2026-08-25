from event_understanding_engine import understand_event
# ORION Event Engine Test Set v1
# 실제 사건 판별기의 성능을 본 시스템 연결 전에 검증한다.

TEST_CASES = [

    {
        "id": 1,
        "title": "Cisco forecasts annual revenue above estimates on sustained AI spending",
        "expected_event": True,
        "expected_type": "EARNINGS",
        "note": "실제 기업 가이던스"
    },

    {
        "id": 2,
        "title": "TSMC to invest $29.4 billion in advanced chip production",
        "expected_event": True,
        "expected_type": "CAPEX",
        "note": "실제 대규모 설비투자"
    },

    {
        "id": 3,
        "title": "CoreWeave revenue doubles as AI infrastructure demand surges",
        "expected_event": True,
        "expected_type": "EARNINGS",
        "note": "실제 매출 성장"
    },

    {
        "id": 4,
        "title": "Foxconn posts quarterly profit surge on AI server demand",
        "expected_event": True,
        "expected_type": "EARNINGS",
        "note": "AI 서버 수요에 따른 실제 실적 변화"
    },

    {
        "id": 5,
        "title": "Super Micro reports $60 billion order backlog",
        "expected_event": True,
        "expected_type": "CONTRACT",
        "note": "대규모 수주잔고"
    },

    {
        "id": 6,
        "title": "Kingspan agrees to buy data center firm BMC for €900 million",
        "expected_event": True,
        "expected_type": "M&A",
        "note": "실제 인수"
    },

    {
        "id": 7,
        "title": "기가비스, 중국 반도체 기판 업체와 111억 검사장비 공급계약",
        "expected_event": True,
        "expected_type": "CONTRACT",
        "note": "실제 공급계약"
    },

    {
        "id": 8,
        "title": "비츠로넥스텍, 한화에어로와 535억 규모 누리호 엔진 부품 공급계약",
        "expected_event": True,
        "expected_type": "CONTRACT",
        "note": "실제 공급계약"
    },

    {
        "id": 9,
        "title": "클래시스, 2분기 매출 1055억 사상 첫 분기 매출 1000억 돌파",
        "expected_event": True,
        "expected_type": "EARNINGS",
        "note": "실제 실적"
    },

    {
        "id": 10,
        "title": "케이엔에스, 상반기 영업이익 30억 70% 급증",
        "expected_event": True,
        "expected_type": "EARNINGS",
        "note": "영업이익 성장"
    },

    # -------------------------------
    # 아래부터는 반드시 버려야 하는 기사
    # -------------------------------

    {
        "id": 11,
        "title": "Expert urges investors to spread bets across the AI universe",
        "expected_event": False,
        "expected_type": "NO_EVENT",
        "note": "전문가 투자 의견"
    },

    {
        "id": 12,
        "title": "Advanced Micro Devices vs. AppLovin: Which Technology Stock Is a Better Buy in 2026?",
        "expected_event": False,
        "expected_type": "NO_EVENT",
        "note": "종목 비교/매수 콘텐츠"
    },

    {
        "id": 13,
        "title": "The $1.3 Trillion Inference War Is Heating Up. 3 Stocks to Watch.",
        "expected_event": False,
        "expected_type": "NO_EVENT",
        "note": "추천주 콘텐츠"
    },

    {
        "id": 14,
        "title": "1 Reason BYD Could Be the Top Stock Investors Are Missing",
        "expected_event": False,
        "expected_type": "NO_EVENT",
        "note": "투자 권유"
    },

    {
        "id": 15,
        "title": "3 Reasons We Love Meta",
        "expected_event": False,
        "expected_type": "NO_EVENT",
        "note": "의견/추천"
    },

    {
        "id": 16,
        "title": "Why is Enersys stock surging today?",
        "expected_event": False,
        "expected_type": "NO_EVENT",
        "note": "단순 주가 움직임"
    },

    {
        "id": 17,
        "title": "Memory Stocks Rally Wednesday: SK Hynix, SanDisk, Micron All Jump. Here's Why",
        "expected_event": False,
        "expected_type": "NO_EVENT",
        "note": "시장반응 기사"
    },

    {
        "id": 18,
        "title": "Cerebras Set to Report Earnings as AI Chips Enter a New Era",
        "expected_event": False,
        "expected_type": "NO_EVENT",
        "note": "실적 발표 전 전망"
    },

    {
        "id": 19,
        "title": "Dow Jones Futures: Nvidia Partners Lead Earnings Movers; CPI Data Due",
        "expected_event": False,
        "expected_type": "NO_EVENT",
        "note": "시장 프리뷰"
    },

    {
        "id": 20,
        "title": "Amazon Grew Revenue 20%. Here's Why Amazon Trades at 22 Times Forward Earnings",
        "expected_event": False,
        "expected_type": "NO_EVENT",
        "note": "과거 실적을 이용한 밸류에이션 해설"
    },

        
    
    { 
        "id": 21,
        "title": "Stripe agrees to acquire AI model router OpenRouter",
        "expected_event": True,
        "expected_type": "M&A",
        "note": "실제 AI 기업 인수"
    },

    # -------------------------------
    # 실전 오탐 + 정책/루머 경계 테스트
    # -------------------------------

    {
        "id": 22,
        "title": "[사설] N% 성과급 파업 확산, 노사 갈등 더 이상 방치 안 돼",
        "expected_event": False,
        "expected_type": "NO_EVENT",
        "note": "영업이익이 언급돼도 사설·노사갈등은 실적 사건 아님"
    },

    {
        "id": 23,
        "title": "4억 뇌물에 1.7조억 수주 '유리한 평가' 악재…LIG D&A, 급락",
        "expected_event": False,
        "expected_type": "NO_EVENT",
        "note": "과거 수주가 언급된 수사·악재 기사"
    },

    {
        "id": 24,
        "title": "\"한화에어로, K9 美 진출 '단일 수주 이상 의미'…목표가↑\"-DS",
        "expected_event": False,
        "expected_type": "NO_EVENT",
        "note": "증권사 목표가·분석 기사이며 신규 수주 아님"
    },

    {
        "id": 25,
        "title": "TSLA Stock Eyes Another Winning Week: Musk Sees 'Crazy' Tesla Growth",
        "expected_event": False,
        "expected_type": "NO_EVENT",
        "note": "성장 전망·주가반응 기사이며 실제 실적 발표 아님"
    },

    {
        "id": 26,
        "title": "S&P 500, Nasdaq end down on tech stocks, investors weigh Iran moves",
        "expected_event": False,
        "expected_type": "NO_EVENT",
        "note": "시장 종합기사 속 정책 언급은 직접 정책 사건으로 보지 않음"
    },

    {
        "id": 27,
        "title": "Federal Reserve cuts interest rates by 25 basis points",
        "expected_event": True,
        "expected_type": "FOMC",
        "note": "실제 미국 기준금리 결정"
    },

    {
        "id": 28,
        "title": "US imposes new export restrictions on advanced AI chips",
        "expected_event": True,
        "expected_type": "POLICY",
        "note": "실제 정부 수출규제 시행"
    },

    {
        "id": 29,
        "title": "Trump announces 25% tariff on semiconductor imports",
        "expected_event": True,
        "expected_type": "POLICY",
        "note": "실제 관세 정책 발표"
    },

    {
        "id": 30,
        "title": "Apple reportedly in talks to acquire AI startup",
        "expected_event": False,
        "expected_type": "NO_EVENT",
        "note": "인수 협상설·미확정 M&A"
    },

    {
        "id": 31,
        "title": "Nvidia announces $50 billion investment in AI infrastructure",
        "expected_event": True,
        "expected_type": "CAPEX",
        "note": "실제 기업 투자 발표"
    },
]

if __name__ == "__main__":

    print("=" * 70)
    print("ORION EVENT ENGINE TEST v1")
    print("=" * 70)

    correct = 0
    wrong = 0

    for case in TEST_CASES:

        article = {
            "title": case["title"],
            "summary": ""
        }

        result = understand_event(article)

        event_ok = (
            result["is_real_event"]
            == case["expected_event"]
        )

        type_ok = (
            result["event_type"]
            == case["expected_type"]
        )

        passed = event_ok and type_ok

        if passed:
            correct += 1
            mark = "✅"
        else:
            wrong += 1
            mark = "❌"

        print()
        print(
            mark,
            f"{case['id']:02d}",
            case["title"]
        )

        print(
            "   정답:",
            case["expected_event"],
            case["expected_type"]
        )

        print(
            "   판정:",
            result["is_real_event"],
            result["event_type"]
        )

        print(
            "   이유:",
            result["reason"]
        )


    score = (
        correct / len(TEST_CASES)
    ) * 100

    print()
    print("=" * 70)

    print(
        f"결과: {correct}/{len(TEST_CASES)}"
    )

    print(
        f"정확도: {score:.1f}%"
    )

    print(
        f"오답: {wrong}개"
    )

    if correct >= 18:
        print("🟢 1차 통과")
    else:
        print("🔴 본체 연결 금지")

    print("=" * 70)
from news_engine import get_all_news
from event_engine import merge_same_events, calc_event_score


print("\n" + "=" * 70)
print("ORION EVENT ENGINE LIVE TEST")
print("=" * 70)

news = get_all_news()

print(f"\n실제 수집 뉴스 수: {len(news)}")
print("\n===== ORION REVIEW QUEUE =====")

review_count = 0

for article in news:
    score, reasons = calc_event_score(article)

    if score > 0:
        review_count += 1

        print()
        print(f"[REVIEW {review_count:02d}]")
        print("제목:", article.get("title", ""))
        print("요약:", article.get("summary", ""))
        print("출처:", article.get("source", ""))
        print("시장:", article.get("market", ""))
        print("날짜:", article.get("published_at", ""))
        print("점수:", score)
        print("판정이유:", reasons)

print()
print(f"검토 대상 기사 수: {review_count}")
print("=" * 70)

live_events = merge_same_events(news)

print(
    f"중복 제거 후 실제 사건 수: "
    f"{len(live_events)}"
)

print("\n===== 실전 사건 TOP20 =====")

for i, event in enumerate(live_events[:20], 1):

    print(
        f"{i:02d}. "
        f"[{event['market']}] "
        f"{event['event_score']}점 "
        f"{event['event_title']}"
    )

    print(
        f"    출처 수: "
        f"{event['source_count']}"
    )

    print(
        f"    EVENT KEY: "
        f"{event['event_key']}"
    )

    print(
        f"    이유: "
        f"{event['reason']}"
    )

print("\n" + "=" * 70)
print("실전 테스트 종료")
print("=" * 70)
