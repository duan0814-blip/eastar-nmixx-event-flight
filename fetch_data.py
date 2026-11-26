import datetime
import json
import os
import time

from curl_cffi import requests

# 目標飛機列表
AIRCRAFT_LIST = ["HL8717", "HL8599", "HL8759", "HL8543", "HL8544"]

# 2026-11 起 Flightradar24 機號頁改成前端渲染，HTML 裡已沒有航班表格，
# 改抓網頁本身在用的 JSON API；用 curl_cffi 模擬 Chrome 的 TLS 指紋以通過 Cloudflare
API_URL = "https://api.flightradar24.com/common/v1/flight/list.json"
HEADERS = {
    "Referer": "https://www.flightradar24.com/",
    "Origin": "https://www.flightradar24.com",
    "Accept": "application/json",
}


def airport_label(ap):
    """轉成跟舊網頁表格一樣的格式，例如 Tokyo(NRT)"""
    if not ap:
        return "—"
    iata = (ap.get("code") or {}).get("iata") or ""
    city = ((ap.get("position") or {}).get("region") or {}).get("city") or ap.get("name") or ""
    if city and iata:
        return f"{city}({iata})"
    return city or iata or "—"


def fmt_duration(dep, arr):
    if not dep or not arr or arr <= dep:
        return "—"
    mins = (arr - dep) // 60
    return f"{mins // 60}:{mins % 60:02d}"


def fetch_aircraft_data(aircraft_id):
    params = {"query": aircraft_id.lower(), "fetchBy": "reg", "page": 1, "limit": 100}
    response = requests.get(API_URL, params=params, headers=HEADERS,
                            impersonate="chrome", timeout=30)
    if response.status_code != 200:
        print(f"  {aircraft_id} HTTP {response.status_code}")
        return []

    data = ((response.json().get("result") or {}).get("response") or {}).get("data") or []
    flights = []
    for f in data:
        t = f.get("time") or {}
        sched = t.get("scheduled") or {}
        real = t.get("real") or {}
        dep_ts = real.get("departure") or sched.get("departure")
        flight_no = ((f.get("identification") or {}).get("number") or {}).get("default")
        if not dep_ts or not flight_no:
            continue
        # FR24 表格的 DATE 是 UTC 日期，跟舊資料一致
        date = datetime.datetime.fromtimestamp(dep_ts, datetime.timezone.utc).strftime("%d %b %Y")
        ap = f.get("airport") or {}
        flights.append({
            "date": date,
            "from": airport_label(ap.get("origin")),
            "to": airport_label(ap.get("destination")),
            "flight": flight_no,
            "flight_time": fmt_duration(real.get("departure"), real.get("arrival")),
        })
    return flights


def row_quality(r):
    """資料完整度：起降地、飛行時間都有值的分數較高；亂碼（�）視為無值"""
    def good(v):
        return bool(v) and v != "—" and "�" not in v
    return good(r.get("from")) + good(r.get("to")) + good(r.get("flight_time"))


def merge_history(new_rows, old_rows):
    """FR24 只提供最近約 7 天，所以把新抓到的跟舊資料合併，累積完整歷史。
    以（日期, 航班）去重，同一筆保留較完整的版本（同分以新抓的為準），依日期新到舊排序"""
    merged = {}
    order = []
    for r in list(new_rows) + list(old_rows):
        k = (r["date"], r["flight"])
        if k not in merged:
            merged[k] = r
            order.append(k)
        elif row_quality(r) > row_quality(merged[k]):
            merged[k] = r
    rows = [merged[k] for k in order]

    def day(r):
        try:
            return datetime.datetime.strptime(r["date"], "%d %b %Y")
        except ValueError:
            return datetime.datetime.min
    rows.sort(key=day, reverse=True)  # 穩定排序，同一天內維持原本順序
    return rows


def load_previous():
    if os.path.exists("data.json"):
        try:
            with open("data.json", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            pass
    return {}


def main():
    previous = load_previous()
    result = {
        "last_updated": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    }

    ok = 0
    for i, aircraft in enumerate(AIRCRAFT_LIST):
        if i:
            time.sleep(2)  # 避免連續請求被限流
        print(f"正在抓取 {aircraft} 資料...")
        try:
            flights = fetch_aircraft_data(aircraft)
        except Exception as e:
            print(f"  {aircraft} 抓取失敗：{e}")
            flights = []
        old = previous.get(aircraft, [])
        if flights:
            ok += 1
            print(f"  {aircraft} 取得 {len(flights)} 筆")
            flights = merge_history(flights, old)
        else:
            # 抓不到（被擋/逾時）時保留上一次的資料，避免網頁變空白
            flights = old
            print(f"  {aircraft} 沿用舊資料（{len(flights)} 筆）")
        result[aircraft] = flights

    if ok == 0:
        # 全部失敗就不寫檔，last_updated 也不更新，避免顯示假的「已更新」
        raise SystemExit("全部飛機都抓取失敗，本次不更新 data.json")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
