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
]


if __name__ == "__main__":

    print("=" * 60)
    print("ORION EVENT TEST SET v1")
    print("=" * 60)

    real_events = sum(
        1 for case in TEST_CASES
        if case["expected_event"]
    )

    rejected = len(TEST_CASES) - real_events

    print("전체 테스트 :", len(TEST_CASES))
    print("잡아야 할 사건 :", real_events)
    print("버려야 할 기사 :", rejected)

    print("\n정답지 생성 완료")
    print("다음 단계: 새 Event Engine을 이 정답지에 연결")
