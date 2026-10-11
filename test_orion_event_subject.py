import unittest
import ast
from pathlib import Path
from event_engine import make_event_key, merge_same_events
from event_understanding_engine import understand_event

class EventSubjectKeyTests(unittest.TestCase):
    def test_facility_not_supplier(self):
        key = make_event_key({"title": "신한울 원전에 구동기 공급…국산 기술로 해외 공략"})
        self.assertTrue(key.startswith("UNKNOWN_"), key)
        self.assertTrue(key.endswith("_CONTRACT"), key)

    def test_named_supplier(self):
        key = make_event_key({"title": "기가비스, 중국 반도체 기판 업체와 111억 검사장비 공급계약"})
        self.assertEqual(key, "기가비스_CONTRACT")

    def test_named_supplier_with_facility_customer(self):
        key = make_event_key({"title": "기가비스, 신한울 원전에 구동기 공급계약 체결"})
        self.assertEqual(key, "기가비스_CONTRACT")

    def test_whitespace_and_fullwidth_comma(self):
        key = make_event_key({"title": "  기가비스 ， 중국 업체와 검사장비 공급계약 체결"})
        self.assertEqual(key, "기가비스_CONTRACT")

    def test_other_facilities_not_suppliers(self):
        for title in [
            "반도체 공장에 검사장비 공급계약 체결",
            "산업 시설에 구동기 공급계약 체결",
            "AI 데이터센터에 냉각장비 공급계약 체결",
            "신한울 원전에서 구동기 공급계약 체결",
        ]:
            with self.subTest(title=title):
                key = make_event_key({"title": title})
                self.assertTrue(key.startswith("UNKNOWN_"), key)
                self.assertTrue(key.endswith("_CONTRACT"), key)

    def test_different_unidentified_suppliers_are_not_merged(self):
        events = merge_same_events([
            {"title": "신한울 원전에 구동기 공급계약 체결", "source": "a"},
            {"title": "신한울 원전에 냉각장비 공급계약 체결", "source": "b"},
        ])
        self.assertEqual(len(events), 2)
        self.assertTrue(all(event['event_key'].startswith('UNKNOWN_') for event in events))

    def test_same_named_supplier_articles_are_merged(self):
        events = merge_same_events([
            {"title": "기가비스, 중국 업체와 검사장비 공급계약 체결", "source": "a"},
            {"title": "기가비스, 중국 업체에 111억 검사장비 공급계약", "source": "b"},
        ])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['event_key'], '기가비스_CONTRACT')
        self.assertEqual(events[0]['source_count'], 2)

    def test_capex_subjects_preserved(self):
        for title, expected in [
            ("포스코DX, 인핸스에 20억 투자", "포스코DX_CAPEX"),
            ("엔비디아 수요 대응…심텍, 증설 결정", "심텍_CAPEX"),
        ]:
            with self.subTest(title=title):
                self.assertEqual(make_event_key({'title': title}), expected)

    def test_existing_event_fixtures_without_live_network(self):
        # 기존 테스트 파일을 import하면 LIVE RSS 호출이 실행되므로 사례만 읽는다.
        tree = ast.parse(Path(__file__).with_name('orion_event_test.py').read_text())
        cases = next(ast.literal_eval(node.value) for node in tree.body
                     if isinstance(node, ast.Assign)
                     and any(isinstance(target, ast.Name) and target.id == 'TEST_CASES'
                             for target in node.targets))
        for case in cases:
            with self.subTest(case=case['id'], title=case['title']):
                result = understand_event({'title': case['title'],
                                           'summary': case.get('summary', '')})
                self.assertEqual((result['is_real_event'], result['event_type']),
                                 (case['expected_event'], case['expected_type']))

if __name__ == "__main__":
    unittest.main()
