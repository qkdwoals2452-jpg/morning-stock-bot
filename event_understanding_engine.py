import re
import os

_LOGGED_ARTICLE_ROLES = set()


# ---------------------------------------------------------
# ORION Event Understanding Engine v1
#
# 목적:
# 단순히 AI, 투자, 반도체 같은 단어가 있다고 사건으로 만들지 않는다.
#
# 반드시
# "실제로 무엇인가 발생했는가?"
# 를 먼저 판단한다.
# ---------------------------------------------------------


def normalize_text(text):
    return re.sub(
        r"\s+",
        " ",
        str(text or "").lower()
    ).strip()


def contains_any(text, patterns):
    return any(
        pattern.lower() in text
        for pattern in patterns
    )

def has_signed_acquisition_agreement(text):
    """체결된 기업 인수 계약. 일반 물품 구매 및 거래 종결과 구별한다."""
    for sentence in re.split(r"(?<=[.!?。])\s+|[\n;]", normalize_text(text)):
        if has_unconfirmed_transaction(sentence):
            continue
        match = re.search(
            r"\b(?:signed|signs|entered into|enters into)\s+"
            r"(?:(?:a|an|the|definitive|binding)\s+){0,3}"
            r"(?P<kind>(?:(?:merger|acquisition)\s+)?)"
            r"(?:agreement|deal)\s+to\s+(?:buy|acquire)\s+(?P<target>.{1,240})",
            sentence,
        )
        if not match:
            continue
        # 'buy electricity from a power company'의 판매자를 인수 대상으로 빌리지 않는다.
        target = re.split(r"\b(?:for|from|with|to|and|as)\b", match['target'])[0]
        corporate_target = re.search(
            r"\b(?:compan(?:y|ies)|startups?|firms?|makers?|shares|stake)\b"
            r"|\bbusiness(?:\s+unit)?\s*[,.]?$", target,
        )
        transaction_terms = re.search(r"\bincluding debt\b|\bshareholders?\b", match['target'])
        if match['kind'] or corporate_target or transaction_terms:
            return True
    return False


def has_speculative_context(text):
    """
    실제 확정 사건이 아니라
    전망·가능성·우려·가정·분석 문맥인지 판별
    """

    speculative_patterns = [
        # 한국어
        "가능성",
        "가능성이",
        "전망이다",
        "전망된다",
        "전망",
        "예상된다",
        "예상",
        "우려",
        "기대된다",
        "기대",
        "관측",
        "될 수",
        "할 수",
        "주간증시전망",

        # 영어
        "could",
        "may ",
        "might",
        "potential",
        "possibly",
        "expected to",
        "could happen",
        "what happens if",
    ]

    return contains_any(
        text,
        speculative_patterns
    )


def is_analysis_article(title):
    """
    새로운 사건 발표가 아니라
    분석·전망·시장반응·해설 성격의 기사인지 판별한다.

    핵심 원칙:
    사건 관련 단어가 포함되어 있어도
    기사 자체의 목적이 '새 사건 발표'가 아니면
    Event Engine으로 내려보내지 않는다.
    """

    title = normalize_text(title)

    # =====================================================
    # 1. 투자 분석 / 전망
    # =====================================================

    analysis_patterns = [
        "biggest risk",
        "risk facing",
        "what happens if",
        "is it a buy",
        "should you buy",
        "prediction:",
        "what to do now",
        "outlook",

        "투자의견",
        "목표주가",
        "주간증시전망",
        "증시전망",
    ]

    if contains_any(title, analysis_patterns):
        return True

    # =====================================================
    # 2. 시장·주가 반응 기사
    #
    # 기업의 새로운 행동이 아니라
    # 이미 존재하는 재료에 주가가 반응한 기사
    # =====================================================

    market_reaction_patterns = [
        "[특징주]",
        "특징주]",
        "[종목",
        "급등",
        "급락",
        "상한가",
        "하한가",
    ]

    if contains_any(title, market_reaction_patterns):
        return True

    # 퍼센트 주가 움직임 표현
    # 예: 12%대↑ / 8%↓ / 15% 상승
    if re.search(
        r"\d+(?:\.\d+)?\s*%[^가-힣A-Za-z0-9]{0,5}"
        r"(↑|↓|상승|하락|급등|급락)",
        title
    ):
        return True

    # =====================================================
    # 3. 비교 / 해설형 제목
    # =====================================================

    explainer_patterns = [
        "comparing",
        "comparison",
        "what it means",
        "here's why",
        "here’s why",
    ]

    if contains_any(title, explainer_patterns):
        return True

    return False
    
def has_unconfirmed_transaction(text):
    """협상·미체결·비구속 약정·미확인 보도를 확정 거래로 승격하지 않는다.

    문장 단위의 보수적 필터다. 다른 문장의 계약으로 이 문장의 거래를
    확정하거나, 익명 보도를 허위라고 판정하는 기능은 아니다.
    """
    text = normalize_text(text)
    transaction = r"(?:invest\w*|acquir\w*|acquisition|merger|buy|contract|agreement|deal|factory|plant|투자|인수|합병|계약|수주|공장)"
    uncertainty = r"(?:in talks|negotiat\w*|considering|exploring|seeking|검토|협상|논의|미확정)"
    patterns = [
        rf"{uncertainty}.{{0,100}}{transaction}",
        rf"{transaction}.{{0,50}}{uncertainty}",
        # 'not only'는 추가 행동을 강조하는 표현이다. 별도의 not/denial은 계속 검사한다.
        rf"(?:\bnot\b(?!\s+only\b)|\b(?:never|denied|denies)\b).{{0,60}}{transaction}",
        r"\bsigned\s+no\s+(?:\w+\s+){0,3}(?:contract|agreement)\b",
        r"\b(?:expects? to|plans? to|seeks? to|aims? to|hopes? to|will|may|might|could)\s+sign\b.{0,80}\b(?:contract|agreement|deal)\b",
        r"(?:계약|투자|인수|수주).{0,30}(?:체결하지|확정되지|사실무근|부인|체결\s*예정)",
        # 계약 체결 '의향'만 제외한다. 체결 후 별도 증설/수주 목표를 빌리지 않는다.
        r"계약(?:을|를)?\s*(?:체결(?:을)?\s*(?:위한\s*)?)?"
        r"(?:추진|목표|협의\s*중)",
        rf"(?:memorandum of understanding|letter of intent|non.binding|\bmou\b|양해각서).{{0,100}}{transaction}",
        rf"{transaction}.{{0,100}}(?:memorandum of understanding|letter of intent|non.binding|\bmou\b|양해각서)",
        rf"(?:reportedly|sources? say|according to sources).{{0,120}}{transaction}",
        rf"{transaction}.{{0,160}}(?:reportedly|sources? say|according to sources)",
    ]
    return any(
        re.search(pattern, sentence)
        for sentence in re.split(r"(?<=[.!?。])\s+|;", text)
        for pattern in patterns
    )


def has_contract_cancellation_context(text):
    """계약 해소 문맥은 신규 수주로 승격하지 않는다. 확정성 판정은 별개다."""
    text = normalize_text(text)
    patterns = [
        r'(?:계약|협약|수주|발주).{0,12}(?:해제|해지|취소|철회|파기)'
        r'(?!\s*(?:조건|조항|없이|하지|되지))',
        r'\b(?:cancels?|cancelled|canceled|cancelling|canceling|terminates?|terminated|'
        r'terminating|rescinds?|rescinded)\b.{0,60}\b(?:contracts?|agreements?|orders?)\b',
        r'\b(?:contracts?|agreements?|orders?)\b.{0,40}\b(?:cancelled|canceled|terminated|rescinded)\b',
        r'\b(?:cancellation|termination|rescission) of\b.{0,40}\b(?:contracts?|agreements?|orders?)\b',
    ]
    return any(re.search(pattern, sentence)
               for sentence in re.split(r'(?<=[.!?。])\s+|[;…]|\.{2,}|(?<!\d),(?!\d)', text)
               for pattern in patterns)


