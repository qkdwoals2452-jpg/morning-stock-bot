"""Text claims, not independent verification of contracts, cash or revenue.

Keep each clause and its source field. Never sum amounts across these claims or
turn a payment into revenue. Missing evidence remains unknown.
"""
import re


NONBINDING = re.compile(r'\bnon[ -]?binding\b|비구속|구속력(?:이|은)?\s*없', re.I)
CONTRACT = re.compile(r'\b(?:contract|agreement|term sheet|lease|memorandum|mou)\b|계약|합의|양해각서', re.I)
CASH = re.compile(r'\b(?:prepayments?|deposits?|advances?)\b|선급금|선수금|예치금', re.I)
FUTURE = re.compile(r'\b(?:expect\w*|anticipat\w*|will|would|forecast\w*|guidance|plans?|scheduled|due)\b|예상|예정|전망|계획', re.I)
NEGATED = re.compile(r'\b(?:not|never|no)\b(?!\s+only)|미수령|미인식|미체결|받지\s*않|인식하지\s*않', re.I)
SIGNED = re.compile(r'\b(?:signs|signed|executed|entered into|enters into)\b|계약\s*체결|체결했|체결하였', re.I)
SIGNING_INTENT = re.compile(r'\b(?:plans? to|expects? to|will|would|may|might|could|aims? to)\s+(?:sign|execute|enter into)\b|체결\s*(?:예정|추진|목표)', re.I)
RECEIVED = re.compile(r'\b(?:received|collected|receipt of)\b|수령했|수령하였|수령\s*완료|수취했|입금\s*완료', re.I)
RECOGNIZED = re.compile(r'\b(?:recognized|recognised)\b.{0,45}\brevenue\b|매출.{0,15}인식(?:했|하였|\s*완료)', re.I)


def assess_financial_states(article):
    """Return conservative per-clause states; no inferred amount or score bonus."""
    contracts, cash, revenue = [], [], []
    for field in ('title', 'summary'):
        text = re.sub(r'\s+', ' ', str(article.get(field, '') or '')).strip()
        # Preserve decimal numbers; split sentences, semicolons and contrast clauses.
        clauses = re.split(r'(?<=[.!?。])\s+(?=[A-Z가-힣])|;|\s+but\s+|\s+while\s+|\s+반면\s*', text)
        for clause in clauses:
            if not clause:
                continue
            proof = {'field': field, 'text': clause}
            negative, future = bool(NEGATED.search(clause)), bool(FUTURE.search(clause))
            if CONTRACT.search(clause):
                if NONBINDING.search(clause):
                    state = 'nonbinding'
                elif negative:
                    state = 'unconfirmed_or_negated'
                elif re.search(r'\b(?:mou|memorandum of understanding|letter of intent|term sheet)\b|양해각서|조건합의', clause, re.I):
                    state = 'preliminary'
                elif SIGNING_INTENT.search(clause) or (future and not SIGNED.search(clause)):
                    state = 'planned'
                elif SIGNED.search(clause):
                    state = 'signed'
                else:
                    state = 'unknown'
                contracts.append(dict(proof, state=state))
            if CASH.search(clause):
                state = ('unconfirmed_or_negated' if negative else 'expected' if future
                         else 'received_claim' if RECEIVED.search(clause) else 'unknown')
                cash.append(dict(proof, state=state))
            if RECOGNIZED.search(clause):
                state = ('unconfirmed_or_negated' if negative else 'expected' if future
                         else 'recognized_claim')
                revenue.append(dict(proof, state=state))
    return {'contract_claims': contracts, 'cash_claims': cash,
            'revenue_claims': revenue, 'verification': 'article_text_only',
            'cash_is_revenue': False, 'score_bonus': 0}


def contract_score_cap(article, event_type):
    """Stop only a headline's preliminary contract becoming a strong event.

    A separate, unnamed summary agreement cannot downgrade an unrelated headline.
    Standard closing conditions on a signed agreement are not nonbinding intent.
    """
    if event_type != 'CONTRACT':
        return None
    title = str(article.get('title', '') or '')
    if CONTRACT.search(title) and (NONBINDING.search(title) or
            re.search(r'\b(?:term sheet|letter of intent|memorandum of understanding|mou)\b|양해각서|조건합의', title, re.I)):
        return 60
    return None
