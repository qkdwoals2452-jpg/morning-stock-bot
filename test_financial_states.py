"""Synthetic wording boundaries; not a historical fact or returns backtest."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from financial_state_engine import assess_financial_states, contract_score_cap
from event_engine import build_events, calc_event_score


class FinancialStateTests(unittest.TestCase):
    def claims(self, text, kind):
        return assess_financial_states({'summary': text})[kind]

    def test_ppl_style_split_does_not_make_term_sheet_binding(self):
        text = ('Invitium agreed to key commercial terms with QTS. '
                'The term sheet is nonbinding. '
                'Invitium executed a cost reimbursement agreement with QTS.')
        states = self.claims(text, 'contract_claims')
        self.assertEqual([c['state'] for c in states], ['nonbinding', 'signed'])
        self.assertIn('reimbursement', states[1]['text'])

    def test_expected_deposit_not_received(self):
        for text in ['We expect $9 billion in customer prepayments and deposits.',
                     'Customer deposits will be received next quarter.',
                     '고객 선급금 90억달러 수령 예정']:
            with self.subTest(text=text):
                self.assertEqual(self.claims(text, 'cash_claims')[0]['state'], 'expected')

    def test_cash_and_revenue_are_separate_even_in_same_sentence(self):
        for text in ['We received $2 billion in customer deposits.',
                     '고객 선수금 20억원 수령 완료']:
            result = assess_financial_states({'summary': text})
            self.assertEqual(result['cash_claims'][0]['state'], 'received_claim')
            self.assertEqual(result['revenue_claims'], [])
            self.assertFalse(result['cash_is_revenue'])
            self.assertEqual(result['score_bonus'], 0)

    def test_denial_and_forecast_are_not_realized(self):
        for text in ['We have not received deposits.', '고객 선수금 미수령']:
            self.assertEqual(self.claims(text, 'cash_claims')[0]['state'], 'unconfirmed_or_negated')
        self.assertEqual(self.claims('We expect recognized revenue to rise.', 'revenue_claims')[0]['state'], 'expected')
        self.assertEqual(self.claims('We recognized first lease revenue.', 'revenue_claims')[0]['state'], 'recognized_claim')

    def test_unknown_is_not_paid(self):
        self.assertEqual(self.claims('Deposits total $9 billion.', 'cash_claims')[0]['state'], 'unknown')

    def test_future_signing_is_not_executed(self):
        for text in ['Company plans to sign a contract.',
                     'Company will execute an agreement.', '공급계약 체결 예정']:
            self.assertEqual(self.claims(text, 'contract_claims')[0]['state'], 'planned')

    def test_definitive_contract_survives_routine_closing_conditions(self):
        article = {'title': 'Company signs supply agreement',
                   'summary': 'Company signed a definitive agreement subject to customary closing conditions.'}
        self.assertIsNone(contract_score_cap(article, 'CONTRACT'))
        self.assertGreaterEqual(calc_event_score(article)[0], 70)
        self.assertEqual(assess_financial_states(article)['contract_claims'][1]['state'], 'signed')

    def test_unrelated_summary_does_not_downgrade_headline(self):
        article = {'title': 'Company signs supply contract',
                   'summary': 'OtherCo signed a nonbinding term sheet.'}
        self.assertIsNone(contract_score_cap(article, 'CONTRACT'))

    def test_score_cap_and_corroboration_cannot_promote_term_sheet(self):
        article = {'title': 'Company signs term sheet agreement for power supply',
                   'summary': '', 'market': 'US', 'source': 'fixture',
                   'link': 'https://example.com/term-sheet', 'published_at': '2026-11-06T12:00:00Z'}
        # Force permissive upstream classification to test the independent guard.
        with patch('event_engine.understand_event', return_value={
                'is_real_event': True, 'event_type': 'CONTRACT', 'reason': 'fixture'}), \
                patch('event_engine.corroboration_bonus', return_value=20):
            self.assertEqual(calc_event_score(article)[0], 60)
            event = build_events([deepcopy(article)])[0]
            self.assertEqual(event['event_score'], 60)
            self.assertEqual(event['evidence_strength'], 'MEDIUM')

    def test_real_term_sheet_path_is_not_confirmed_or_strong(self):
        for title in ['Company signs term sheet agreement for power supply',
                      'Company signs nonbinding supply agreement']:
            article = {'title': title}
            score, reasons = calc_event_score(article)
            self.assertEqual(score, 60)
            self.assertNotIn('사건신분:CONFIRMED', reasons)
            event = build_events([article])[0]
            self.assertEqual(event['evidence_strength'], 'MEDIUM')
            self.assertLess(event['event_score'], 70)

    def test_rejected_article_still_audited_and_input_not_mutated_by_extractor(self):
        article = {'title': 'Company signs non-binding supply agreement', 'summary': ''}
        original = deepcopy(article)
        assess_financial_states(article)
        self.assertEqual(article, original)
        decisions = []
        self.assertEqual(build_events([article], decisions), [])
        self.assertEqual(decisions[0]['financial_states']['contract_claims'][0]['state'], 'nonbinding')

    def test_live_event_path_retains_expected_cash_without_score_bonus(self):
        article = {'title': 'CoreWeave reports revenue of $3.661 billion',
                   'summary': 'We expect $9 billion in customer prepayments and deposits.'}
        event = build_events([article])[0]
        self.assertEqual(event['event_type'], 'EARNINGS')
        self.assertEqual(event['financial_states']['cash_claims'][0]['state'], 'expected')
        self.assertEqual(event['financial_states']['revenue_claims'], [])


if __name__ == '__main__':
    unittest.main()
