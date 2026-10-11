import unittest
from unittest.mock import patch, Mock
import backtest_engine as bt

class TradingCheckpointTests(unittest.TestCase):
    def test_skips_weekend_and_uses_trading_sessions(self):
        item = {"date": "2026-10-02", "start_price": 100,
                "result_1d": None, "result_3d": None, "result_5d": None,
                "result_10d": None, "result_20d": None}
        dates = ["2026-10-05", "2026-10-06", "2026-10-07",
                 "2026-10-08", "2026-10-09"]
        self.assertEqual(bt.fill_trading_checkpoints(item, list(zip(dates, [110, 120, 130, 140, 150]))), 3)
        self.assertEqual(item["result_1d"], 10)
        self.assertEqual(item["result_3d"], 30)
        self.assertEqual(item["result_5d"], 50)
        self.assertIsNone(item["result_10d"])

    def test_no_future_session_does_not_fill(self):
        item = {"date": "2026-10-10", "start_price": 100, "result_1d": None}
        self.assertEqual(bt.fill_trading_checkpoints(item, [("2026-10-09", 150)]), 0)

    def test_historical_response_is_parsed(self):
        sample = {"chart": {"result": [{"timestamp": [1791244800],
            "indicators": {"quote": [{"close": [123.0]}]}}]}}
        response = Mock()
        response.json.return_value = sample
        with patch.object(bt.requests, "get", return_value=response):
            result = bt.fetch_daily_closes("005930")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1], 123.0)

if __name__ == "__main__":
    unittest.main()
