import unittest
from event_engine import make_event_key

class EventSubjectKeyTests(unittest.TestCase):
    def test_facility_not_treated_as_supplier(self):
        article = {"title": "신한울 원전에 구동기 공급…국산 기술로 해외 공략"}
        key = make_event_key(article)
        self.assertTrue(key.startswith("UNKNOWN_"), key)
        self.assertTrue(key.endswith("_CONTRACT"), key)

    def test_named_supplier_kept(self):
        article = {"title": "기가비스, 중국 반도체 기판 업체와 111억 검사장비 공급계약"}
        self.assertEqual(make_event_key(article), "기가비스_CONTRACT")

if __name__ == "__main__":
    unittest.main()