def has_investment_cancellation_context(text):
    """취소·철회된 투자/증설을 신규 CAPEX 수혜 근거로 사용하지 않는다.

    계약 취소와 별도 역할로 남긴다. 쉼표/문장 경계를 넘어 다른 행동의
    취소를 빌리지 않으며, 부정적 사건 자체를 허위라고 판단하지 않는다.
    """
    text = normalize_text(text)
    investment = r'\b(?:invest(?:ment|ments)?|capex|capital spending|new (?:plant|factory)|factory expansion)\b'
    reversal = r'\b(?:cancels?|cancelled|canceled|abandons?|abandoned|scraps?|scrapped|shelves?|shelved)\b'
    # 다른 행동/대상을 거쳐 투자 명사를 연결하지 않는다.
    gap = r'(?:(?!\b(?:announces?|signs?|concert|conference|ceremony)\b).){0,80}'
    korean_investment = r'(?:투자|공장\s*(?:신설|증설)|생산시설\s*증설)'
    korean_reversal = r'(?:취소|철회|백지화|중단)(?!\s*(?:조건|조항|없이|하지|되지))'
    patterns = [
        reversal + gap + investment,
        investment + gap + r'\b(?:cancelled|canceled|abandoned|scrapped|shelved)\b',
        r'\b(?:cancellation|abandonment) of\b' + gap + investment,
        korean_investment + r'.{0,25}' + korean_reversal,
        r'(?:취소한|철회한|백지화한|중단한)\s*.{0,20}' + korean_investment,
    ]
    return any(re.search(pattern, clause)
               for clause in re.split(r'(?<=[.!?。])\s+|[;…]|\.{2,}|(?<!\d),(?!\d)', text)
               for pattern in patterns)


def has_direct_us_rate_decision_title(title):
    """요약의 배경 언급을 빌리지 않고 제목에 직접 드러난 미국 금리 결정만 허용."""
    title = normalize_text(title)
    title = re.sub(r'^(?:\[(?:속보|breaking)\]\s*|breaking\s*:\s*)', '', title)
    if '?' in title or has_speculative_context(title) or re.search(
        r'\b(?:expects?|expected|predicts?|bets?|previously|last year|last month|'
        r'not|never|denies|denied|didn.t|won.t|would|if)\b|지난|과거|하지 않|안 했|부인|철회|취소', title
    ):
        return False
    english = re.search(
        r'^(?:the\s+)?(?:federal reserve|fed|fomc)\s+(?:has\s+)?'
        r'(?:cuts?\s+(?:interest\s+)?rates\b|raises?\s+(?:interest\s+)?rates\b|'
        r'(?:holds?|keeps?)\s+(?:interest\s+)?rates\s+(?:steady|unchanged)\b)', title
    )
    korean = re.search(
        r'^(?:(?:미국|美|미)\s*,?\s*|(?:(?:미국|미)\s*)?'
        r'(?:연준|연방준비제도|fomc)(?:은|이)?\s*,?\s*)'
        r'(?:기준)?금리\s*(?:를\s*)?(?:[0-9.,%pＰ포인트]+\s*)?'
        r'(?:인하|인상|동결)(?:\b|했다|한다|결정|을|에|…|·|,|$)', title
    )
    return bool(english or korean)


def has_direct_policy_action_title(title):
    """정책 명사·배경 설명 대신 제목의 실제 발표/시행 행동을 요구한다."""
    title = normalize_text(title)
    if not title or '?' in title or '？' in title:
        return False
    if re.search(
        r"\b(?:no sign of|no signs of|not|never|denies?|denied|may|might|could|would|"
        r"considering|expected to|plans? to|threatens? to|last year|previously)\b|"
        r"징후\s*없|부과하지|시행하지|검토|가능성|전망|예정|지난해|작년|여부", title
    ):
        return False
    policy = r"(?:tariffs?|export (?:restrictions?|ban)|sanctions?)"
    action = r"(?:imposes?|imposed|announces?|announced|raises?|raised|cuts?|cut|"
    action += r"implements?|implemented|enacts?|enacted|lifts?|lifted)"
    return bool(
        re.search(r"\b" + action + r"\b.{0,60}\b" + policy + r"\b", title)
        or re.search(r"\b" + policy + r"\b.{0,35}\b(?:takes? effect|took effect|"
                     r"comes? into force|came into force|is imposed|are imposed)\b", title)
        or re.search(r"(?:관세|수출\s*(?:규제|제한|금지)|제재).{0,25}"
                     r"(?:부과|인상|인하|발표|시행|발효|해제|철회)", title)
    )


def earnings_context_without_benchmark(title):
    """실적 제목에서 결과 비교인 '예상 상회/하회'만 전망 검사에서 분리.

    원문·숫자는 바꾸지 않으며, 전망/가능성/예상 발표 등 다른 미래 표현은
    그대로 둔다. '예상 상회할'처럼 미래형으로 이어지는 표현도 지우지 않는다.
    """
    title = normalize_text(title)
    if not (re.search(r'(?:[1-4]분기|상반기|하반기|연간|(?:1[0-2]|[1-9])월)', title)
            and re.search(r'매출|영업이익|순이익|순익|실적', title)):
        return title
    return re.sub(
        r'(?:시장\s*)?예상(?:치)?(?:를|을)?\s*(?:크게\s*)?'
        r'(?:(?:상회|하회)(?:했다|해|한)?|웃돌았다|밑돌았다|웃돌아|밑돌아)(?![가-힣])',
        '실적 비교', title)


