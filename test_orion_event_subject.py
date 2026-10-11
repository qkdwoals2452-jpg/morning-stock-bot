import unittest
from event_engine import make_event_key

class EventSubjectKeyTests(unittest.TestCase):
    def test_facility_not_supplier(self):
        key = make_event_key({"title": "신한울 원전에 구동기 공급…국산 기술로 해외 공략"})
        self.assertTrue(key.startswith("UNKNOWN_"), key)
        self.assertTrue(key.endswith("_CONTRACT"), key)

    def test_named_supplier(self):
        key = make_event_key({"title": "기가비스, 중국 반도체 기판 업체와 111억 검사장비 공급계약"})
        self.assertEqual(key, "기가비스_CONTRACT")

if __name__ == "__main__":
    unittest.main()
