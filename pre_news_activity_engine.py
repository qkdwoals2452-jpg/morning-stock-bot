"""뉴스 이전 완료된 일별 거래활동 관측. 추천 점수에는 반영하지 않는다."""
from datetime import datetime, date, timedelta, timezone
import math
import re
from statistics import mean
from zoneinfo import ZoneInfo

import requests

SEOUL = ZoneInfo("Asia/Seoul")
KOREAN_SOURCES = ("한국경제", "매일경제", "이데일리")
HEADERS = {"User-Agent": "ORION Stock Research Bot"}


def parse_timestamp(value, source=""):
    """오프셋 없는 시간은 확인된 국내 피드만 KST로 해석하고 가정을 기록한다."""
    try:
        if not isinstance(value, datetime) and not re.search(r"[T ]\d{2}:\d{2}", str(value)):
            return None, False
        stamp = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        assumed = False
        if stamp.tzinfo is None:
            if not str(source or "").startswith(KOREAN_SOURCES):
                return None, False
            stamp, assumed = stamp.replace(tzinfo=SEOUL), True
        return stamp.astimezone(SEOUL), assumed
    except (TypeError, ValueError):
        return None, False


def number(value):
    try:
        if isinstance(value, bool) or value is None:
            return None
        result = float(str(value).replace(",", ""))
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def unavailable(status, **fields):
    return {"status": status, "volume_ratio": None, "estimated_value_ratio": None,
            "score_effect": 0, "cutoff_policy": "strict_prior_calendar_day",
            "value_method": "close_x_volume_estimate", **fields}


def analyze_pre_news_activity(rows, cutoff_at, as_of=None, baseline_sessions=20, recent_sessions=5):
    cutoff, _ = parse_timestamp(cutoff_at)
    assessed, _ = parse_timestamp(as_of or datetime.now(timezone.utc))
    if cutoff is None or assessed is None:
        return unavailable("invalid_timestamp")
    metadata = {"reference_at": cutoff.isoformat(), "analysis_as_of": assessed.isoformat()}
    if cutoff > assessed:
        return unavailable("reference_not_yet_available", **metadata)
    if (isinstance(baseline_sessions, bool) or isinstance(recent_sessions, bool)
            or not isinstance(baseline_sessions, int) or not isinstance(recent_sessions, int)
            or baseline_sessions < 1 or recent_sessions < 1):
        return unavailable("invalid_window", **metadata)
    if not isinstance(rows, list):
        return unavailable("invalid_history", **metadata)
    by_day, conflicts = {}, set()
    for row in rows:
        if not isinstance(row, dict):
            return unavailable("invalid_history", **metadata)
        raw_day = str(row.get("localDate") or row.get("date") or "")
        try:
            day = datetime.strptime(raw_day, "%Y%m%d").date() if re.fullmatch(r"[0-9]{8}", raw_day) else date.fromisoformat(raw_day)
        except ValueError:
            return unavailable("invalid_history_date", **metadata)
        # 일별 데이터만 사용하고 뉴스 당일·이후 및 실행 당일 데이터는 제외한다.
        if day >= cutoff.date() or day >= assessed.date():
            continue
        close = number(row.get("closePrice", row.get("close")))
        volume = number(row.get("accumulatedTradingVolume", row.get("volume")))
        values = (close, volume)
        if day in by_day and by_day[day] != values:
            conflicts.add(day)
        by_day[day] = values
    needed = baseline_sessions + recent_sessions
    days = sorted(by_day)[-needed:]
    metadata.update({"observed_sessions": len(days), "required_sessions": needed,
                     "session_dates": [day.isoformat() for day in days]})
    if len(days) < needed:
        return unavailable("insufficient_history", **metadata)
    if conflicts.intersection(days):
        return unavailable("conflicting_history", **metadata)
    window = [by_day[day] for day in days]
    if any(close is None or close <= 0 or volume is None or volume < 0 or not volume.is_integer()
           for close, volume in window):
        return unavailable("invalid_window_data", **metadata)
    values = [close * volume for close, volume in window]
    if not all(math.isfinite(value) for value in values):
        return unavailable("invalid_window_data", **metadata)
    volumes = [volume for _, volume in window]
    base_volume, recent_volume = mean(volumes[:baseline_sessions]), mean(volumes[baseline_sessions:])
    base_value, recent_value = mean(values[:baseline_sessions]), mean(values[baseline_sessions:])
    metadata.update({"baseline_sessions": baseline_sessions, "recent_sessions": recent_sessions,
                     "baseline_dates": [day.isoformat() for day in days[:baseline_sessions]],
                     "recent_dates": [day.isoformat() for day in days[baseline_sessions:]],
                     "baseline_avg_volume": base_volume, "recent_avg_volume": recent_volume,
                     "baseline_avg_estimated_value": base_value, "recent_avg_estimated_value": recent_value,
                     "last_session_date": days[-1].isoformat()})
    if base_volume <= 0 or base_value <= 0:
        return unavailable("zero_baseline", **metadata)
    volume_ratio, value_ratio = recent_volume / base_volume, recent_value / base_value
    if not math.isfinite(volume_ratio) or not math.isfinite(value_ratio):
        return unavailable("invalid_window_data", **metadata)
    return {**unavailable("ok", **metadata),
            "volume_ratio": round(volume_ratio, 4),
            "estimated_value_ratio": round(value_ratio, 4)}