def classify_article_role(title, summary=""):
    """
    기사 자체의 역할을 먼저 판별한다.

    반환값:
    EVENT_CANDIDATE (아직 실제 사건으로 확정한 것이 아님)
    ANALYSIS
    OUTLOOK
    MARKET_REACTION
    EXPLAINER
    LIFESTYLE
    UNCONFIRMED_TRANSACTION
    CONTRACT_CANCELLATION_CONTEXT
    INVESTMENT_CANCELLATION_CONTEXT
    """

    title = normalize_text(title)
    summary = normalize_text(summary)
    text = f"{title} {summary}".strip()

    # 투자 목록·매수 조언은 본문에 관련 기업이 등장해도 사건 기사가 아니다.
    recommendation_patterns = [
        r"\bstocks?\s+to\s+(?:buy|own|watch)\b",
        r"\b(?:stocks?|etfs?)\b.*\b(?:worth owning|worth buying|to own)\b",
        r"\bshould you(?: really)? buy\b",
        r"\bhow to invest\b",
        r"\b(?:best|top|unique)\s+etfs?\b.*\b(?:momentum|buy|own)\b",
        r"추천주|매수 추천|주목할 종목|투자 포인트|사야 할까|살까",
        r"(?:은행\s*)?예금보다\s*(?:낫|좋)",
        r"배당\s*쏠쏠|배당.{0,12}(?:매력적인|매력적|챙길\s*종목)",
    ]
    if any(re.search(pattern, title) for pattern in recommendation_patterns):
        return "ANALYSIS"

    # 주가에 대한 위험·장애물 의견은 요약의 과거 실적·계약으로 되살리지 않는다.
    # 위험 단어만 보지 않고 의견 동사 + 위험 대상이 주가인 제목에 한정한다.
    if re.search(
        r"\b(?:sees?|warns? of|flags?|highlights?)\s+"
        r"(?:(?:a|an|new|fresh|another|major|growing|more)\s+){0,3}"
        r"(?:hurdles?|headwinds?|risks?|challenges?)\s+(?:for|to|facing)\b"
        r".{0,100}\b(?:stocks?|shares|share price)\b",
        title,
    ):
        return "ANALYSIS"

    # 실적 수치 자체의 발표와, 실적이 주가에 미칠 영향을 설명하는 글을 구분한다.
    # ANALYSIS는 요약 속 실적 키워드로 확정 사건 예외를 적용하지 않는다.
    if re.search(
        r"^how\b.{0,100}\b(?:earnings|results|revenue|profit)\b"
        r".{0,80}\b(?:impact|affect)\b.{0,80}\b(?:stock|shares|share price)\b",
        title,
    ):
        return "ANALYSIS"

    if has_contract_cancellation_context(title) or has_contract_cancellation_context(summary):
        return "CONTRACT_CANCELLATION_CONTEXT"

    if has_investment_cancellation_context(title) or has_investment_cancellation_context(summary):
        return "INVESTMENT_CANCELLATION_CONTEXT"

    # 제목 또는 요약의 미확정 거래를 후단의 단순 거래 키워드로 되살리지 않는다.
    if has_unconfirmed_transaction(title) or has_unconfirmed_transaction(summary):
        return "UNCONFIRMED_TRANSACTION"

    lifestyle_patterns = [
        r"먹는\s*법|데우는\s*법|요리\s*방법|요리\s*레시피",
        r"\bhow to (?:cook|reheat|wash|clean)\b",
        r"\b(?:hottest|favorite|popular)\b.*\bmovie genre\b",
    ]
    if any(re.search(pattern, title) for pattern in lifestyle_patterns):
        return "LIFESTYLE"

    # =====================================================
    # 1. 시장·주가 반응 기사
    # =====================================================

    market_reaction_patterns = [
        "[특징주]",
        "특징주]",
        "[종목",
        "급등",
        "급락",
        "상한가",
        "하한가",
        "stock surging",
        "stock plunging",
        "stock tumbling",
        "stock sliding",
        "stocks lower at close",
        "stocks higher at close",
    ]

    if contains_any(title, market_reaction_patterns):
        return "MARKET_REACTION"

    price_context = contains_any(
        title,
        [
            "주가",
            "주식",
            "stock",
            "shares",
            "share price",
        ]
    )

    percent_move = re.search(
        r"\d+(?:\.\d+)?\s*%[^가-힣A-Za-z0-9]{0,5}"
        r"(↑|↓|상승|하락|급등|급락)",
        title
    )

    english_move = re.search(r"\b(?:stocks?|shares)\s+(?:rises?|falls?|gains?|drops?|jumps?|slumps?)\b", title)
    if (price_context and percent_move) or english_move:
        return "MARKET_REACTION"
    # =====================================================
    # 2. 전망 / 기대 / 가능성 기사
    # 실제 기업 행동과 구별
    # =====================================================

    outlook_patterns = [
        "expected to",
        "likely to",
        "could",
        "might",
        "possibly",
        "potential",
        "전망",
        "예상",
        "가능성",
        "기대",
        "관측",
        "dow jones futures",
        "earnings preview",
        "달릴까",
        "오를까",
    ]

    if contains_any(earnings_context_without_benchmark(title), outlook_patterns):
        return "OUTLOOK"

    # =====================================================
    # 3. 비교 / 분석 기사
    # =====================================================

    analysis_patterns = [
        "comparing",
        "comparison",
        " vs. ",
        " vs ",
        "biggest risk",
        "risk facing",
        "is it a buy",
        "should you buy",
        "want to invest in",
        "how to invest in",
        "before its ipo",
        "what to do now",
        "valuation",
        "price target",
        "투자의견",
        "목표주가",
        "주간증시전망",
        "증시전망",
        "history says",
        "history suggests",
        "street calls of the week",
    ]

    if contains_any(title, analysis_patterns):
        return "ANALYSIS"

    # =====================================================
    # 4. 설명 / 해설 기사
    # =====================================================

    explainer_patterns = [
        "what it means",
        "here's why",
        "here’s why",
        "이유",
        "왜 ",
        "왜?",
        "의미",
        "필요성",
        "answer for why",
    ]

    if contains_any(title, explainer_patterns):
        return "EXPLAINER"

    return "EVENT_CANDIDATE"
def has_confirmed_event_inside_reaction(title, summary=""):
    """
    주가반응·전망·해설 기사라도 기사 내부에
    신규 확정 사건의 강한 근거가 있는지 확인한다.

    단순 '소식', '재평가', 과거 사건 언급은 살리지 않는다.
    """

    title = normalize_text(title)
    summary = normalize_text(summary)

    # 핵심:
    # 시장반응 제목 자체가 아니라 summary에서
    # 독립적인 확정 사건 근거를 우선 확인한다.
    evidence_text = summary

    if not evidence_text:
        return False

    # 단순 계약 단어 대신 실제 체결·결정 행동을 확인한다.
    action_patterns = [
        r"\b(?:signed|signs|executed|entered into|enters into)\b.{0,100}\b(?:contract|agreement)\b",
        r"\b(?:agrees? to acquire|agreed to acquire|completed acquisition|committed to invest)\b",
        r"\b(?:announces?|announced)\b.{0,80}\binvestment\b",
        r"\b(?:beat|beats|reported|reports)\b.{0,100}\b(?:estimates|revenue|earnings|results)\b",
        r"(?:공급\s*계약|본계약|계약).{0,30}(?:체결|확정)",
        r"(?:투자|증설|인수).{0,10}(?:결정|확정|완료)",
    ]
    for sentence in re.split(r"(?<=[.!?。])\s+|[\n;]", evidence_text):
        if (has_contract_cancellation_context(sentence)
                or has_investment_cancellation_context(sentence)):
            continue
        if has_unconfirmed_transaction(sentence):
            continue
        if re.search(r"last year|previously|지난해|작년|과거|memorandum of understanding|non.binding|\bmou\b", sentence):
            continue
        for pattern in action_patterns:
            for match in re.finditer(pattern, sentence):
                before = sentence[max(0, match.start() - 35):match.start()]
                after = sentence[match.end():match.end() + 12]
                if re.search(r"\bnot\b(?!\s+only\b)|\b(?:never|denied|denies|if|expected to|expects? to|plans? to|could|might|may)\b", before):
                    continue
                if re.search(r"\bno\s+(?:\w+\s+){0,3}(?:contract|agreement)\b", match.group()):
                    continue
                if re.search(r"\b(?:will|would)\s+(?:\w+\s+){0,2}$", before):
                    continue
                if re.search(r"예정|검토|미확정|가능성|하지 않|하지 않았|여부", after):
                    continue
                return True
    return False
