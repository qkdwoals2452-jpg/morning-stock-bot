def get_news_impact_score(stock, theme, articles, company):
    stock_name = stock.get("name", "")

    article_text = ""

    for article in articles:
        article_text += " " + article.get("title", "")
        article_text += " " + article.get("summary", "")

    article_text = article_text.lower()

    matched = company.get("matched", {})

    company_words = []

    for words in matched.values():
        company_words.extend(words)

    company_words = list(set(company_words))

    direct_matched = []

    STOP_WORDS = {
    "AI",
    "인공지능",
    "반도체",
    "공급",
    "투자",
    "계약",
    "장비"
   }

   for word in company_words:
       if not word:
           continue

       # 공통 키워드는 직접 수혜 판단에서 제외
       if word in STOP_WORDS:
           continue

       if word.lower() in article_text:
           direct_matched.append(word)
    score = 0

    if stock_name and stock_name.lower() in article_text:
        score += 60

    score += min(len(direct_matched) * 10, 40)

    if score >= 60:
        memo = "뉴스 직접 수혜 가능성 높음"
    elif score >= 30:
        memo = "뉴스 간접 수혜 가능성"
    else:
        memo = "뉴스와 직접 연결 약함"

    return {
        "score": score,
        "memo": memo,
        "matched": direct_matched[:10],
        "exclude": score < 20,
        "exclude_reason": "기사와 기업의 직접 연결 근거 부족"
    }
