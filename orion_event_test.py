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
        
    {
        "id": 32,
        "title": '벡트 "LED 디스플레이 매출 증가세…하반기 수주 가속화"',
        "expected_event": False,
        "expected_type": "NO_EVENT",
        "note": "매출 증가세·향후 수주 전망일 뿐 확정 실적/신규 수주 사건 아님"
    },

    {
        "id": 33,
        "title": "Amazon.com vs. e.l.f. Beauty: Which High-Growth Consumer Stock Is a Better Investment in 2026?",
        "expected_event": False,
        "expected_type": "NO_EVENT",
        "note": "종목 비교·투자 아이디어이며 기업의 실제 CAPEX가 아님"
    },

    {
        "id": 34,
        "title": "코스피, 한은 2연속 기준금리 인상에 장중 상승폭 축소",
        "expected_event": False,
        "expected_type": "NO_EVENT",
        "note": "한국은행 금리 결정 및 시장반응 기사이며 미국 FOMC 사건이 아님"
    },
    {
        "id": 35,
        "title": "화장품 매출 비중 쑥…저점 대비 67% 반등한 파마리서치",
        "expected_event": False,
        "expected_type": "NO_EVENT",
        "note": "매출 비중과 주가 반등 기사이며 실제 기업 실적 발표가 아님"
    },

    {
        "id": 36,
        "title": "\"3개년 순이익 50% 주주환원\" 동원수산 '기업가치 제고 계획' 공시",
        "expected_event": False,
        "expected_type": "NO_EVENT",
        "note": "순이익의 주주환원 비율을 말한 것이며 실제 실적 발표가 아님"
    },

    {
        "id": 37,
        "title": "The Biggest Risk Facing Tesla Stock Right Now",
        "summary": "Tesla is pouring billions into investment, but what happens if these bets pay off later than expected?",
        "expected_event": False,
        "expected_type": "NO_EVENT",
        "note": "기존 투자에 대한 위험 분석 기사이며 신규 CAPEX 발표가 아님"
    },

    {
        "id": 38,

        "title": "美 금리 인상 우려 '쑥'…'칠천피' 탈환 시험대[주간증시전망]",

        "summary": "7000선 문턱에서 주춤한 코스피가 이번 주 케빈 워시 미국 연방준비제도(Fed·연준) 의장의 매파적 발언을 처음 소화한다. 워시 의장이 잭슨홀 회의에서 인플레이션에 대한 강한 경계감을 드러내면서 미국의 9월 기준금리 인상 가능성이 급부상한 가운데 미국 고용·제조업 지표도 줄줄이 예정돼 있다.",

        "expected_event": False,

        "expected_type": "NO_EVENT",

        "note": "연준 관련 기사지만 금리 인상 가능성·전망이며 실제 금리 결정이 아님"
    },

    {
        "id": 39,
        "title": "中 CXMT 매출 10배 폭증…삼성·SK 기술 추격 잰걸음",
        "summary": "기업공개로 확보한 자금과 현금을 더해 생산능력 확대와 첨단 D램 개발에 속도가 붙을 전망이다.",
        "expected_event": False,
        "expected_type": "NO_EVENT",
        "note": "향후 생산능력 확대 전망이지 신규 증설 또는 CAPEX 결정 발표가 아님"
    },

    {
        "id": 40,
        "title": "CrowdStrike Just Lit a Fire Under Cybersecurity Stocks. Is Palo Alto Networks Next?",
        "summary": "CrowdStrike just posted its best quarter ever and sent cybersecurity stocks surging, but history shows Palo Alto Networks has a nasty habit of falling on strong earnings reports, and the buy side has already baked in a beat.",
        "expected_event": False,
        "expected_type": "NO_EVENT",
        "note": "실제 CrowdStrike 실적을 언급하지만 후속 시장반응 기사이므로 PRIMARY_EVENT는 아님"
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
            "summary": case.get("summary", "")
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

    if score >= 95:
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
reject_candidates = []

for article in news:

    score, reasons = calc_event_score(article)

    # =====================================================
    # 실제 사건으로 통과한 기사
    # =====================================================

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

    # =====================================================
    # NO_EVENT로 버려진 기사 중
    # 실제 사건을 놓쳤을 가능성이 있는 기사 수집
    #
    # 목적:
    # 오탐(False Positive)뿐 아니라
    # 미탐(False Negative)도 확인한다.
    # =====================================================

    else:

        result = understand_event(article)

        title = str(
            article.get("title", "") or ""
        ).lower()

        summary = str(
            article.get("summary", "") or ""
        ).lower()

        text = f"{title} {summary}"

        # -------------------------------------------------
        # 사건 냄새가 강한 단어
        #
        # 여기서는 실제 사건으로 판정하지 않는다.
        # 단지 사람이 확인할 후보만 뽑는다.
        # -------------------------------------------------

        suspicious_words = [

            # 실적
            "revenue",
            "profit",
            "earnings",
            "guidance",
            "매출",
            "영업이익",
            "순이익",
            "실적",

            # 투자 / CAPEX
            "invest",
            "investment",
            "capex",
            "factory",
            "plant",
            "production",
            "투자",
            "증설",
            "공장",
            "생산능력",

            # 계약 / 수주
            "contract",
            "agreement",
            "order",
            "backlog",
            "supply",
            "계약",
            "수주",
            "공급",

            # M&A
            "acquire",
            "acquisition",
            "merger",
            "인수",
            "합병",

            # 정책 / FOMC
            "federal reserve",
            "fomc",
            "tariff",
            "sanction",
            "export restriction",
            "연준",
            "금리",
            "관세",
            "수출 제한",
            "수출 규제",
        ]

        matched_words = []

        for word in suspicious_words:

            if word in text:
                matched_words.append(word)

        if matched_words:

            reject_candidates.append(
                {
                    "article": article,
                    "result": result,
                    "matched_words": matched_words,
                }
            )


print()
print(f"검토 대상 기사 수: {review_count}")
print("=" * 70)


# =========================================================
# REJECT REVIEW
#
# NO_EVENT 처리됐지만 사건 관련 단어가 존재하는 기사
# → 미탐 여부 확인용
# =========================================================

print("\n===== ORION REJECT REVIEW =====")

# 너무 많은 기사가 출력되지 않도록
# 우선 최대 30개만 사람이 확인한다.
reject_candidates = reject_candidates[:30]

if not reject_candidates:

    print("의심되는 미탐 후보 없음")

else:

    for i, item in enumerate(
        reject_candidates,
        1
    ):

        article = item["article"]
        result = item["result"]

        print()
        print(f"[REJECT {i:02d}]")

        print(
            "제목:",
            article.get("title", "")
        )

        print(
            "요약:",
            article.get("summary", "")
        )

        print(
            "출처:",
            article.get("source", "")
        )

        print(
            "시장:",
            article.get("market", "")
        )

        print(
            "날짜:",
            article.get("published_at", "")
        )

        print(
            "NO_EVENT 이유:",
            result.get("reason", "")
        )

        print(
            "감지 단어:",
            item["matched_words"]
        )


print()
print(
    f"미탐 검토 후보 수: "
    f"{len(reject_candidates)}"
)

print("=" * 70)


# =========================================================
# 실제 사건 병합
# =========================================================

live_events = merge_same_events(news)

print(
    f"중복 제거 후 실제 사건 수: "
    f"{len(live_events)}"
)

print("\n===== 실전 사건 TOP20 =====")

for i, event in enumerate(
    live_events[:20],
    1
):

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