def assess_event_evidence(article, event_info):
    """
    실제 사건 판정 이후
    그 사건을 뒷받침하는 근거의 강도를 평가한다.

    STRONG:
        계약 체결, 확정 수주, 투자 결정,
        공장 신설, 실제 실적 숫자,
        확정 M&A/정책 결정 등

    MEDIUM:
        실제 행동 가능성은 높지만
        표현이 상대적으로 약하거나 계획/약정 중심

    WEAK:
        사건 근거가 부족함
    """

    title = normalize_text(
        article.get("title", "")
    )

    summary = normalize_text(
        article.get("summary", "")
    )

    text = f"{title} {summary}".strip()

    event_type = event_info.get(
        "event_type",
        "NO_EVENT"
    )

    # 사건 자체가 아니면 근거도 없음
    if not event_info.get("is_real_event"):
        return {
            "evidence_strength": "WEAK",
            "evidence_reason": "실제 사건으로 확인되지 않음"
        }

    # =====================================================
    # CONTRACT
    # =====================================================

    if event_type == "CONTRACT":

        strong_contract = (
            contains_any(
                text,
                [
                    "signed contract",
                    "signs contract",
                    "won contract",
                    "wins contract",
                    "supply contract",
                    "supply agreement",
                    "entered into an agreement",
                    "enters into an agreement",
                    "공급계약",
                    "공급 계약",
                    "계약 체결",
                ]
            )
            or (
                "수주" in title
                and bool(
                    re.search(
                        r"\d[\d,.]*\s*"
                        r"(억|억원|조|조원|만원|원|척|대|개|건)",
                        title
                    )
                )
            )
        )

        if strong_contract:
            return {
                "evidence_strength": "STRONG",
                "evidence_reason": "계약 체결·확정 수주 근거 확인"
            }

        return {
            "evidence_strength": "MEDIUM",
            "evidence_reason": "계약 관련 행동은 확인되나 확정 근거 강도는 중간"
        }

    # =====================================================
    # CAPEX
    # =====================================================

    if event_type == "CAPEX":

        strong_capex = (
            contains_any(
                text,
                [
                    "announces investment",
                    "announced investment",
                    "commits",
                    "committed",
                    "new factory",
                    "new plant",
                    "공장 신설",
                    "공장 건설",
                    "투자 결정",
                    "투자 확정",
                    "설비투자",
                    "신규 구축",
                    "증설 결정",
                    "증설 착수",
                ]
            )
            or bool(
                re.search(
                    r"\d[\d,.]*\s*"
                    r"(억달러|만달러|달러|억원|억|조원|조)"
                    r".{0,30}"
                    r"(투자|신설|증설|구축)",
                    title
                )
            )
        )

        if strong_capex:
            return {
                "evidence_strength": "STRONG",
                "evidence_reason": "구체적 투자·시설 확정 근거 확인"
            }

        return {
            "evidence_strength": "MEDIUM",
            "evidence_reason": "투자 행동은 확인되나 확정 근거 강도는 중간"
        }

    # =====================================================
    # M&A
    # =====================================================

    if event_type == "M&A":

        strong_ma = contains_any(
            text,
            [
                "agrees to buy",
                "agreed to buy",
                "agrees to acquire",
                "agreed to acquire",
                "acquires",
                "acquired",
                "completed acquisition",
                "merger completed",
                "merger approved",
                "인수 완료",
                "인수 확정",
                "인수 계약",
                "합병 승인",
            ]
        )

        if strong_ma or has_signed_acquisition_agreement(title) or has_signed_acquisition_agreement(summary):
            return {
                "evidence_strength": "STRONG",
                "evidence_reason": "확정 인수·합병 근거 확인"
            }

        return {
            "evidence_strength": "MEDIUM",
            "evidence_reason": "M&A 행동은 확인됐으나 확정 표현 강도는 중간"
        }

    # =====================================================
    # EARNINGS
    # =====================================================

    if event_type == "EARNINGS":

        actual_number = bool(
            re.search(
                r"\d[\d,.]*\s*"
                r"(억|억원|조|조원|달러|%|퍼센트)",
                title
            )
        )

        actual_signal = contains_any(
            title,
            [
                "매출",
                "영업이익",
                "순이익",
                "흑자전환",
                "적자전환",
                "revenue",
                "profit",
                "earnings",
            ]
        )

        if actual_number and actual_signal:
            return {
                "evidence_strength": "STRONG",
                "evidence_reason": "실제 실적 수치·결과 확인"
            }

        return {
            "evidence_strength": "MEDIUM",
            "evidence_reason": "실적 변화는 확인됐으나 수치 근거는 제한적"
        }

    # =====================================================
    # 정책 / FOMC / 생산
    # =====================================================

    if event_type in [
        "FOMC",
        "POLICY",
        "PRODUCTION",
    ]:
        return {
            "evidence_strength": "STRONG",
            "evidence_reason": "확정 정책·생산 행동 확인"
        }

    return {
        "evidence_strength": "MEDIUM",
        "evidence_reason": "실제 사건이나 근거 강도 추가 확인 필요"
    }
