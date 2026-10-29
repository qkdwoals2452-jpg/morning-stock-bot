import unittest
from datetime import date
from unittest.mock import Mock, patch
import test_financial_data as fixtures
from breaking_event_gate import headline_action
from event_understanding_engine import is_analysis_article

class CurrentDisclosureTests(unittest.TestCase):
    setUp = fixtures.FinancialDataTests.setUp
    tearDown = fixtures.FinancialDataTests.tearDown

    def response(self, status='000', rows=None):
        return Mock(json=lambda: {'status': status, 'list': rows or []})

    def rows(self):
        return [dict(sj_div=section, account_id=account, account_nm='',
                     thstrm_amount=str(value), thstrm_add_amount=str(cumulative))
                for section, account, value, cumulative in [
                    ('IS', 'ifrs-full_Revenue', 100, 200),
                    ('IS', 'dart_OperatingIncomeLoss', 20, -10),
                    ('BS', 'ifrs-full_Equity', 100, 999),
                    ('BS', 'ifrs-full_Liabilities', 50, 999)]]

    def test_latest_published_report_uses_consistent_ytd(self):
        with patch('requests.get', side_effect=[self.response('013'), self.response(rows=self.rows())]) as get:
            result = self.finance.get_dart_finance('022100', date(2026,10,30))
        self.assertEqual([c.kwargs['params']['reprt_code'] for c in get.call_args_list], ['11014','11012'])
        self.assertEqual(result['op_margin'], -5)
        self.assertEqual(result['debt_ratio'], 50)
        self.assertEqual(result['report']['year'], 2026)

    def test_api_error_does_not_silently_use_old_finance(self):
        with patch('requests.get', return_value=self.response('020')) as get:
            result = self.finance.get_dart_finance('022100', date(2026,10,30))
        self.assertIsNone(result['op_margin'])
        self.assertEqual(get.call_count, 1)

    def test_missing_ytd_or_profit_cannot_become_zero(self):
        rows=self.rows()
        rows[1].pop('thstrm_add_amount')
        with patch('requests.get', return_value=self.response(rows=rows)):
            result=self.finance.get_dart_finance('022100', date(2026,10,30))
        self.assertIsNone(result['op_margin'])

    def test_completed_periods_only_and_rollover(self):
        candidates=self.finance.report_candidates(date(2027,1,1))
        self.assertEqual(candidates[0], (2026,'11011'))
        self.assertNotIn((2027,'11013'), candidates)

    def test_rating_article_never_contract_alert(self):
        title="팬오션, 운임 호황에도 투자의견 '보유' 유지…선박 공급 과잉 우려-KB"
        self.assertTrue(is_analysis_article(title))
        self.assertFalse(headline_action({'event_title': title, 'event_type':'CONTRACT'}))
        self.assertTrue(headline_action({'event_title':'팬오션, 500억 규모 장기 운송 계약 체결','event_type':'CONTRACT'}))
