import pandas as pd
import requests
from datetime import datetime, timedelta
import os
import re

# 현재 스크립트의 디렉토리 경로를 가져옴
script_dir = os.path.dirname(os.path.abspath(__file__))

# 날짜와 시간을 밀리초 타임스탬프로 변환하는 함수
def datetime_to_ms_timestamp(dt):
    epoch = datetime(1970, 1, 1)
    timestamp = int((dt - epoch).total_seconds() * 1000)
    return timestamp

# URL에서 마켓 이름과 시간 추출하는 함수
def extract_market_and_time(url):
    # 마켓 이름 추출 (BTC-USD-95000-C 형식)
    market_match = re.search(r'market=([^&]+)', url)
    market = market_match.group(1) if market_match else "unknown-market"
    
    # 심플한 마켓 이름으로 변환 (BTC-95000-C 형식)
    simple_market = market.replace("USD-", "") if "USD-" in market else market
    
    # 시작 시간과 종료 시간 추출
    start_match = re.search(r'start=(\d+)', url)
    end_match = re.search(r'end=(\d+)', url)
    
    start_ts = int(start_match.group(1)) if start_match else 0
    end_ts = int(end_match.group(1)) if end_match else 0
    
    # UTC+8 시간대로 변환 (밀리초 → 초 변환 후)
    utc_plus_8 = timedelta(hours=8)
    start_time = datetime.utcfromtimestamp(start_ts/1000) + utc_plus_8
    end_time = datetime.utcfromtimestamp(end_ts/1000) + utc_plus_8
    
    # 시간 포맷: YYYYMMDD_HHMM
    start_str = start_time.strftime("%Y%m%d_%H%M")
    end_str = end_time.strftime("%Y%m%d_%H%M")
    
    return simple_market, start_str, end_str

# Paradex API에서 데이터 가져오기
def fetch_paradex_data(url):
    response = requests.get(url)
    data = response.json()
    return data['results']

# 사용자 입력 받기
print("\n=== 옵션 데이터 수집 설정 ===")
market = input("마켓 입력 (예: BTC-USD-95000-C): ")
if not market:
    market = "BTC-USD-95000-C"  # 기본값

# 날짜 형식 안내
print("\n날짜 형식: YYYY-MM-DD HH:MM (예: 2025-04-23 10:30)")

# 시작 시간 입력
while True:
    try:
        start_input = input("시작 시간 (UTC+8): ")
        start_time = datetime.strptime(start_input, "%Y-%m-%d %H:%M")
        break
    except ValueError:
        print("올바른 날짜/시간 형식이 아닙니다. 다시 입력해주세요.")

# 종료 시간은 항상 현재 시간(가장 최신)으로 설정
end_time = datetime.now() + timedelta(hours=8)  # 현재 시간 + 8시간(UTC+8)
print(f"종료 시간: 현재 시간 (UTC+8: {end_time.strftime('%Y-%m-%d %H:%M')})")

# UTC+8 시간을 UTC로 변환 (API에 보낼 때는 UTC 기준)
utc_offset = timedelta(hours=8)
start_time_utc = start_time - utc_offset
end_time_utc = end_time - utc_offset  # 현재 시간은 이미 UTC이므로 변환 필요 없음

# 타임스탬프 변환
start_ts = datetime_to_ms_timestamp(start_time_utc)
end_ts = datetime_to_ms_timestamp(end_time_utc)

# API URL 생성
url = f'https://api.prod.paradex.trade/v1/markets/summary?market={market}&start={start_ts}&end={end_ts}'
print(f"\n사용할 API URL: {url}")

# 마켓 이름과 시간 추출
market_name, start_time_str, end_time_str = extract_market_and_time(url)

# 데이터 가져오기
try:
    results = fetch_paradex_data(url)
    if not results:
        print("\n⚠️ 해당 기간에 데이터가 없습니다.")
        exit()
    
    # API 응답의 모든 필드 확인 (첫 번째 결과만)
    print("\n사용 가능한 데이터 필드:")
    for key in results[0].keys():
        print(f"- {key}")
        
except Exception as e:
    print(f"\n❌ API 요청 중 오류 발생: {e}")
    exit()

# 문자열을 float로 안전하게 변환하는 함수 추가
def safe_float(value, default=0.0):
    if value == '' or value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

# 필요한 데이터 추출하기
data_list = []
for item in results:
    timestamp = item['created_at']
    date_time = datetime.fromtimestamp(timestamp / 1000)  # milliseconds to seconds
    
    greeks = item.get('greeks', {})
    
    # 24시간 변동량 - API 문서에 따른 정확한 필드명 사용
    price_change_rate_24h = item.get('price_change_rate_24h', 0)
    volume_24h = item.get('volume_24h', 0)
    
    # funding_rate 추가
    funding_rate = item.get('funding_rate', 0)
    next_funding_time = item.get('next_funding_time', 0)
    
    data_dict = {
        'timestamp': date_time,
        'underlying_price': safe_float(item.get('underlying_price')),
        'last_traded_price': safe_float(item.get('last_traded_price')),
        'mark_price': safe_float(item.get('mark_price')),
        'mark_iv': safe_float(item.get('mark_iv')),
        'bid': safe_float(item.get('bid')),
        'ask': safe_float(item.get('ask')),
        # 24시간 관련 필드
        'price_change_rate_24h': safe_float(price_change_rate_24h),
        'volume_24h': safe_float(volume_24h),
        # 펀딩 관련 추가
        'funding_rate': safe_float(funding_rate),
        'next_funding_time': next_funding_time,
        # 그리스
        'delta': safe_float(greeks.get('delta')),
        'gamma': safe_float(greeks.get('gamma')),
        'vega': safe_float(greeks.get('vega')),
        'theta': safe_float(greeks.get('theta')),
        'rho': safe_float(greeks.get('rho')),
        'vanna': safe_float(greeks.get('vanna')),
        'volga': safe_float(greeks.get('volga'))
    }
    data_list.append(data_dict)

# 데이터프레임 생성
df = pd.DataFrame(data_list)

# 시간순으로 정렬
df.sort_values('timestamp', inplace=True)

# 동적 파일 이름 생성
file_name = f"{market_name}_{start_time_str}_to_{end_time_str}.csv"
csv_path = os.path.join(script_dir, file_name)

# CSV 파일로 저장
df.to_csv(csv_path, index=False)

# 데이터 확인
print(f"\n✅ 데이터가 {csv_path}에 저장되었습니다.")
print(f"\n총 {len(df)}개의 데이터 행이 수집되었습니다.")
print("\n데이터 샘플 (처음 5행):")
print(df.head())
