from datetime import date, datetime, timedelta, timezone
import unittest
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import requests

import chart_engine as chart


KST = ZoneInfo("Asia/Seoul")


def row(day, close, **extra):
    return {"localDate": day.replace("-", ""), "closePrice": close,
            "highPrice": close + 10, "lowPrice": close - 10,
            "accumulatedTradingVolume": 0, **extra}


def response(rows, symbol="009150.KS"):
    if isinstance(rows, dict):
        rows = rows.get("priceInfos") or rows.get("data") or []
    stamps = [int(datetime.strptime(x["localDate"], "%Y%m%d").replace(tzinfo=KST).timestamp())
              for x in rows]
    quote = {key: [x.get(field) for x in rows] for key, field in (
        ("close", "closePrice"), ("high", "highPrice"), ("low", "lowPrice"),
        ("volume", "accumulatedTradingVolume"))}
    payload = {"chart": {"result": [{"meta": {
        "symbol": symbol, "currency": "KRW", "exchangeTimezoneName": "Asia/Seoul",
        "dataGranularity": "1d"}, "timestamp": stamps,
        "indicators": {"quote": [quote]}}]}}
    return Mock(json=lambda: payload)


class ChartHistoryTests(unittest.TestCase):
    def broken_historical_close(self):
        return chart._normalize_price_history([
            row('2026-03-26', 11530, highPrice=11920, lowPrice=11500),
            row('2026-03-27', 11530, highPrice=11500, lowPrice=10930,
                accumulatedTradingVolume=4167020),
            row('2026-10-22', 7230)], date(2026, 3, 1), date(2026, 10, 22),
            'YAHOO_REGULAR_CLOSE')

    def secondary_response(self, *, code='034220', day='20260327', high=11500,
                           low=10930, close=11500, volume=4167020):
        return Mock(text=f'<protocol><chartdata symbol="{code}" timeframe="day">'
                         f'<item data="{day}|11350|{high}|{low}|{close}|{volume}" />'
                         '</chartdata></protocol>')

    def test_actual_repeated_close_repaired_with_original_preserved(self):
        original = self.broken_historical_close()
        with patch.object(chart.requests, 'get', return_value=self.secondary_response()):
            repaired = chart._repair_repeated_historical_close('034220', original)
        self.assertIsNone(original[1]['high'])
        self.assertEqual(original[1]['close'], 11530)
        self.assertEqual(repaired[1]['close'], 11500)
        self.assertEqual(repaired[1]['high'], 11500)
        self.assertEqual(repaired[1]['price_correction']['original'], original[1])
        self.assertEqual(repaired[-1], original[-1])
        with patch.object(chart.requests, 'get') as get:
            self.assertEqual(chart._repair_repeated_historical_close('034220', repaired), repaired)
            get.assert_not_called()

    def test_production_history_path_repairs_once_and_caches_same_regular_quote(self):
        records = [row('2026-03-26', 11530, highPrice=11920, lowPrice=11500),
                   row('2026-03-27', 11530, highPrice=11500, lowPrice=10930,
                       accumulatedTradingVolume=4167020), row('2026-10-22', 7230)]
        cache = {}
        now = datetime(2026, 10, 23, 7, tzinfo=KST)
        with patch.object(chart.requests, 'get', side_effect=[
                response(records, symbol='034220.KS'), self.secondary_response()]) as get:
            result = chart.get_price_history('034220', now=now, cache=cache)
            self.assertIs(chart.get_price_history('034220', now=now, cache=cache), result)
            self.assertEqual(get.call_count, 2)
        self.assertEqual(result[1]['close'], 11500)
        self.assertEqual(result[1]['high'], 11500)
        self.assertEqual(result[-1]['close'], 7230)
        self.assertEqual(result[-1]['source'], 'YAHOO_REGULAR_CLOSE')

    def test_secondary_must_match_symbol_date_high_low_and_volume(self):
        for change in ({'code': '009150'}, {'day': '20260326'}, {'high': 11510},
                       {'low': 10920}, {'volume': 4167021}, {'close': 11530}):
            with self.subTest(change=change):
                original = self.broken_historical_close()
                with patch.object(chart.requests, 'get', return_value=self.secondary_response(**change)):
                    self.assertEqual(chart._repair_repeated_historical_close('034220', original), original)

    def test_secondary_failure_does_not_guess_high_or_close(self):
        for exc in (requests.Timeout(), ValueError('invalid XML')):
            original = self.broken_historical_close()
            with patch.object(chart.requests, 'get', side_effect=exc):
                self.assertEqual(chart._repair_repeated_historical_close('034220', original), original)
                self.assertIsNone(original[1]['high'])

    def test_latest_or_non_repeated_bad_close_is_not_replaced(self):
        for records in (self.broken_historical_close()[:2], self.broken_historical_close()):
            if len(records) == 3:
                records[0]['close'] = 11600
            with patch.object(chart.requests, 'get') as get:
                self.assertEqual(chart._repair_repeated_historical_close('034220', records), records)
                get.assert_not_called()

    def test_crosschecked_close_restores_52_week_calculation_in_real_history_shape(self):
        start = date(2026, 3, 1)
        records = [row((start + timedelta(days=i)).isoformat(), 11000,
                       highPrice=12000, lowPrice=10000) for i in range(160)]
        records[25] = row('2026-03-26', 11530, highPrice=11920, lowPrice=11500)
        records[26] = row('2026-03-27', 11530, highPrice=11500, lowPrice=10930,
                          accumulatedTradingVolume=4167020)
        history = chart._normalize_price_history(records, start, date(2026, 10, 22),
                                                  'YAHOO_REGULAR_CLOSE')
        with patch.object(chart.requests, 'get', return_value=self.secondary_response()):
            repaired = chart._repair_repeated_historical_close('034220', history)
        with patch.object(chart, 'get_price_history', return_value=repaired):
            result = chart.get_chart_score({'code': '034220'})
        self.assertEqual(result['details']['high_52w'], 12000)
        self.assertEqual(result['details']['high_52w_gap'], -8.33)
        self.assertEqual(result['details']['high_52w_invalid_dates'], [])
        self.assertEqual(result['details']['price_corrections'][0]['original']['close'], 11530)

    def history(self, rows, now=None):
        with patch.object(chart.requests, "get", return_value=response(rows)):
            return chart.get_price_history("009150", now=now or datetime(2026, 10, 22, 6, tzinfo=KST))

    def test_reversed_rows_use_latest_date_not_last_position(self):
        rows = [row("2026-10-21", 1184000), row("2026-10-20", 1125000)]
        result = self.history(rows)
        self.assertEqual([x["date"] for x in result], ["2026-10-20", "2026-10-21"])
        self.assertEqual(result[-1]["close"], 1184000)
        self.assertEqual(result[-1]["source"], "YAHOO_REGULAR_CLOSE")
        self.assertEqual(result[-1]["volume"], 0)

    def test_current_unfinished_and_future_rows_are_excluded(self):
        result = self.history([row("2026-10-21", 100), row("2026-10-22", 200),
                               row("2026-10-23", 300)])
        self.assertEqual([x["close"] for x in result], [100])

    def test_kst_boundary_uses_same_rule_for_utc_clock(self):
        rows = [row("2026-10-21", 100), row("2026-10-22", 200)]
        for now, expected in [(datetime(2026, 10, 22, 6, 29, tzinfo=timezone.utc), 100),
                              (datetime(2026, 10, 22, 6, 30, tzinfo=timezone.utc), 200)]:
            with self.subTest(now=now):
                self.assertEqual(self.history(rows, now)[-1]["close"], expected)

    def test_identical_duplicate_day_counts_once(self):
        record = row("2026-10-21", 100)
        self.assertEqual(len(self.history([record, dict(record)])), 1)

    def test_conflicting_duplicate_day_cannot_change_average(self):
        self.assertEqual(self.history([row("2026-10-21", 100), row("2026-10-21", 200)]), [])

    def test_undated_or_invalid_date_cannot_supply_current_price(self):
        for stamp in (None, "20260230", "2026102", 20261021):
            with self.subTest(stamp=stamp):
                with self.assertRaises(ValueError):
                    chart._normalize_price_history([row("2026-10-21", 100, localDate=stamp)],
                        date(2025, 9, 1), date(2026, 10, 21), "fixture")

    def test_invalid_close_cannot_reach_trend_gate(self):
        for price in (None, 0, -1, True, "NaN", "inf", "unknown"):
            record = row("2026-10-21", 100, closePrice=price)
            with self.subTest(price=price):
                self.assertEqual(self.history([record]), [])

    def test_inconsistent_ohlc_is_not_used(self):
        for extra, key in (({"highPrice": 90}, "high"), ({"lowPrice": 110}, "low"),
                           ({"highPrice": "inf"}, "high"), ({"accumulatedTradingVolume": -1}, "volume")):
            with self.subTest(extra=extra):
                result = self.history([row("2026-10-21", 100, **extra)])
                self.assertEqual(result[-1]["close"], 100)
                self.assertIsNone(result[-1][key])

    def test_kosdaq_symbol_is_validated_after_kospi_http_failure(self):
        failed = Mock()
        failed.raise_for_status.side_effect = requests.HTTPError("503")
        kosdaq = response([row("2026-10-21", 100)], symbol="009150.KQ")
        with patch.object(chart.requests, "get", side_effect=[failed, kosdaq]):
            result = chart.get_price_history("009150", now=datetime(2026, 10, 22, 6, tzinfo=KST))
        failed.json.assert_not_called()
        self.assertEqual(result[-1]["source"], "YAHOO_REGULAR_CLOSE")

    def test_conflicting_primary_can_use_valid_dated_fallback(self):
        first = response([row("2026-10-21", 100), row("2026-10-21", 200)])
        second = response([row("2026-10-21", 100)], symbol="009150.KQ")
        with patch.object(chart.requests, "get", side_effect=[first, second]):
            result = chart.get_price_history("009150", now=datetime(2026, 10, 22, 6, tzinfo=KST))
        self.assertEqual(result[-1]["source"], "YAHOO_REGULAR_CLOSE")

    def test_only_latest_260_dates_are_retained_after_sorting(self):
        end = date(2026, 10, 21)
        records = [row((end - timedelta(days=i)).isoformat(), 100 + i) for i in range(300)]
        result = self.history(records)
        self.assertEqual(len(result), 260)
        self.assertEqual(result[0]["date"], (end - timedelta(days=259)).isoformat())
        self.assertEqual(result[-1]["date"], end.isoformat())

    def test_chart_score_uses_sorted_completed_dates_and_records_provenance(self):
        end = date(2026, 10, 21)
        records = [row((end - timedelta(days=119 - i)).isoformat(), 100 + i)
                   for i in range(120)]
        records = list(reversed(records)) + [row("2026-10-22", 10000)]
        clock = datetime(2026, 10, 22, 6, tzinfo=KST)
        with patch.object(chart.requests, "get", return_value=response(records)), patch.object(
            chart, "datetime", wraps=datetime
        ) as mocked_clock:
            mocked_clock.now.return_value = clock
            result = chart.get_chart_score({"code": "009150", "name": "삼성전기"})
        self.assertEqual(result["details"]["current"], 219)
        self.assertEqual(result["details"]["ma120"], 159.5)
        self.assertEqual(result["details"]["price_date"], "2026-10-21")
        self.assertEqual(result["details"]["price_source"], "YAHOO_REGULAR_CLOSE")
        self.assertTrue(chart.pass_long_term_trend(result)[0])

    def test_unknown_response_shape_and_invalid_code_fail_closed(self):
        for payload in (None, "error", {"data": {}}, ["row"]):
            with self.subTest(payload=payload), patch.object(chart.requests, "get",
                    return_value=Mock(json=lambda: payload)):
                self.assertEqual(chart.get_price_history("009150"), [])
        with patch.object(chart.requests, "get") as request:
            for code in ("9150", "000000", "009150.KS", 9150, None):
                self.assertEqual(chart.get_price_history(code), [])
            request.assert_not_called()

    def test_wrong_symbol_currency_timezone_or_interval_cannot_be_used(self):
        for key, value in (("symbol", "005930.KS"), ("currency", "USD"),
                           ("exchangeTimezoneName", "UTC"), ("dataGranularity", "1m")):
            payload = response([row("2026-10-21", 1168000)]).json()
            payload["chart"]["result"][0]["meta"][key] = value
            with self.subTest(key=key), patch.object(chart.requests, "get",
                    return_value=Mock(json=lambda: payload)):
                self.assertEqual(chart.get_price_history("009150"), [])

    def test_regular_close_does_not_use_after_market_meta_price(self):
        payload = response([row("2026-10-21", 1168000)]).json()
        payload["chart"]["result"][0]["meta"]["regularMarketPrice"] = 1184000
        with patch.object(chart.requests, "get", return_value=Mock(json=lambda: payload)) as get:
            result = chart.get_price_history("009150", now=datetime(2026, 10, 22, 6, tzinfo=KST))
        self.assertEqual(result[-1]["close"], 1168000)
        self.assertEqual(get.call_args.kwargs["params"]["includePrePost"], "false")

    def test_failure_does_not_fall_back_to_unverified_naver_price(self):
        with patch.object(chart.requests, "get", side_effect=requests.Timeout()) as get:
            self.assertEqual(chart.get_price_history("009150"), [])
        self.assertEqual(get.call_count, 2)
        self.assertTrue(all("finance.yahoo.com" in call.args[0] for call in get.call_args_list))

    def test_misaligned_arrays_cannot_distort_moving_average(self):
        payload = response([row("2026-10-21", 100)]).json()
        payload["chart"]["result"][0]["indicators"]["quote"][0]["close"] = []
        with self.assertRaises(ValueError):
            chart._regular_session_rows(payload, "009150.KS")

    def test_null_outside_used_260_days_does_not_block_recent_prices(self):
        end = date(2026, 10, 21)
        records = [row((end - timedelta(days=i)).isoformat(), 100) for i in range(264)]
        records[-1]["closePrice"] = None
        self.assertEqual(len(self.history(records)), 260)
        records[0]["closePrice"] = None
        self.assertEqual(self.history(records), [])

    def test_inconsistent_high_does_not_manufacture_52_week_gap(self):
        end = date(2026, 10, 21)
        records = [row((end - timedelta(days=i)).isoformat(), 100) for i in range(120)]
        records[20]["highPrice"] = 90
        with patch.object(chart, "get_price_history", return_value=self.history(records)):
            result = chart.get_chart_score({"code": "009150"})
        self.assertEqual(result["details"]["ma120"], 100)
        self.assertIsNone(result["details"]["high_52w_gap"])

    def test_actual_high_contradiction_preserves_raw_values_and_date(self):
        result = self.history([row("2026-03-27", 457000,
                                   highPrice=438500, lowPrice=430000)])
        self.assertIsNone(result[0]["high"])
        self.assertEqual(result[0]["raw_high"], 438500)
        self.assertEqual(result[0]["close"], 457000)
        self.assertEqual(result[0]["date"], "2026-03-27")
        self.assertIn("high_below_close", result[0]["quality_issues"])

    def test_high_window_excludes_older_peak_and_missing_high(self):
        end = date(2026, 10, 21)
        records = [row((end - timedelta(days=i * 3)).isoformat(), 100)
                   for i in range(130)]
        records[-1]["highPrice"] = 10000
        records[-2]["highPrice"] = None
        with patch.object(chart, "get_price_history", return_value=self.history(records)):
            result = chart.get_chart_score({"code": "009150"})
        self.assertEqual(result["details"]["high_52w"], 110)
        self.assertEqual(result["details"]["high_52w_invalid_dates"], [])
        self.assertEqual(result["details"]["high_52w_start_exclusive"], "2025-10-22")
        self.assertEqual(result["details"]["high_52w_end"], "2026-10-21")

    def test_missing_high_inside_window_keeps_gap_unknown_with_date(self):
        end = date(2026, 10, 21)
        records = [row((end - timedelta(days=i)).isoformat(), 100) for i in range(120)]
        records[20]["highPrice"] = None
        with patch.object(chart, "get_price_history", return_value=self.history(records)):
            result = chart.get_chart_score({"code": "009150"})
        self.assertIsNone(result["details"]["high_52w"])
        self.assertIsNone(result["details"]["high_52w_gap"])
        self.assertEqual(result["details"]["high_52w_invalid_dates"], ["2026-10-01"])

    def test_high_window_boundary_is_exclusive(self):
        end = date(2026, 10, 21)
        records = [row((end - timedelta(days=i * 3)).isoformat(), 100)
                   for i in range(120)]
        records += [row("2025-10-22", 100, highPrice=10000),
                    row("2025-10-23", 100, highPrice=200)]
        with patch.object(chart, "get_price_history", return_value=self.history(records)):
            result = chart.get_chart_score({"code": "009150"})
        self.assertEqual(result["details"]["high_52w"], 200)


