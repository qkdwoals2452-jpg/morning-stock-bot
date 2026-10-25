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

    def test_financial_sector_is_held_for_model_coverage_not_generic_debt_failure(self):
        for sector in ('기타 금융업', '은행 및 저축기관', '보험업', '금융 지원 서비스업'):
            with self.subTest(sector=sector), patch.object(self.finance, 'get_naver_basic') as basic:
                result = self.finance.get_finance_score({'name': '검증회사', 'code': '123456', 'sector': sector})
                self.assertTrue(result['exclude'])
                self.assertEqual(result['model_coverage'], 'UNSUPPORTED_FINANCIAL_SECTOR')
                self.assertIn('전용 재무 검증 미지원', result['exclude_reason'])
                basic.assert_not_called()

    def test_financial_word_in_software_company_name_does_not_block_normal_model(self):
        with patch.object(self.finance, 'get_naver_basic', return_value={'per': 10, 'pbr': 1}), \
             patch.object(self.finance, 'get_dart_finance', return_value={'op_margin': 8, 'debt_ratio': 50}), \
             patch.object(self.finance, 'get_quality_score', return_value={'score': 10}):
            result = self.finance.get_finance_score({'name': '금융IT', 'code': '123456', 'sector': '소프트웨어 개발업'})
        self.assertFalse(result['exclude'])

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

    def test_samsung_electro_mechanics_operating_balance_totals(self):
        # 2026-10-20 운영 로그의 2025 연결 재무: 총계 계정명에 공백이 있다.
        rows = [
            self.row('BS', 'ifrs-full_Assets', '자산 총계', 14595895255468),
            self.row('BS', 'ifrs-full_Equity', '자본 총계', 9797343882863),
            self.row('BS', 'ifrs-full_Liabilities', '부채 총계', 4798551372605),
            self.row('CIS', 'ifrs-full_Revenue', '매출액', 11314459238100),
            self.row('CIS', 'dart_OperatingIncomeLoss', '영업이익', 913331178557),
            self.row('CIS', 'ifrs-full_ProfitLoss', '당기순이익', 730989517218),
            self.row('SCE', 'ifrs-full_Equity', '자본 총계', 1),
            self.row('CF', 'ifrs-full_Liabilities', '부채 총계', 1),
        ]
        # 테스트용 CSV의 종목을 운영 종목으로 매핑한다.
        self.finance.corp_map['009150'] = '00126371'
        self.quality.corp_map['009150'] = '00126371'
        with patch('requests.get', return_value=Mock(json=lambda: {'status': '000', 'list': rows})), patch.object(
            self.finance, 'get_quality_score', return_value={'score': 0}
        ):
            result = self.finance.get_finance_score({'code': '009150'})
            quality = self.quality.get_dart_year_finance('009150', 2025)
        self.assertEqual(result['op_margin'], 8.07)
        self.assertEqual(result['debt_ratio'], 48.98)
        self.assertFalse(result['exclude'])
        self.assertEqual(quality['equity'], 9797343882863)
        self.assertEqual(quality['debt_ratio'], 48.98)
        self.assertEqual(quality['roe'], 7.46)

    def test_balance_totals_support_ids_and_custom_spaced_names(self):
        for ids, names in [
            (['ifrs-full_Assets', 'ifrs-full_Liabilities', 'ifrs-full_Equity'],
             ['Total assets', 'Total liabilities', 'Total equity']),
            (['custom_assets', 'custom_debt', 'custom_equity'],
             ['자산\u00a0총계', '부채 총계', '자본\t총계']),
        ]:
            with self.subTest(ids=ids):
                rows = [self.row('BS', account, name, value)
                        for account, name, value in zip(ids, names, [150, 50, 100])]
                with patch('requests.get', return_value=Mock(json=lambda: {'status': '000', 'list': rows})):
                    self.assertEqual(self.finance.get_dart_finance('022100')['debt_ratio'], 50)
                    self.assertEqual(self.quality.get_dart_year_finance('022100', 2025)['debt_ratio'], 50)

    def test_missing_balance_values_are_not_zero_debt(self):
        for missing in [None, '-', '']:
            rows = [self.row('BS', 'ifrs-full_Assets', '자산 총계', 150),
                    self.row('BS', 'ifrs-full_Equity', '자본 총계', 100),
                    self.row('BS', 'ifrs-full_Liabilities', '부채 총계', missing)]
            with self.subTest(missing=missing), patch('requests.get', return_value=Mock(
                json=lambda: {'status': '000', 'list': rows}
            )):
                self.assertIsNone(self.finance.get_dart_finance('022100')['debt_ratio'])
                self.assertIsNone(self.quality.get_dart_year_finance('022100', 2025)['debt_ratio'])

    def test_balance_equity_fallback_and_real_zero_debt(self):
        for debt, expected in [(50, 50), (0, 0)]:
            rows = [self.row('BS', 'ifrs-full_Assets', '자산 총계', 150),
                    self.row('BS', 'ifrs-full_Liabilities', '부채 총계', debt)]
            with self.subTest(debt=debt), patch('requests.get', return_value=Mock(
                json=lambda: {'status': '000', 'list': rows}
            )):
                self.assertEqual(self.finance.get_dart_finance('022100')['debt_ratio'], expected)
                self.assertEqual(self.quality.get_dart_year_finance('022100', 2025)['debt_ratio'], expected)

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
        normalized = [{'date': '2026-10-07', 'close': 21100, 'volume': 201348,
                       'source': 'YAHOO_REGULAR_CLOSE'},
                      {'date': '2026-10-08', 'close': 20800, 'volume': 249834,
                       'source': 'YAHOO_REGULAR_CLOSE'}]
        with patch.object(self.market, 'get_price_history', return_value=normalized):
            result = self.market.get_market_score({'code': '022100'})
        self.assertEqual(result['trading_date'], '20261008')
        self.assertEqual(result['volume'], 249834)
        self.assertEqual(result['trading_value'], 5196547200)
        self.assertEqual(result['change_rate'], -1.42)
        self.assertTrue(result['trading_value_is_estimate'])

    def test_empty_chart_does_not_fabricate_market_data(self):
        with patch.object(self.market, 'get_price_history', return_value=[]):
            result = self.market.get_naver_market('022100')
        self.assertIsNone(result['trading_value'])


if __name__ == '__main__':
    unittest.main()
