import importlib
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo


class FinancialDataTests(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        self.directory = tempfile.TemporaryDirectory()
        os.chdir(self.directory.name)
        Path('corp_code.csv').write_text('stock_code,corp_code\n022100,00126380\n')
        for name in ('finance_engine', 'quality_engine'):
            sys.modules.pop(name, None)
        self.finance = importlib.import_module('finance_engine')
        self.quality = importlib.import_module('quality_engine')
        self.market = importlib.import_module('market_engine')

    def tearDown(self):
        os.chdir(self.cwd)
        self.directory.cleanup()
        for name in ('finance_engine', 'quality_engine'):
            sys.modules.pop(name, None)

    def row(self, section, account, name, value):
        return dict(sj_div=section, account_id=account, account_nm=name,
                    thstrm_amount=str(value))

    def test_statement_components_do_not_overwrite_totals(self):
        rows = [
            self.row('BS', 'ifrs-full_Assets', '자산총계', 834391536739),
            self.row('BS', 'ifrs-full_Equity', '자본총계', 572559763845),
            self.row('BS', 'ifrs-full_Liabilities', '부채총계', 261831772894),
            self.row('CIS', 'ifrs-full_Revenue', '매출액', 1075175363044),
            self.row('CIS', 'dart_OperatingIncomeLoss', '영업이익', 60388586087),
            self.row('CIS', 'ifrs-full_ProfitLoss', '당기순이익(손실)', 52623905401),
            self.row('CIS', 'ifrs-full_ProfitLossAttributableToOwnersOfParent',
                     '지배기업 소유주 귀속 순이익', 52081264979),
            self.row('SCE', 'ifrs-full_Equity', '자본총계', 224437298894),
            self.row('SCE', 'ifrs-full_ProfitLoss', '당기순이익(손실)', 0),
            self.row('CF', 'ifrs-full_ProfitLoss', '당기순이익(손실)', 0),
        ]
        with patch('requests.get', return_value=Mock(json=lambda: {'status': '000', 'list': rows})):
            quality = self.quality.get_dart_year_finance('022100', 2025)
            finance = self.finance.get_dart_finance('022100')
        self.assertEqual(quality['equity'], 572559763845)
        self.assertEqual(quality['net_income'], 52623905401)
        self.assertEqual(quality['debt_ratio'], 45.73)
        self.assertEqual(quality['roe'], 9.19)
        self.assertEqual(quality['op_margin'], 5.62)
        self.assertEqual(finance['debt_ratio'], quality['debt_ratio'])

    def test_missing_profit_is_not_reported_as_zero_roe(self):
        rows = [self.row('BS', 'ifrs-full_Equity', '자본총계', 100),
                self.row('CIS', 'ifrs-full_ProfitLoss', '당기순이익', '-')]
        with patch('requests.get', return_value=Mock(json=lambda: {'status': '000', 'list': rows})):
            result = self.quality.get_dart_year_finance('022100', 2025)
        self.assertIsNone(result['roe'])
        self.assertIsNone(result['net_income'])

    def test_per_pbr_integration_fields(self):
        response = Mock(json=lambda: {'totalInfos': [
            {'code': 'per', 'value': '100.48배'}, {'code': 'pbr', 'value': '5.68배'}]})
        with patch('requests.get', return_value=response):
            self.assertEqual(self.finance.get_naver_basic('022100'), {'per': 100.48, 'pbr': 5.68})

    def test_unavailable_valuation_remains_missing(self):
        response = Mock(json=lambda: {'totalInfos': [
            {'code': 'per', 'value': 'N/A'}, {'code': 'pbr', 'value': '-'}]})
        with patch('requests.get', return_value=response):
            self.assertEqual(self.finance.get_naver_basic('022100'), {'per': None, 'pbr': None})

    def test_market_uses_latest_completed_day_in_any_order(self):
        rows = [
            {'localDate': '20261008', 'closePrice': 20800, 'accumulatedTradingVolume': 249834},
            {'localDate': '20261012', 'closePrice': 21100, 'accumulatedTradingVolume': 7947},
            {'localDate': '20261007', 'closePrice': 21100, 'accumulatedTradingVolume': 201348},
        ]
        with patch('requests.get', return_value=Mock(json=lambda: rows)), patch.object(
            self.market, 'datetime', wraps=datetime
        ) as clock:
            clock.now.return_value = datetime(2026, 10, 12, 8, 32, tzinfo=ZoneInfo('Asia/Seoul'))
            result = self.market.get_market_score({'code': '022100'})
        self.assertEqual(result['trading_date'], '20261008')
        self.assertEqual(result['volume'], 249834)
        self.assertEqual(result['trading_value'], 5196547200)
        self.assertEqual(result['change_rate'], -1.42)
        self.assertTrue(result['trading_value_is_estimate'])

    def test_empty_chart_does_not_fabricate_market_data(self):
        with patch('requests.get', return_value=Mock(json=lambda: [])):
            result = self.market.get_naver_market('022100')
        self.assertIsNone(result['trading_value'])


if __name__ == '__main__':
    unittest.main()
