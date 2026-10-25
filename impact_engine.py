import re
from event_understanding_engine import understand_event
from company_identity_engine import COMPANY_ALIASES, has_company_mention, joint_subject_end


def assess_company_event_relation(stock, articles):
    """기사 원문에서 확인한 사건 당사자만 허용한다. 이익 수혜는 추정하지 않는다."""
    name = str(stock.get("name", "") or "").strip()
    if not name:
        return {"pass": False, "role": "UNVERIFIED", "evidence": [],
                "reason": "기업명 확인불가"}
    names = (name,) + COMPANY_ALIASES.get(name, ())
    boundary = r"(?<![가-힣A-Za-z0-9])(?:" + "|".join(re.escape(n) for n in names) + r")"
    # 원익을 원익IPS로, 이닉스를 SK하이닉스로 오인하지 않는다.
    boundary += r"(?=(?:은|는|이|가|와|과|에|의|으로부터|로부터)?(?:[^가-힣A-Za-z0-9]|$))"
    actor = re.compile(r"^\s*[\"“'‘]*" + boundary + r"(?:\s*[,，:]|(?:은|는|이|가)\s|\s+)", re.I)
    counterparty = re.compile(boundary + r"\s*(?:와|과|에게|에|으로부터|로부터)(?=\s)", re.I)
    matches = []
    for article in articles:
        if not understand_event(article).get("is_real_event"):
            continue
        # 기사 여러 개나 서로 다른 문장을 합쳐 관계를 만들어내지 않는다.
        for text in (article.get("title", ""), article.get("summary", "")):
            sentences = re.split(r"(?<=[.!?。])\s+|[\n;]", str(text or ""))
            # 제목의 말줄임표는 문장 종결이 아닐 수 있다. 전체 절과 각 절을 함께 확인한다.
            # '포스코DX, AI 승부수…인핸스에 투자'의 주체가 사라지지 않게 한다.
            clauses = [clause for sentence in sentences for clause in
                       ([sentence] + sentence.split("…") if "…" in sentence else [sentence])]
            for sentence in clauses:
                if not has_company_mention(name, sentence):
                    continue
                if re.search(r"지난해|작년|과거|\d+년\s*전|당시|previously|last year|전망|예상|기대|검토|분석|평가|목표주가|애널리스트|analyst|expects?|could|might|주가|급등|급락|수혜주|관련주|투자자\s*관심|부인|미체결|취소|불발|체결하지|denied|\bnot\b|\bnever\b", sentence, re.I):
                    continue
                event = understand_event({"title": sentence, "summary": ""})
                if not event.get("is_real_event"):
                    continue
                actor_match = actor.search(sentence)
                actor_end = actor_match.end() if actor_match else joint_subject_end(name, sentence)
                if actor_end is not None:
                    rest = sentence[actor_end:]
                    action = re.search(r"공급계약|계약|수주|투자|증설|인수|매출|영업이익|순이익|실적", rest)
                    prefix = rest[:action.start()] if action else rest
                    # 'GST, 엔비디아가 계약 체결'에서 GST를 계약 주체로 삼지 않는다.
                    if re.search(r"[가-힣A-Za-z0-9&.]+(?:은|는|이|가)\s", prefix):
                        actor_end = None
                counterparty_match = counterparty.search(sentence)
                if counterparty_match and re.match(r"(?:경쟁|무관|관련|관한|따르면)", sentence[counterparty_match.end():].lstrip()):
                    counterparty_match = None
                role = "EVENT_ACTOR" if actor_end is not None else "NAMED_COUNTERPARTY" if counterparty_match else None
                if role is None:
                    continue
                amounts = re.findall(r"(?:US\$|\$|€|₩)\s*[\d,.]+(?:\s*(?:million|billion|trillion))?|[\d,.]+\s*(?:조|억|만)\s*(?:원|달러)?", sentence, re.I)
                proof = {
                    "role": role, "event_type": event.get("event_type"),
                    "text": sentence.strip(), "source": article.get("source", ""),
                    "link": article.get("link", ""),
                    "published_at": article.get("published_at", ""),
                    "amount_text": [amount.strip() for amount in amounts],
                }
                if proof not in matches:
                    matches.append(proof)
    matches.sort(key=lambda p: p["role"] != "EVENT_ACTOR")
    return {
        "pass": bool(matches),
        "role": matches[0]["role"] if matches else "UNVERIFIED",
        "evidence": matches,
        "reason": "기사에 명시된 사건 당사자(매출 귀속·이익 효과는 별도 검증)" if matches else "기업명·키워드 언급만으로 사건 당사자 관계를 확인할 수 없음",
    }