def fetch_daily_activity(code, cutoff_at, cache=None):
    if not re.fullmatch(r"[0-9]{6}", str(code)) or code == "000000":
        return None, "invalid_code"
    end = cutoff_at.date() - timedelta(days=1)
    key = (code, end.isoformat())
    if cache is not None and key in cache:
        return cache[key]
    try:
        res = requests.get(f"https://api.stock.naver.com/chart/domestic/item/{code}/day",
                           headers=HEADERS, params={
                               "startDateTime": (end - timedelta(days=120)).strftime("%Y%m%d"),
                               "endDateTime": end.strftime("%Y%m%d")}, timeout=(10, 20))
        res.raise_for_status()
        rows = res.json()
        result = (rows, None) if isinstance(rows, list) else (None, "invalid_history")
    except (requests.RequestException, ValueError):
        result = (None, "history_unavailable")
    if cache is not None:
        cache[key] = result
    return result


def get_pre_news_activity(stock, connection, as_of=None, cache=None):
    assessed, _ = parse_timestamp(as_of or datetime.now(timezone.utc))
    if assessed is None:
        return unavailable("invalid_timestamp")
    if not isinstance(connection, dict) or not connection.get("pass"):
        return unavailable("unverified_event_connection")
    if not isinstance(connection.get("evidence"), list):
        return unavailable("missing_news_timestamp")
    references = []
    for proof in connection.get("evidence", []):
        if not isinstance(proof, dict):
            return unavailable("missing_news_timestamp")
        stamp, assumed = parse_timestamp(proof.get("published_at"), proof.get("source", ""))
        if stamp is None:
            # 더 이른 기사일 수 있으므로 누락된 시각을 무시하고 뒤의 기사로 기준을 옮기지 않는다.
            return unavailable("missing_news_timestamp")
        if stamp > assessed:
            return unavailable("reference_not_yet_available")
        references.append((stamp, assumed, proof))
    if not references:
        return unavailable("missing_news_timestamp")
    stamp, assumed, proof = min(references, key=lambda row: row[0])
    rows, error = fetch_daily_activity(stock.get("code"), stamp, cache)
    result = unavailable(error) if error else analyze_pre_news_activity(rows, stamp, assessed)
    result.update({"reference_at": stamp.isoformat(), "analysis_as_of": assessed.isoformat(),
                   "reference_scope": "earliest_available_linked_article",
                   "news_link": proof.get("link", ""), "news_source": proof.get("source", ""),
                   "news_timezone_assumed_kst": assumed, "data_source": "NAVER_daily_chart",
                   "observation_recorded_at": datetime.now(timezone.utc).isoformat()})
    return result