if __name__ == "__main__":
    unittest.main()


class ChartSessionGuardTests(unittest.TestCase):
    def test_unlabelled_auxiliary_cannot_repair_after_session_change(self):
        for day in ('2026-09-14', '2026-10-20'):
            records = [row('2026-09-01', 11530),
                       row(day,11530,highPrice=11500,lowPrice=10930,
                           accumulatedTradingVolume=4167020),row('2026-10-29',7230)]
            history=chart._normalize_price_history(records,date(2026,9,1),date(2026,10,29),'YAHOO_REGULAR_CLOSE')
            with patch.object(chart.requests,'get') as get:
                self.assertEqual(chart._repair_repeated_historical_close('034220',history),history)
                get.assert_not_called()
            self.assertIsNone(history[1]['high'])

    def test_rejection_evidence_retains_date_price_and_averages(self):
        details={'price_date':'2026-10-29','price_source':'YAHOO_REGULAR_CLOSE',
                 'current':155200,'ma120':201082.5,'high_52w':438000,'high_52w_gap':-64.57}
        result=chart.chart_rejection_evidence({'details':details})
        self.assertEqual(result,details)
        result['current']=1
        self.assertEqual(details['current'],155200)
        self.assertIsNone(chart.chart_rejection_evidence({'details':{'current':float('nan'),'ma120':True}})['current'])

    def test_followup_explains_chart_rejection_with_same_snapshot(self):
        from breaking_news import followup
        message=followup({'event_title':'검증 사건'},[],{'analysis_status':{
            'analyzed_count':1,'selected_count':0,'excluded':[{
                'name':'LG전자','code':'066570','reason':'52주 고점 대비 -60% 이하',
                'evidence':{'price_date':'2026-10-29','current':155200,
                            'ma120':201082.5,'high_52w':438000,'high_52w_gap':-64.57}}]}})
        for value in ('2026-10-29','155,200원','201,082.50원','438,000원','-64.57%'):
            self.assertIn(value,message)