GENERIC_WORDS = {
    "ai",
    "인공지능",
    "반도체",
    "공급",
    "투자",
    "계약",
    "장비",
    "부품",
    "소재",
    "사업",
    "고객",
    "수주",
    "생산",
    "공장",
    "서버",
    "데이터센터"
}


STRONG_WORDS = {
    "hbm",
    "hbm3",
    "hbm3e",
    "hbm4",
    "gpu",
    "cdu",
    "액침냉각",
    "수랭식",
    "liquid cooling",
    "cowos",
    "패키징",
    "유리기판",
    "실리콘포토닉스",
    "변압기",
    "전력기기",
    "ess",
    "낸드",
    "dram",
    "파운드리",
    "첨단패키징",
    "후공정",
    "테스트소켓",
    "프로브카드"
}


CUSTOMER_WORDS = {
    "nvidia",
    "엔비디아",
    "microsoft",
    "마이크로소프트",
    "amazon",
    "아마존",
    "google",
    "구글",
    "meta",
    "메타",
    "openai",
    "tesla",
    "테슬라",
    "tsmc",
    "micron",
    "마이크론",
    "broadcom",
    "브로드컴"
}


def normalize_text(text):
    text = str(text or "").lower()
    text = re.sub(r"\s+", " ", text)
    return text


def flatten_company_words(company):
    matched = company.get("matched", {})

    words = []

    for value in matched.values():
        if isinstance(value, list):
            words.extend(value)

    cleaned = []

    for word in words:
        word_low = normalize_text(word).strip()

        if not word_low:
            continue

        if word_low in GENERIC_WORDS:
            continue

        cleaned.append(word_low)

    return list(set(cleaned))


def get_news_impact_score(stock, theme, articles, company):
    relation = assess_company_event_relation(stock, articles)
    stock_name = normalize_text(stock.get("name", ""))
    stock_code = normalize_text(stock.get("code", ""))

    article_text_parts = []

    for article in articles:
        article_text_parts.append(article.get("title", ""))
        article_text_parts.append(article.get("summary", ""))

    article_text = normalize_text(" ".join(article_text_parts))

    company_words = flatten_company_words(company)

    direct_matched = []
    strong_matched = []
    customer_matched = []

    for word in company_words:
        if word in article_text:
            direct_matched.append(word)

            if word in STRONG_WORDS:
                strong_matched.append(word)

            if word in CUSTOMER_WORDS:
                customer_matched.append(word)

    score = 0
    reasons = []

    # 1. 회사명이 기사에 직접 등장
    if relation["pass"] or (stock_name and stock_name in article_text):
        score += 70
        reasons.append("기사의 사건 당사자 기업명 확인" if relation["pass"] else "기사에 회사명 언급(사건 관계 미확인)")

    # 2. 종목코드가 기사에 등장
    if stock_code and stock_code in article_text:
        score += 20
        reasons.append("기사에 종목코드 등장")

    # 3. 구체적인 제품·기술 키워드
    if strong_matched:
        strong_score = min(len(set(strong_matched)) * 15, 45)
        score += strong_score
        reasons.append(
            "구체 기술 일치: " + ", ".join(sorted(set(strong_matched))[:5])
        )

    # 4. 고객사·글로벌 기업 연결
    if customer_matched:
        customer_score = min(len(set(customer_matched)) * 10, 20)
        score += customer_score
        reasons.append(
            "글로벌 기업명 일치(거래관계는 별도 검증): " + ", ".join(sorted(set(customer_matched))[:3])
        )

    # 5. 일반 직접 매칭은 낮은 점수만 부여
    other_matched = [
        word
        for word in direct_matched
        if word not in strong_matched
        and word not in customer_matched
    ]

    if other_matched:
        other_score = min(len(set(other_matched)) * 3, 15)
        score += other_score
        reasons.append(
            "사업 키워드 일부 일치: "
            + ", ".join(sorted(set(other_matched))[:5])
        )

    score = min(score, 100)
    raw_score = score
    if not relation["pass"]:
        score = 0

    if score >= 70:
        memo = "뉴스 사건 당사자 연결 확인(이익 효과 미확인)"
    elif score >= 40:
        memo = "뉴스 수혜 연결 가능성 있음"
    elif score >= 20:
        memo = "뉴스 간접 관련"
    else:
        memo = "뉴스와 직접 연결 약함"

    exclude = score < 20

    return {
        "score": score,
        "raw_score": raw_score,
        "event_connection": relation,
        "memo": memo,
        "matched": sorted(set(direct_matched))[:10],
        "strong_matched": sorted(set(strong_matched))[:10],
        "customer_matched": sorted(set(customer_matched))[:10],
        "reasons": reasons,
        "exclude": exclude,
        "exclude_reason": (
            relation["reason"] if not relation["pass"] else "기사와 기업의 직접 연결 근거 부족"
            if exclude
            else ""
        )
    }