def understand_event(article):

    title = normalize_text(
        article.get("title", "")
    )

    summary = normalize_text(
        article.get("summary", "")
    )

    text = f"{title} {summary}".strip()

    # =====================================================
    # 기사 역할 판별
    #
    # 새로운 사건 발표가 아닌
    # 위험분석·투자분석·시장전망 기사는 사건에서 제외
    # =====================================================

    article_role = classify_article_role(
        title,
        summary
    )
    if os.getenv("ORION_DEBUG_EVENT_ROLE") == "1":
        key = (title, summary, article_role)
        if key not in _LOGGED_ARTICLE_ROLES:
            print("DEBUG ARTICLE ROLE:", title, "=>", article_role)
            _LOGGED_ARTICLE_ROLES.add(key)
    if article_role == 'CONTRACT_CANCELLATION_CONTEXT':
        return {
            'is_real_event': False,
            'event_type': 'NO_EVENT',
            'article_role': article_role,
            'reason': '계약 해제·해지·취소 문맥이며 신규 계약·수주 근거가 아님',
        }
    
    
    confirmed_event_override = (
        article_role in {"MARKET_REACTION", "OUTLOOK", "EXPLAINER"}
        and has_confirmed_event_inside_reaction(title, summary)
    )
    if article_role not in {"EVENT", "EVENT_CANDIDATE"}:

        # -------------------------------------------------
        # 주가반응·전망·해설 혼합 기사 예외
        #
        # 제목은 주가반응 기사라도 summary 안에서
        # 독립적인 신규 확정 사건이 확인되면
        # 아래 Event 판정 로직까지 통과시킨다.
        # -------------------------------------------------

        if (
            confirmed_event_override
        ):
            pass

        else:
            return {
                "is_real_event": False,
                "event_type": "NO_EVENT",
                "article_role": article_role,
                "reason": f"{article_role} 성격의 기사이며 신규 확정 사건이 아님"
            }
    # =====================================================
    # 1. 명백한 비사건 콘텐츠
    # 가장 먼저 제거한다.
    # =====================================================

    no_event_patterns = [

        # 매수/추천
        "stocks to watch",
        "stocks to buy",
        "stock to buy",
        "better buy",
        "best stocks",
        "top stock",
        "stock pick",
        "should you buy",
        "worth buying",
        "we love",
        "investors are missing",

        # 투자 조언
        "urges investors",
        "for investors",
        "what investors need to know",
        "spread bets",
        "to consider",

        # 단순 주가 기사
        "why is",
        "why shares",
        "stock surging",
        "stock plunging",
        "stock tumbling",
        "stock sliding",
        "here's why",
        "here’s why",

        # 시장 프리뷰
        "dow jones futures",
        "data due",
        "set to report earnings",
        "earnings preview",

        # 밸류에이션/해설
        "forward earnings",
        "price target",
        "valuation",
        "times earnings",

        # 한국어
        "추천주",
        "주목할 종목",
        "매수 추천",
        "목표가",
        "투자 포인트",
        "살까",
        "사야 할까",
    ]

    
    if contains_any(text, no_event_patterns):

        if not confirmed_event_override:
            return {
                "is_real_event": False,
                "event_type": "NO_EVENT",
                "reason": "투자권유·해설·시장반응 콘텐츠"
            }
        

    # =========================================================
    # FOMC / FED 정책 이벤트
    # 반드시 미국 연준이 주체여야 함
    # =========================================================

    # -----------------------------------------------------
    # 한국어 미국 기준금리 실제 결정
    #
    # 예:
    # 美, 기준금리 0.25%p 인상
    # 미국, 기준금리 0.25%p 인하
    #
    # 전망·기대·우려는 여기서 잡지 않는다.
    # -----------------------------------------------------

    korean_us_rate_decision = (
        contains_any(
            title,
            [
                "美, 기준금리",
                "美 기준금리",
                "미국, 기준금리",
                "미국 기준금리",
                "미 연준, 기준금리",
                "연준, 기준금리",
            ]
        )
        and contains_any(
            title,
            [
                "인상",
                "인하",
                "동결",
            ]
        )
        and not contains_any(
            title,
            [
                "전망",
                "예상",
                "기대",
                "우려",
                "가능성",
                "관측",
                "검토",
                "인상 기대",
                "인하 기대",
            ]
        )
    )

    if korean_us_rate_decision and has_direct_us_rate_decision_title(title):
        return {
            "is_real_event": True,
            "event_type": "FOMC",
            "reason": "미국 기준금리 실제 결정 확인"
        }
    # 제목의 직접 결정이 없으면 FOMC 경로만 건너뛴다.
    # 요약에 연준 배경이 있어도 제목의 별도 기업 계약·투자 사건은 계속 판정한다.
    if has_direct_us_rate_decision_title(title):
        # -------------------------------------------------
        # FOMC 후속 시장반응 기사 제외
        #
        # 실제 Fed 결정 자체가 아니라
        # 그 결정 이후 주식·환율·채권시장의 반응을 다룬 기사
        # -------------------------------------------------

        fed_market_reaction = contains_any(
            title,
            [
                "코스피",
                "코스닥",
                "나스닥",
                "다우",
                "s&p 500",
                "증시",
                "주가",
                "환율",
                "원·달러",
                "원달러",
                "미국채",
                "국채금리",
                "채권금리",
            ]
        )

        if fed_market_reaction:
            return {
                "is_real_event": False,
                "event_type": "NO_EVENT",
                "reason": "미국 금리 결정 이후 시장반응 기사이며 FOMC 원사건이 아님"
            }
    

        fed_uncertain_context = contains_any(
            text,
            [
                "expected to",
                "expectation",
                "expectations",
                "hope that",
                "hopes that",
                "renewed hope",
                "likely to",
                "unlikely to",
                "could",
                "might",
                "may ",
                "won't be as eager",
                "would raise",
                "would cut",
                "rate hike bets",
                "rate cut bets",
                "bets on",
                "금리 인상 우려",
                "금리 인하 기대",
                "금리 인상 가능성",
                "금리 인하 가능성",
                "금리 인상 전망",
                "금리 인하 전망",
                "연내 금리 인상",
                "연내 금리 인하",
                "금리 인상 한 번 더",
                "금리 인하 한 번 더",
                "인상 근거 놓고",
                "인하 근거 놓고",
            ]
        )

        if has_speculative_context(text) or fed_uncertain_context:
            return {
                "is_real_event": False,
                "event_type": "NO_EVENT",
                "reason": "미국 금리 전망·가능성이며 실제 정책 결정이 아님"
            }

        return {
            "is_real_event": True,
            "event_type": "FOMC",
            "reason": "실제 미국 통화정책·금리 결정"
        }
    # =====================================================
    # PRICE_CHANGE
    # 실제 제품·서비스 가격의 확정 인상/인하
    #
    # 예:
    # GPU 렌탈가를 최대 21% 인상하기로 결정
    # 제품 가격을 10% 인하한다고 발표
    #
    # 주가 상승/하락, 목표가, 가격 전망은 제외
    # =====================================================

    price_target_patterns = [
        "가격",
        "판매가",
        "렌탈가",
        "이용료",
        "요금",
        "구독료",
        "단가",
        "price",
        "pricing",
        "rental price",
        "subscription price",
        "fee",
    ]

    price_change_patterns = [
        "가격 인상",
        "가격 인하",
        "판매가 인상",
        "판매가 인하",
        "렌탈가 인상",
        "렌탈가 인하",
        "이용료 인상",
        "이용료 인하",
        "요금 인상",
        "요금 인하",
        "구독료 인상",
        "구독료 인하",
        "단가 인상",
        "단가 인하",
        "raise prices",
        "raises prices",
        "raised prices",
        "price increase",
        "price increases",
        "increase prices",
        "increases prices",
        "cut prices",
        "cuts prices",
        "price cut",
        "price reduction",
        "lower prices",
    ]

    price_confirmed_patterns = [
        "결정",
        "결정했다",
        "결정해",
        "발표",
        "발표했다",
        "시행",
        "적용",
        "부터",
        "하기로",
        "will raise",
        "will increase",
        "will cut",
        "announced",
        "effective",
    ]

    price_speculative_patterns = [
        "전망",
        "예상",
        "기대",
        "가능성",
        "관측",
        "검토",
        "우려",
        "오를 것",
        "내릴 것",
        "상승 전망",
        "하락 전망",
        "could",
        "might",
        "may raise",
        "may increase",
        "may cut",
        "expected to",
        "likely to",
    ]

    # 주식 자체의 가격 변동은 PRICE_CHANGE가 아니다.
    stock_price_context = contains_any(
        text,
        [
            "주가",
            "목표주가",
            "목표가",
            "stock price",
            "share price",
            "shares rose",
            "shares fell",
        ]
    )

    structured_price_change = bool(
        re.search(
            r"(가격|판매가|렌탈가|이용료|요금|구독료|단가)"
            r".{0,30}"
            r"(인상|인하)",
            text
        )
    )
    confirmed_price_change = (
        contains_any(text, price_target_patterns)
        and (
            contains_any(text, price_change_patterns)
            or structured_price_change
        )
        and contains_any(text, price_confirmed_patterns)
        and not contains_any(text, price_speculative_patterns)
        and not stock_price_context
    )

    if confirmed_price_change:
        return {
            "is_real_event": True,
            "event_type": "PRICE_CHANGE",
            "reason": "제품·서비스의 실제 가격 변경 결정 확인"
        }
    # =====================================================
    # 3. POLICY / 관세 / 수출규제 / 제재
    # =====================================================

    policy_patterns = [
        "imposes tariff",
        "impose tariff",
        "announces tariff",
        "raises tariff",
        "tariff on",
        "export restrictions",
        "export restriction",
        "export ban",
        "imposes sanctions",
        "announces sanctions",

        "관세 부과",
        "관세 인상",
        "수출 규제",
        "수출 제한",
        "수출 금지",
        "제재 발표",
    ]
    if contains_any(title, policy_patterns) and has_direct_policy_action_title(title):
        policy_uncertain = contains_any(

            text,

            [

                "검토 중",

                "검토중",

                "방안 검토",

                "부과 검토",

                "도입 검토",

                "considering",

                "under consideration",

                "may impose",

                "could impose",

                "might impose",

            ]

        )

        if policy_uncertain:

            return {

                "is_real_event": False,

                "event_type": "NO_EVENT",

                "reason": "정책 검토 단계이며 실제 확정 정책이 아님"

            }


        # "관세 부과 시", "부과할 경우" 등은
        # 실제 정책 시행이 아니라 가정이다.
        hypothetical_policy = contains_any(
            title,
            [
                "관세 부과 시",
                "관세 부과할 경우",
                "관세를 부과할 경우",
                "tariff if",
                "if tariff",
            ]
        )

        if hypothetical_policy:
            return {
                "is_real_event": False,
                "event_type": "NO_EVENT",
                "reason": "가정형 정책 기사이며 실제 정책 결정이 아님"
            }

        return {
            "is_real_event": True,
            "event_type": "POLICY",
            "reason": "실제 정부 정책·관세·수출규제 변화"
        } 

        
    # =====================================================
    # 2. M&A
    #
    # 핵심:
    # '인수'라는 단어가 있다는 것과
    # 실제 인수가 확정됐다는 것은 다르다.
    # =====================================================

    ma_confirmed_en = [
        "agrees to buy",
        "agreed to buy",
        "agrees to acquire",
        "agreed to acquire",
        "acquires",
        "acquired",
        "completes acquisition",
        "completed acquisition",
        "merger completed",
        "merger approved",
        "enters into an agreement to acquire",
        "entered into an agreement to acquire",
    ]

    if has_signed_acquisition_agreement(title) or has_signed_acquisition_agreement(summary):
        return {
            "is_real_event": True,
            "event_type": "M&A",
            "reason": "기업 인수·합병 거래 계약 체결 확인(거래 종결은 별도)",
        }

    if contains_any(text, ma_confirmed_en):
        return {
            "is_real_event": True,
            "event_type": "M&A",
            "reason": "실제 인수·합병 사건"
        }

    # -----------------------------------------------------
    # 한국어 M&A
    #
    # "인수"라는 단어만으로 확정 M&A로 판정하지 않는다.
    #
    # 확정:
    #   A사, B사 인수
    #   A사, B사 인수 계약 체결
    #   A사, B사 인수 완료
    #
    # 미확정:
    #   인수 검토 / 추진 / 협상 / 본격화
    #   기업결합 심사 / 사전심사
    # -----------------------------------------------------

    korean_ma_uncertain = contains_any(
        title,
        [
            "인수 검토",
            "인수 추진 검토",
            "인수 추진",
            "인수 본격화",
            "인수설",
            "인수 가능성",
            "인수 협상",
            "인수 논의",
            "인수 타진",
            "인수 제안",

            "합병 검토",
            "합병 추진",
            "합병 가능성",
            "합병 논의",

            "기업결합 사전심사",
            "기업결합 심사",
            "사전심사 개시",

            "동시 검토",

            "인수인 이유",
            "인수 이유",
            "인수해야",
            "인수 필요",
            "인수가 필요한",
            "합병 이유",
        ]
    )

    korean_ma_explainer = contains_any(
        title,
        [
            "이유",
            "왜 ",
            "왜?",
            "필요성",
            "의미",
            "최종관문",
        ]
    )

    # 확정성이 명시된 한국어 M&A
    korean_ma_confirmed = contains_any(
        title,
        [
            "인수 완료",
            "인수 확정",
            "인수 계약",
            "인수 계약 체결",
            "인수하기로",
            "인수키로",

            "합병 완료",
            "합병 확정",
            "합병 승인",
            "합병 계약",
            "합병하기로",
            "합병키로",
        ]
    )
    # 인수·매각 + 실제 거래계약 체결
    korean_ma_transaction_signed = bool(
        re.search(
            r"(인수|매각|합병)"
            r".{0,40}"
            r"(spa\s*체결|주식매매계약\s*체결|본계약\s*체결|매각\s*계약\s*체결)",
            title
        )
    )

    if (
        korean_ma_transaction_signed
        and not korean_ma_explainer
    ):
        return {
            "is_real_event": True,
            "event_type": "M&A",
            "reason": "인수·매각 관련 실제 거래계약 체결 확인"
        }

    if (
        korean_ma_confirmed
        and not korean_ma_uncertain
        and not korean_ma_explainer
    ):
        return {
            "is_real_event": True,
            "event_type": "M&A",
            "reason": "확정된 한국어 인수·합병 행동 확인"
        }

    # -----------------------------------------------------
    # 짧고 직접적인 확정형 제목
    #
    # 예:
    # "엔비디아, 허깅페이스 인수"
    #
    # 단, 추진/검토/협상/심사 등의 문맥은 위에서 차단
    # -----------------------------------------------------

    korean_direct_ma = bool(
        re.search(
            r"^[^…]{1,60}[,\s]+[^…]{1,60}\s+(인수|합병)"
            r"(?:\s*$|…(?:개장전|장중|시간외)?[↑↓]?\s*$)",
            title
        )
    )

    if (
        korean_direct_ma
        and not korean_ma_uncertain
        and not korean_ma_explainer
    ):
        return {
            "is_real_event": True,
            "event_type": "M&A",
            "reason": "제목에서 직접 확인된 확정 인수·합병"
        }

    # =====================================================
    # 3. 계약 / 수주 / 공급
    # =====================================================

    contract_patterns = [
        "wins contract",
        "won contract",
        "signed contract",
        "signs contract",
        "supply contract",
        "supply agreement",
        "purchase order",
        
        

        "공급계약",
        "공급 계약",
        "계약 체결",
        
    ]

    if contains_any(text, contract_patterns):
        return {
            "is_real_event": True,
            "event_type": "CONTRACT",
            "reason": "실제 계약·수주·공급 변화"
        }
        
    # 영어: 실제 계약 체결 문장
    confirmed_agreement = re.search(
        r"\b(signed|signs|entered into|enters into)\b"
        r".{0,60}"
        r"\b(agreement|deal)\b",
        text
    )

    if confirmed_agreement:
        return {
            "is_real_event": True,
            "event_type": "CONTRACT",
            "reason": "실제 계약 체결 문장 확인"
            
        }
    # -----------------------------------------------------
    # 영어: 확정 계약 + 실제 공급/서비스 이행
    #
    # 예:
    # definitive agreements to serve a Google data center
    #
    # 단순 agreement 언급은 인정하지 않는다.
    # -----------------------------------------------------

    definitive_service_agreement = bool(
        re.search(
            r"\bdefinitive agreements?\b"
            r".{0,40}"
            r"\bto\s+(serve|supply|provide|deliver)\b",
            text
        )
    )

    if definitive_service_agreement:
        return {
            "is_real_event": True,
            "event_type": "CONTRACT",
            "reason": "확정 계약과 실제 공급·서비스 이행 확인"
        }
    # -----------------------------------------------------
    # 영어: 구체적 금액이 확인된 실제 수주잔고
    #
    # 예:
    # Super Micro reports $60 billion order backlog
    #
    # 단순 order backlog / orderbook 언급은 통과시키지 않는다.
    # -----------------------------------------------------

    confirmed_order_backlog = bool(
        re.search(
            r"(?:reports?|reported|posts?|posted|records?|recorded)"
            r".{0,60}"
            r"\$[\d,.]+\s*"
            r"(?:million|billion|trillion)?"
            r".{0,40}"
            r"(?:order backlog|orderbook)",
            text
        )
    )

    if confirmed_order_backlog:
        return {
            "is_real_event": True,
            "event_type": "CONTRACT",
            "reason": "구체적 금액이 확인된 실제 수주잔고 발표"
        }
    # -----------------------------------------------------
    # 한국어 신규 수주
    #
    # 숫자 + '수주'만으로는 부족하다.
    # 과거 수주 조사/비리/평가 문맥은 신규 사건이 아니다.
    # -----------------------------------------------------
    # -----------------------------------------------------
    # 한국어 신규 수주
    #
    # 핵심 원칙:
    # 단순히 제목에 "수주"라는 단어가 있다고
    # 신규 CONTRACT로 판정하지 않는다.
    #
    # 1. "수주잔고 / 수주전망 / 수주 기대" 등은 제외
    # 2. 영업이익·매출 등의 숫자를 수주금액으로 오인하지 않는다.
    # 3. 실제 신규 수주 행동이 제목에서 확인돼야 한다.
    # -----------------------------------------------------

    korean_order_context_only = contains_any(
        title,
        [
            "수주 과정",
            "수주 과정 조사",
            "수주 비리",
            "수주 의혹",
            "수주 관련 조사",
            "유리한 평가",

            "수주잔고",
            "수주 잔고",
            "수주 전망",
            "수주 기대",
            "수주 예상",
            "수주 목표",
            "수주 증가",
            "수주 확대",
            "수주 가속화",
        ]
    )

    korean_order_secondary = contains_any(
        title,
        [
            "주가",
            "급등",
            "급락",
            "상승",
            "하락",
            "반등",
            "이유는",
            "왜",
            "목표가",
            "전망",
            "예상",
            "기대",
            "목표",
            "건설주",
            "관련주",
            "사이클",
        ]
    )

    # -----------------------------------------------------
    # 수량 + 수주
    #
    # 예:
    # "컨테이너선 2척 4445억원 수주"
    # "탱커 6척 수주"
    # -----------------------------------------------------

    korean_order_quantity = bool(
        re.search(
            r"\d[\d,.]*\s*(척|대|개|건|종)"
            r".{0,40}"
            r"수주",
            title
        )
    )

    # -----------------------------------------------------
    # 금액이 실제로 '수주'와 연결되어 있는 경우만 인정
    #
    # 예:
    # "535억 규모 ... 공급계약"
    # "104.6억 수주"
    #
    # 영업이익 1조처럼 수주와 무관한 숫자는 제외
    # -----------------------------------------------------

    korean_order_amount = bool(
        re.search(
            r"\d[\d,.]*\s*"
            r"(억원|억|조원|조)"
            r"\s*(규모\s*)?"
            r".{0,25}"
            r"수주",
            title
        )
    )

    # -----------------------------------------------------
    # 기업이 사업/프로젝트를 직접 수주했다고
    # 제목에서 명시하는 형태
    #
    # 예:
    # 웨이버스 "...구축 사업 수주"
    # -----------------------------------------------------

    korean_direct_order = bool(
        re.search(
            r"(사업|공사|프로젝트|장비|선박|시스템)"
            r".{0,30}"
            r"수주(?:$|[\s\"'…·,])",
            title
        )
    )
    # -----------------------------------------------------
    # 계약이라는 단어가 생략된 '확정 공급' 제목
    #
    # 예:
    # 포스코퓨처엠, 삼성SDI에 양극재 6조 공급
    # LG전자, 르노 첫 상용 SDV에 '통합 콕핏' 공급
    #
    # 공급 전망 / 공급 가능성 / 공급 부족 등은 제외
    # -----------------------------------------------------

    korean_direct_supply = bool(
        re.search(
            r".{1,80}"
            r"(에|에게)\s*"
            r".{1,60}"
            r"공급(?:$|[\s\"'…·,])",
            title
        )
    )

    korean_supply_uncertain = contains_any(
        title,
        [
            "공급 전망",
            "공급 예상",
            "공급 기대",
            "공급 가능성",
            "공급 검토",
            "공급 계획",
            "공급 예정",
            "공급 부족",
            "공급 우려",
            "공급 확대 전망",
            "공급 증가 전망",
        ]
    )

    if (
        (
            korean_order_quantity
            or korean_order_amount
            or korean_direct_order
            or korean_direct_supply
        )
        and not korean_order_context_only
        and not korean_order_secondary
        and not korean_supply_uncertain
    ):
        return {
            "is_real_event": True,
            "event_type": "CONTRACT",
            "reason": "제목에서 실제 신규 수주 행동 확인"
        }

    # =====================================================
    # 4. CAPEX / 투자 / 증설
    # =====================================================

    capex_patterns = [
        "to invest",
        "will invest",
        "plans to invest",
        "announces investment",
        "announced investment",
        
        "invest $",
        "invests $",
        
        "spending plan",
        "raises spending",
        "boosts spending",
        "new factory",
        "new plant",
        "expand production",
        "expands production",
        
        "투자 계획",
        "설비투자",
        "설비투자",
        "증설한다",
        "증설하기로",
        "증설 결정",
        "증설 착수",
        "증설 완료",
        "증설 투자",

        "공장 건설",
        "생산능력 확대",
    ]

    # 요약의 사업 소개·자금 사용 계획만으로 제목을 CAPEX로 승격하지 않는다.
    # 기존 주가반응 혼합 기사 예외는 요약에 실제 투자 발표가 있을 때만 유지한다.
    capex_text = title
    if confirmed_event_override:
        for sentence in re.split(r"(?<=[.!?。])\s+|[\n;]", summary):
            if re.search(
                r"\b(?:announces?|announced|committed to invest)\b.{0,80}"
                r"\b(?:investment|invest)\b|(?:투자|증설).{0,10}(?:결정|확정|완료)",
                sentence,
            ) and has_confirmed_event_inside_reaction(title, sentence):
                capex_text += f" {sentence}"

    if contains_any(capex_text, capex_patterns):

        # 향후 투자·증설 전망은 실제 신규 CAPEX 사건이 아니다.
        if has_speculative_context(capex_text):
            return {
                "is_real_event": False,
                "event_type": "NO_EVENT",
                "reason": "투자·증설 전망이며 실제 확정 CAPEX가 아님"
            }

        return {
            "is_real_event": True,
            "event_type": "CAPEX",
            "reason": "실제 투자·CAPEX·생산능력 변화"
        }
    # 한국어: 구체적인 금액이 있는 실제 투자
    # -----------------------------------------------------
    # 한국어: 실제 물리적 설비 / 공장 / 생산시설 신규 구축
    # -----------------------------------------------------

    korean_facility_build = re.search(
        r"(발전설비|생산설비|제조설비|설비|생산라인|공장|생산시설)"
        r".{0,25}"
        r"(신규\s*구축|신설|설치|착공|짓는다|건설한다)",
        title
    )

    korean_facility_uncertain = contains_any(
        title,
        [
            "구축 계획",
            "신설 계획",
            "설치 계획",
            "착공 계획",
            "구축 예정",
            "신설 예정",
            "검토 중",
            "검토중",
            "가능성",
            "전망",
        ]
    )

    if korean_facility_build and not korean_facility_uncertain:
        return {
            "is_real_event": True,
            "event_type": "CAPEX",
            "reason": "실제 설비·생산시설 신규 구축 확인"
        }
    # =========================================================

    # PRODUCTION / 실제 생산·가동 변화

    # =========================================================

    # 한국어: 실제 공장·생산시설 가동률 확인

    korean_operation_rate = (

        re.search(

            r"(공장|생산라인|생산시설|라인)"

            r".{0,30}"

            r"\d+(?:\.\d+)?\s*%\s*가동",

            title

        )

        or re.search(

            r"\d+(?:\.\d+)?\s*%\s*가동"

            r".{0,30}"

            r"(공장|생산라인|생산시설|라인)",

            title

        )

    )

    if korean_operation_rate:

        return {

            "is_real_event": True,

            "event_type": "PRODUCTION",

            "reason": "실제 공장·생산시설 가동률 변화 확인"

        }
    
    
    korean_investment_amount = re.search(
        r"\d[\d,.]*\s*"
        r"(억달러|만달러|달러|억원|억|조원|조)"
        r"\s*"
        r"(규모\s*)?"
        r"(투자(?:$|[\s…·,:])|투자한다|투자하기로|투자 결정|투자 확정)",
        title
    )
    if (
        korean_investment_amount
        and not has_speculative_context(title)
    ):
        return {
            "is_real_event": True,
            "event_type": "CAPEX",
            "reason": "구체적 투자 금액과 확정 투자 행동 확인"
        }
    # "announces $50 billion investment in ..." 같은
    # 실제 투자 발표 문장 처리

    if re.search(
        r"\b(announces|announced|plans|planned|commits|committed)\b"
        r".{0,40}"
        r"\binvestment\b",
        capex_text
    ):

        if has_speculative_context(capex_text):
            return {
                "is_real_event": False,
                "event_type": "NO_EVENT",
                "reason": "투자 전망이며 실제 확정 CAPEX가 아님"
            }

        return {
            "is_real_event": True,
            "event_type": "CAPEX",
            "reason": "실제 투자·CAPEX·생산능력 변화"
        }

    # =====================================================
    # 5. 실적 / 가이던스
    # =====================================================

    earnings_patterns = [
        
        # 영어 실제 실적
        "reports revenue",
        "reported revenue",
        "revenue doubles",
        "revenue rose",
        "revenue rises",
        "revenue increased",
        "profit surge",
        "profit rises",
        "earnings beat",
        "earnings miss",
        "quarterly profit",
        "quarterly revenue",
        "raises guidance",
        "raised guidance",
        "cuts guidance",
        "cut guidance",
        "forecasts annual revenue",
        "revenue above estimates",
        "record revenue",

        # 한국어 - 행동 자체가 명확한 경우
        "흑자전환",
        "흑자 전환",
        "적자전환",
        "적자 전환",
        "가이던스 상향",
        "가이던스 하향",
    ]

    
    if contains_any(text, earnings_patterns):

        # -------------------------------------------------
        # 실적 분석·비교·전망은 실제 신규 실적 발표가 아니다.
        # -------------------------------------------------

        earnings_secondary = contains_any(
            earnings_context_without_benchmark(title),
            [
                # 영어 비교·분석
                "comparing",
                "comparison",
                " vs. ",
                " vs ",
                "trajectory",
                "trajectories",

                # 영어 미래 전망
                "expected to",
                "expects to",
                
    

                # 한국어 전망·기대
                "전망",
                "예상",
                "기대",
                "추정",
            ]
        )

        if earnings_secondary:
            return {
                "is_real_event": False,
                "event_type": "NO_EVENT",
                "reason": "실적 비교·분석·전망이며 신규 확정 실적이 아님"
            }

        return {
            "is_real_event": True,
            "event_type": "EARNINGS",
            "reason": "실제 실적·가이던스 변화"
        }
        
    # 영어: 분기 실적 결과 + 예상치 상회 / 가이던스 상향
    english_earnings_result = (
        re.search(
            r"\bq[1-4]\s+\d{4}\s+earnings\b",
            title
        )
        and (
            re.search(
                r"\b(beat|beats|beat expectations|"
                r"smashed|topped|exceeded)\b"
                r".{0,50}"
                r"\b(expectations|estimates)\b",
                text
            )
            or re.search(
                r"\b(raise|raises|raised|raising)\b"
                r".{0,60}"
                r"\b(revenue|guidance|forecast|outlook|expectations)\b",
                text
            )
        )
    )

    if english_earnings_result:
        return {
            "is_real_event": True,
            "event_type": "EARNINGS",
            "reason": "분기 실적 결과와 예상치·가이던스 변화 확인"
        }
    # 영어: 분기 실적 기사 + 실제 결과 신호
    #
    # Q4 Earnings Call Highlights
    # Fiscal Q3 Results
    # 같은 형식의 실제 실적 기사 처리
    english_period_report = (
        re.search(
            r"\b(?:fiscal\s+)?q[1-4]\s+\d{4}\b"
            r".{0,40}"
            r"\b(earnings|results|earnings call)\b",
            title
        )
        or re.search(
            r"\b(earnings call highlights|fiscal q[1-4] results)\b",
            title
        )
        or (re.search(r"\breports?\b|\breported\b", title)
            and not re.search(r"\b(?:will|to|scheduled to)\s+report\b", title)
            and re.search(r"\bfiscal\s+(?:first|second|third|fourth)[ -]quarter\b"
                          r".{0,60}\b(?:results|earnings)\b", title))
    )

    english_actual_result_signal = (
        re.search(
            r"\b(better-than-expected|beat|beats|beating|"
            r"record|surpasses|surpassed|exceeds|exceeded)\b",
            text
        )
        or re.search(
            r"\b(raise|raises|raised|raising|guide|guides|guiding)\b"
            r".{0,60}"
            r"\b(guidance|revenue|profit|earnings|growth|outlook)\b",
            text
        )
    )

    if english_period_report and english_actual_result_signal:
        return {
            "is_real_event": True,
            "event_type": "EARNINGS",
            "reason": "분기 실적 기사에서 실제 결과·가이던스 변화 확인"
        }

    # -----------------------------------------------------
    # 한국어 실제 실적
    #
    # 실적은 반드시 '금액'이 있어야 하는 것이 아니다.
    # 기간 + 실적지표 + 확정된 결과 변화도 실제 실적이다.
    # -----------------------------------------------------

    korean_period = contains_any(
        title,
        [
            "1분기",
            "2분기",
            "3분기",
            "4분기",
            "상반기",
            
            "연간",
        ]
    )
    korean_monthly_period = bool(
        re.search(
            r"\b(?:1[0-2]|[1-9])월\b",
            title
        )
    )
    korean_metric = contains_any(
        title,
        [
            "매출",
            "영업이익",
            "순이익",
            "순익",
            "실적",
        ]
    )

    korean_result_change = contains_any(
        title,
        [
            "급증",
            "급감",
            "증가",
            "감소",
            "늘어",
            "줄어",
            "사상 최대",
            "사상 첫",
            "최대 실적",
            "최대 매출",
            "흑자전환",
            "흑자 전환",
            "적자전환",
            "적자 전환",
        ]
    )

    korean_result_number = bool(
        re.search(
            r"(매출(?:액)?|영업이익|순이익|순익)"
            r".{0,25}?"
            r"\d[\d,.]*\s*(억|억원|조|조원|만원|원)",
            title
        )
    )

    korean_result_percent = bool(
        re.search(
            r"(매출(?:액)?|영업이익|순이익|순익)"
            r".{0,25}?"
            r"\d[\d,.]*\s*%",
            title
        )
    )
    korean_earnings_speculative = contains_any(
        earnings_context_without_benchmark(title),
        [
            "전망",
            "예상",
            "기대",
            "추정",
            "넘을듯",
            "넘을 듯",
            "예상된다",
            "전망된다",
            "것으로 보인다",
            "것으로 예상",
            "것으로 전망",
        ]
    )

    if (
        (korean_period or korean_monthly_period)
        and korean_metric
        and not korean_earnings_speculative
        and (
            korean_result_change
            or korean_result_number
            or korean_result_percent
        )
    ):
        return {
            "is_real_event": True,
            "event_type": "EARNINGS",
            "reason": "실적 기간과 확정된 실적 변화 확인"
        }


    # =====================================================
    # 6. 생산 / 양산
    # =====================================================

    production_patterns = [
        "mass production",
        "begins production",
        "began production",
        "commercial production",
        "starts production",
        "양산 시작",
        "양산 본격화",
        "상업 생산",
    ]

    if contains_any(text, production_patterns):

        return {
            "is_real_event": True,
            "event_type": "PRODUCTION",
            "reason": "실제 생산·양산 변화"
        }

    # =====================================================
    # 고객사 품질테스트 통과 / 제품 승인
    # =====================================================

    customer_quality_approval = (
        contains_any(title, [
            "품질테스트 통과",
            "품질 테스트 통과",
            "고객사 품질검증 통과",
            "고객사 품질 검증 통과",
        ])
        and not has_speculative_context(title)
    )

    if customer_quality_approval:
        return {
            "is_real_event": True,
            "event_type": "APPROVAL",
            "reason": "고객사 품질테스트 통과 확인"
        }


    # =====================================================
    # 7. 어느 조건에도 해당하지 않으면 사건으로 만들지 않는다.
    # =====================================================

    return {
        "is_real_event": False,
        "event_type": "NO_EVENT",
        "article_role": article_role,
        "reason": "확인 가능한 실제 행동·변화 없음"
}
