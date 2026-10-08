import datetime
import json
import os
import cloudscraper
from bs4 import BeautifulSoup

# 目標飛機列表
AIRCRAFT_LIST = ["HL8717", "HL8599", "HL8759", "HL8543", "HL8544"]

def fetch_aircraft_data(scraper, aircraft_id):
    url = f"https://www.flightradar24.com/data/aircraft/{aircraft_id.lower()}"
    response = scraper.get(url, timeout=30)
    
    flights = []
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        # 尋找表格列
        rows = soup.find_all('tr', class_='data-row')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 7:
                date = cols[2].get_text(strip=True)
                from_city = cols[3].get_text(strip=True)
                to_city = cols[4].get_text(strip=True)
                flight_no = cols[5].get_text(strip=True)
                flight_time = cols[6].get_text(strip=True)
                
                if date and flight_no:
                    flights.append({
                        "date": date,
                        "from": from_city,
                        "to": to_city,
                        "flight": flight_no,
                        "flight_time": flight_time
                    })
    else:
        print(f"  {aircraft_id} HTTP {response.status_code}")
    return flights

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
    scraper = cloudscraper.create_scraper()
    result = {
        "last_updated": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    }
    
    ok = 0
    for aircraft in AIRCRAFT_LIST:
        print(f"正在抓取 {aircraft} 資料...")
        try:
            flights = fetch_aircraft_data(scraper, aircraft)
        except Exception as e:
            print(f"  {aircraft} 抓取失敗：{e}")
            flights = []
        if flights:
            ok += 1
        else:
            # 抓不到（被擋/逾時）時保留上一次的資料，避免網頁變空白
            flights = previous.get(aircraft, [])
            print(f"  {aircraft} 沿用舊資料（{len(flights)} 筆）")
        result[aircraft] = flights
    
    if ok == 0:
        # 全部失敗就不寫檔，last_updated 也不更新，避免顯示假的「已更新」
        raise SystemExit("全部飛機都抓取失敗，本次不更新 data.json")
        
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
