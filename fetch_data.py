import datetime
import json
import cloudscraper
from bs4 import BeautifulSoup

# 目標飛機列表
AIRCRAFT_LIST = ["HL8717", "HL8599", "HL8759", "HL8543", "HL8544"]

def fetch_aircraft_data(aircraft_id):
    url = f"https://www.flightradar24.com/data/aircraft/{aircraft_id.lower()}"
    scraper = cloudscraper.create_scraper()
    response = scraper.get(url)
    
    flights = []
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        # 尋找表格列
        rows = soup.find_all('tr', class_='data-row')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 6:
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
    return flights

def main():
    result = {
        "last_updated": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    }
    
    for aircraft in AIRCRAFT_LIST:
        print(f"正在抓取 {aircraft} 資料...")
        result[aircraft] = fetch_aircraft_data(aircraft)
        
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
