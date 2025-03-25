import telegram
import yfinance as yf
import matplotlib
matplotlib.use('Agg')  # Matplotlib 비GUI 모드 설정
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, UTC
import requests
from bs4 import BeautifulSoup
import os
from flask import Flask

app = Flask(__name__)

# 텔레그램 설정
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
bot = telegram.Bot(token=TOKEN)

print(f"Starting bot... TOKEN: {TOKEN[:5]}..., CHAT_ID: {CHAT_ID}")

# 데이터 가져오기
def get_asset_data(ticker):
    print(f"Fetching data for {ticker}")
    try:
        asset = yf.Ticker(ticker)
        hist = asset.history(period="1d")
        if hist.empty:
            print(f"{ticker}: No data available")
            return None, None
        price = hist["Close"].iloc[-1]
        change = ((price - hist["Open"].iloc[0]) / hist["Open"].iloc[0]) * 100
        print(f"{ticker}: Price = ${price:.2f}, Change = {change:.2f}%")
        return price, change
    except Exception as e:
        print(f"{ticker}: Error in get_asset_data - {str(e)}")
        return None, None

# 차트 생성
def create_chart(ticker):
    print(f"Creating chart for {ticker}")
    try:
        asset = yf.Ticker(ticker)
        hist = asset.history(period="7d")
        if hist.empty:
            print(f"{ticker}: No chart data")
            return
        prices = hist["Close"]
        dates = hist.index
        plt.figure(figsize=(6, 4))
        plt.plot(dates, prices, label=ticker)
        plt.title(f"{ticker} - 7 Day Chart")
        plt.xlabel("Date")
        plt.ylabel("Price (USD)")
        plt.grid(True)
        plt.savefig(f"{ticker}_chart.png")
        plt.close39
        print(f"{ticker}: Chart saved successfully")
    except Exception as e:
        print(f"{ticker}: Error in create_chart - {str(e)}")

# 야후 파이낸스 뉴스
def get_yahoo_news(ticker):
    print(f"Fetching news for {ticker}")
    try:
        url = f"https://finance.yahoo.com/quote/{ticker}/news"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")
        news_items = soup.find_all("h3", class_="Mb(5px)")[:1]
        news = news_items[0].text.strip() if news_items else "No recent news."
        print(f"{ticker}: News - {news}")
        return news
    except Exception as e:
        print(f"{ticker}: Error in get_yahoo_news - {str(e)}")
        return "News unavailable"

# 아침 업데이트
def send_morning_update():
    tickers = ["IGV", "SOXL", "IVZ", "BLK", "BRKU", "BTC-USD", "ETH-USD"]
    related = {"IGV": "ADBE", "SOXL": "NVDA"}
    message = "🌞 Good Morning!\n\n"
    print("Starting morning update...")

    for ticker in tickers:
        price, change = get_asset_data(ticker)
        if price is None or change is None:
            message += f"{ticker}: Data unavailable\n"
            continue
        news = get_yahoo_news(ticker)
        if ticker in related and "No recent news" in news:
            news = get_yahoo_news(related[ticker])
        message += f"{ticker}: ${price:.2f} ({change:+.2f}%) - {news}\n"

        create_chart(ticker)
        try:
            with open(f"{ticker}_chart.png", "rb") as photo:
                print(f"{ticker}: Sending chart to Telegram")
                bot.send_photo(chat_id=CHAT_ID, photo=photo)
                print(f"{ticker}: Chart sent successfully")
        except Exception as e:
            print(f"{ticker}: Error sending chart - {str(e)}")

    try:
        print("Sending final message to Telegram")
        bot.send_message(chat_id=CHAT_ID, text=message)
        print("Morning update sent successfully!")
    except Exception as e:
        print(f"Error sending message - {str(e)}")

# Flask 엔드포인트 (테스트용 KST 23시)
@app.route('/')
def run_update():
    now = datetime.now(UTC) + timedelta(hours=9)  # KST, Deprecation 수정
    print(f"Request received at {now.hour}:{now.minute} KST")
    if now.hour == 23:  # KST 23시로 테스트
        send_morning_update()
        return "Update sent!"
    return "Bot is alive, waiting for 23 PM KST"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)