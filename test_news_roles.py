import contextlib
import io
import os
import unittest
from unittest.mock import patch

import event_understanding_engine as engine


class NewsRoleTests(unittest.TestCase):
    def test_recommendation_lists_are_analysis_not_events(self):
        for title in [
            '3 AI Stocks To Own In October 2026',
            '3 Monthly Dividend Stocks Yielding Over 5% Worth Owning Now',
            'Following OpenAI’s Revenue Report, Should You Really Buy AI Stocks Right Now?',
            '3 Unique ETFs With Strong Momentum for the End of the Year',
            'AI 추천주와 투자 포인트',
        ]:
            with self.subTest(title=title):
                self.assertEqual(engine.classify_article_role(title), 'ANALYSIS')
                self.assertFalse(engine.understand_event({'title': title})['is_real_event'])

    def test_lifestyle_titles_are_not_events(self):
        for title in ['남은 탕수육 맛있게 먹는법', 'How to reheat leftover food',
                      'Horror Is Hollywood’s Hottest Movie Genre These Days']:
            with self.subTest(title=title):
                self.assertEqual(engine.classify_article_role(title), 'LIFESTYLE')
                self.assertFalse(engine.understand_event({'title': title})['is_real_event'])

    def test_price_only_articles_are_market_reaction(self):
        for title in ['Nvidia stock rises 5%', 'AMD stock falls after AI demand reset',
                      'Russia stocks lower at close of trade']:
            with self.subTest(title=title):
                self.assertEqual(engine.classify_article_role(title), 'MARKET_REACTION')
                self.assertFalse(engine.understand_event({'title': title})['is_real_event'])

    def test_history_based_investment_predictions_are_analysis(self):
        for title in ['History Says This Will Happen to AMD Stock in 2027',
                      'Micron Is Down 18% From Its High. History Suggests This Is What Happens Next.']:
            with self.subTest(title=title):
                self.assertEqual(engine.classify_article_role(title), 'ANALYSIS')

    def test_explanatory_titles_are_not_confirmed_events(self):
        title = 'Jeff Bezos has a blunt answer for why housing is so expensive'
        self.assertEqual(engine.classify_article_role(title), 'EXPLAINER')
        self.assertFalse(engine.understand_event({'title': title})['is_real_event'])

    def test_unclassified_text_is_only_a_candidate(self):
        self.assertEqual(engine.classify_article_role('Company announces update'), 'EVENT_CANDIDATE')
        result = engine.understand_event({'title': 'Company announces update'})
        self.assertFalse(result['is_real_event'])
        self.assertEqual(result['article_role'], 'EVENT_CANDIDATE')

    def test_clear_contract_still_reaches_event_validation(self):
        result = engine.understand_event({'title': '기가비스, 중국 업체와 111억 공급계약 체결'})
        self.assertTrue(result['is_real_event'])
        self.assertEqual(result['event_type'], 'CONTRACT')

    def test_mixed_reaction_article_keeps_confirmed_contract(self):
        for title, summary in [
            ('Nvidia stock rises 5%', 'Nvidia signed a $5 billion supply agreement with a new customer today.'),
            ('[특징주] 기가비스 급등', '기가비스는 오늘 111억원 규모 공급계약을 체결했다.'),
            ('Why company shares jumped', 'The company signed a $5 billion supply contract today.'),
        ]:
            with self.subTest(title=title):
                result = engine.understand_event({'title': title, 'summary': summary})
                self.assertTrue(result['is_real_event'])
                self.assertEqual(result['event_type'], 'CONTRACT')

    def test_mixed_reaction_keeps_actual_reported_earnings(self):
        result = engine.understand_event({
            'title': 'Broadcom Stock Falls Despite Better-Than-Expected Fiscal Q3 Results',
            'summary': 'Broadcom beat estimates for its fiscal third quarter. Broadcom stock fell.'})
        self.assertTrue(result['is_real_event'])
        self.assertEqual(result['event_type'], 'EARNINGS')

    def test_unconfirmed_or_historical_summary_does_not_override(self):
        for summary in [
            'The company expects to sign a $5 billion supply agreement.',
            'The company has not signed a supply agreement.',
            'The company denied having signed a supply agreement.',
            'The company signed no supply agreement.',
            'The company will beat estimates next quarter.',
            'Last year, the company signed a $5 billion supply agreement.',
            'The company signed a memorandum of understanding to explore a supply agreement.',
            '공급계약 체결을 검토하고 있다.',
        ]:
            with self.subTest(summary=summary):
                self.assertFalse(engine.has_confirmed_event_inside_reaction('Nvidia stock rises', summary))
                self.assertFalse(engine.understand_event({'title': 'Nvidia stock rises', 'summary': summary})['is_real_event'])

    def test_recommendations_do_not_borrow_contract_confirmation(self):
        result = engine.understand_event({'title': '3 stocks to buy now',
                                         'summary': 'Company signed a $5 billion supply agreement today.'})
        self.assertFalse(result['is_real_event'])

    def test_mixed_reaction_keeps_confirmed_investment_and_acquisition(self):
        for summary, kind in [
            ('Company announced a $3 billion investment to build a new data center.', 'CAPEX'),
            ('Company agreed to acquire a software maker for $500 million in a definitive agreement.', 'M&A'),
        ]:
            with self.subTest(kind=kind):
                result = engine.understand_event({'title': 'Company stock rises 5%', 'summary': summary})
                self.assertTrue(result['is_real_event'])
                self.assertEqual(result['event_type'], kind)

    def test_old_sentence_does_not_hide_a_separate_new_confirmation(self):
        summary = 'Last year the company signed a supply agreement. Today the company signed a new $5 billion supply contract.'
        self.assertTrue(engine.has_confirmed_event_inside_reaction('Nvidia stock rises', summary))
        self.assertTrue(engine.understand_event({'title': 'Nvidia stock rises', 'summary': summary})['is_real_event'])

    def test_financial_factory_news_is_not_lifestyle(self):
        result = engine.understand_event({'title': '화장품 기업, 500억 공장 증설 투자 결정'})
        self.assertTrue(result['is_real_event'])
        self.assertEqual(result['event_type'], 'CAPEX')

    def test_role_debug_is_off_by_default(self):
        with patch.dict(os.environ, {'ORION_DEBUG_EVENT_ROLE': '0'}), contextlib.redirect_stdout(io.StringIO()) as output:
            engine.understand_event({'title': 'Company announces update'})
        self.assertNotIn('DEBUG ARTICLE ROLE', output.getvalue())

    def test_opt_in_debug_logs_each_article_once(self):
        engine._LOGGED_ARTICLE_ROLES.clear()
        with patch.dict(os.environ, {'ORION_DEBUG_EVENT_ROLE': '1'}), contextlib.redirect_stdout(io.StringIO()) as output:
            for _ in range(3):
                engine.understand_event({'title': 'Company announces update'})
        self.assertEqual(output.getvalue().count('DEBUG ARTICLE ROLE'), 1)
        engine._LOGGED_ARTICLE_ROLES.clear()


if __name__ == '__main__':
    unittest.main()
