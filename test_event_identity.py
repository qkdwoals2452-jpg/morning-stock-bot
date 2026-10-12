import copy
import unittest

from event_engine import calc_event_score, merge_same_events
from event_identity_engine import canonical_link, event_facts, same_event
from news_engine import remove_duplicates


def article(title, source='한국경제_경제', link='https://www.hankyung.com/article/1',
            date='2026-10-12T09:00:00+09:00', summary='계약 내용을 공시했다.'):
    return dict(title=title, source=source, link=link, published_at=date,
                summary=summary, market='KR')


TITLE = '기가비스, 삼성전자와 111억원 검사장비 공급계약 체결'


class EventIdentityTests(unittest.TestCase):
    def events(self, *articles):
        return merge_same_events(copy.deepcopy(list(articles)))

    def test_different_counterparty_amount_and_product_are_separate(self):
        a = article(TITLE)
        b = article('기가비스, LG전자와 220억원 냉각장비 공급계약 체결',
                    '매일경제_기업', 'https://www.mk.co.kr/news/business/2')
        events = self.events(a, b)
        self.assertEqual(len(events), 2)
        self.assertEqual(len({e['event_key'] for e in events}), 2)
        for event in events:
            self.assertEqual(event['event_subject_key'], '기가비스_CONTRACT')
            self.assertEqual(event['source_bonus'], 0)
            self.assertEqual(event['event_score'], calc_event_score(event['articles'][0])[0])

    def test_each_known_conflicting_fact_blocks_merge(self):
        for title in [TITLE.replace('삼성전자', 'LG전자'), TITLE.replace('111억원', '112억원'),
                      TITLE.replace('검사장비', '냉각장비')]:
            with self.subTest(title=title):
                self.assertEqual(len(self.events(article(TITLE), article(title))), 2)

    def test_contract_dates_are_not_publication_dates(self):
        a = article('기가비스, 10월 11일 삼성전자와 111억원 검사장비 공급계약 체결')
        b = article('기가비스, 10월 12일 삼성전자와 111억원 검사장비 공급계약 체결')
        self.assertEqual(len(self.events(a, b)), 2)
        self.assertEqual(event_facts(article(TITLE))['event_dates'], [])

    def test_contract_years_and_locations_conflict(self):
        for suffix_a, suffix_b in [('3년간', '5년간'), ('평택공장', '울산공장')]:
            a = article(TITLE + ' ' + suffix_a)
            b = article(TITLE + ' ' + suffix_b)
            with self.subTest(suffix_a=suffix_a):
                self.assertFalse(same_event(a, b))

    def test_korean_amount_units_and_decimal_are_not_mixed(self):
        a = article(TITLE.replace('111억원', '1.11조원'))
        b = article(TITLE.replace('111억원', '11100억원'))
        self.assertEqual(event_facts(a)['amounts'], event_facts(b)['amounts'])
        self.assertTrue(same_event(a, b))
        self.assertFalse(same_event(article(TITLE.replace('111억원', '111.5억원')), article(TITLE.replace('111억원', '1115억원'))))

    def test_compound_korean_amount_is_one_amount(self):
        a = article(TITLE.replace('111억원', '1조 2000억원'))
        b = article(TITLE.replace('111억원', '1.2조원'))
        self.assertEqual(event_facts(a)['amounts'], ['KRW:1200000000000'])
        self.assertTrue(same_event(a, b))

    def test_currency_and_unknown_currency_are_kept_explicit(self):
        self.assertFalse(same_event(article(TITLE), article(TITLE.replace('111억원', '111억달러'))))
        self.assertEqual(event_facts(article(TITLE.replace('111억원', '111억')))['amounts'], ['UNKNOWN:11100000000'])
        self.assertEqual(event_facts(article('Company signs $2 billion deal with Nvidia'))['amounts'], ['USD:2000000000'])

    def test_anonymous_counterparty_does_not_establish_same_contract(self):
        a = article(TITLE.replace('삼성전자', '중국 업체'))
        b = article(TITLE.replace('삼성전자', '중국 업체'), '매일경제_기업', 'https://www.mk.co.kr/news/business/2')
        self.assertFalse(same_event(a, b))
        self.assertEqual(len(self.events(a, b)), 2)

    def test_missing_amount_does_not_bridge_two_contracts(self):
        a = article(TITLE)
        bridge = article(TITLE.replace('111억원 ', ''), '매일경제_기업', 'https://www.mk.co.kr/news/business/2')
        b = article(TITLE.replace('111억원', '220억원'), '이데일리_기업', 'https://www.edaily.co.kr/news/3')
        self.assertEqual(len(self.events(a, bridge, b)), 3)

    def test_all_group_members_must_match(self):
        a = article(TITLE)
        b = article(TITLE.replace('삼성전자', '삼성전자와 LG전자'), '매일경제_기업', 'https://www.mk.co.kr/news/business/2')
        c = article(TITLE.replace('삼성전자', 'LG전자'), '이데일리_기업', 'https://www.edaily.co.kr/news/3')
        events = self.events(a, b, c)
        self.assertEqual(len(events), 3)
        self.assertFalse(any(a['title'] in [x['title'] for x in e['articles']] and c['title'] in [x['title'] for x in e['articles']] for e in events))

    def test_generic_joined_nouns_are_not_named_counterparties(self):
        for title in ['기가비스, 검사와 공급에 111억원 투자 확정',
                      '기가비스, A사와 111억원 검사장비 공급계약 체결']:
            with self.subTest(title=title):
                self.assertEqual(event_facts(article(title))['counterparties'], [])

    def test_old_same_title_is_not_current_contract(self):
        self.assertFalse(same_event(article(TITLE), article(TITLE, date='2025-10-12T09:00:00+09:00')))

    def test_undated_articles_need_article_identifier(self):
        a, b = article(TITLE, date=''), article(TITLE, link='https://www.hankyung.com/article/2', date='')
        self.assertFalse(same_event(a, b))

    def test_same_contract_can_merge_and_get_verified_publisher_bonus(self):
        a = article(TITLE, summary='검사장비 계약금액 111억원을 공시했다.')
        b = article('기가비스, 삼성전자와 검사장비 111억원 공급계약 확정',
                    '매일경제_기업', 'https://www.mk.co.kr/news/business/2', summary='삼성전자 검사장비 납품 계약을 체결했다.')
        events = self.events(a, b)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['source_count'], 2)
        self.assertEqual(events[0]['source_bonus'], 10)
        self.assertEqual(events[0]['event_score'], min(100, max(calc_event_score(a)[0], calc_event_score(b)[0]) + 10))

    def test_two_feeds_from_same_publisher_are_one_source(self):
        a = article(TITLE)
        b = article(TITLE, '한국경제_증권', 'https://www.hankyung.com/article/2', summary='다른 요약 문장')
        event = self.events(a, b)[0]
        self.assertEqual(event['source_count'], 1)
        self.assertEqual(event['source_bonus'], 0)

    def test_copied_summary_and_missing_body_do_not_add_bonus(self):
        for summary in ['동일한 보도자료 본문', '']:
            a = article(TITLE, summary=summary)
            b = article(TITLE, '매일경제_기업', 'https://www.mk.co.kr/news/business/2', summary=summary)
            self.assertEqual(self.events(a, b)[0]['source_bonus'], 0)

    def test_unknown_source_labels_do_not_add_bonus(self):
        a = article(TITLE, 'feed_a', 'https://a.example/1', summary='요약 A')
        b = article(TITLE, 'feed_b', 'https://b.example/2', summary='요약 B')
        self.assertEqual(self.events(a, b)[0]['source_bonus'], 0)

    def test_news_stage_retains_distinct_contracts_before_event_engine(self):
        a = article(TITLE)
        b = article(TITLE.replace('111억원', '220억원'), link='https://www.hankyung.com/article/2')
        self.assertEqual(len(remove_duplicates([a, b])), 2)

    def test_only_actual_duplicate_records_are_removed(self):
        a = article(TITLE)
        b = article(TITLE, link=a['link'] + '?utm_source=rss#section')
        c = article(TITLE, link='https://www.hankyung.com/article/2')
        self.assertEqual(len(remove_duplicates([a, b, c])), 2)

    def test_article_id_query_is_not_removed(self):
        a = 'https://n.news.naver.com/article?oid=001&aid=111&utm_source=x'
        b = 'https://n.news.naver.com/article?oid=001&aid=222&utm_source=y'
        self.assertNotEqual(canonical_link(a), canonical_link(b))

    def test_identity_is_stable_when_input_order_changes(self):
        a = article(TITLE)
        b = article(TITLE, '매일경제_기업', 'https://www.mk.co.kr/news/business/2', summary='다른 본문')
        self.assertEqual(self.events(a, b)[0]['event_key'], self.events(b, a)[0]['event_key'])


if __name__ == '__main__':
    unittest.main()
