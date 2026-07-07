def pass_theme_sector_filter(theme_name, stock, company):
    name = stock.get("name", "")
    sector = stock.get("sector", "")
    matched_text = str(company.get("matched", {}))

    text = name + " " + sector + " " + matched_text

    if theme_name == "AI":
        allow_words = [
            "반도체", "HBM", "메모리", "서버", "GPU",
            "데이터센터", "전력", "전기", "전자",
            "소프트웨어", "보안", "네트워크",
            "장비", "부품", "PCB", "MLCC", "냉각"
        ]

        block_words = [
            "화장품", "뷰티", "피부", "미용",
            "패션", "의류", "식품", "음료",
            "엔터", "광고", "유통"
        ]

        if any(word in text for word in block_words):
            return False, "AI 테마 부적합 업종"

        if not any(word in text for word in allow_words):
            return False, "AI 테마 핵심 업종 아님"

    return True, ""
