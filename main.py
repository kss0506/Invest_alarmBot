import telegram
import yfinance as yf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, UTC
import requests
from bs4 import BeautifulSoup
import os
from flask import Flask
import asyncio
import time
import traceback

print("\n" * 50)  # 콘솔 초기화
print("===== NEW EXECUTION START =====")

app = Flask(__name__)

# 환경 변수 확인
print("Loading environment variables...")
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
if TOKEN is None or CHAT_ID is None:
    print("ERROR: BOT_TOKEN or CHAT_ID is None!")
    exit(1)
print(f"TOKEN loaded: {TOKEN[:5]}...")
print(f"CHAT_ID loaded: {CHAT_ID}")

# 텔레그램 봇 초기화
print("Initializing Telegram bot...")
try:
    bot = telegram.Bot(token=TOKEN)
    print("Telegram bot initialized successfully!")
except Exception as e:
    print(f"ERROR initializing bot: {str(e)}")
    exit(1)

print(f"Starting bot... TOKEN: {TOKEN[:5]}..., CHAT_ID: {CHAT_ID}")

# 마지막 실행 시간 저장
last_run_time = 0

# 데이터 가져오기
def get_asset_data(ticker):
    print(f"[DATA] Fetching data for {ticker}")
    try:
        asset = yf.Ticker(ticker)
        hist = asset.history(period="1d")
        if hist.empty:
            print(f"[DATA] {ticker}: No data available")
            return None, None
        price = hist["Close"].iloc[-1]
        change = ((price - hist["Open"].iloc[0]) / hist["Open"].iloc[0]) * 100
        print(f"[DATA] {ticker}: Price = ${price:.2f}, Change = {change:.2f}%")
        return price, change
    except Exception as e:
        print(f"[DATA] {ticker}: Error - {str(e)}")
        return None, None

# 차트 생성
def create_chart(ticker):
    print(f"[CHART] Creating chart for {ticker}")
    try:
        asset = yf.Ticker(ticker)
        hist = asset.history(period="6mo")
        if hist.empty:
            print(f"[CHART] {ticker}: No chart data")
            return None
        prices = hist["Close"]
        dates = hist.index
        plt.figure(figsize=(8, 5))
        plt.plot(dates, prices, color='blue', linewidth=2)
        plt.title(f"{ticker} - 6 Month Chart", fontsize=14)
        plt.xlabel("Date (MM-DD)", fontsize=12)
        plt.ylabel("Price (USD)", fontsize=12)
        plt.grid(True, linestyle='--', alpha=0.5)
        plt.gca().xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%m-%d'))
        plt.gca().xaxis.set_major_locator(plt.matplotlib.dates.MonthLocator())
        plt.xticks(rotation=45)
        plt.tight_layout()
        chart_file = f"{ticker}_chart.png"
        plt.savefig(chart_file)
        plt.close()
        print(f"[CHART] {ticker}: Chart saved successfully")
        return chart_file
    except Exception as e:
        print(f"[CHART] {ticker}: Error - {str(e)}")
        return None

# Zum 데일리 브리핑 가져오기
def get_zum_briefing(ticker):
    print(f"[NEWS] Fetching Zum briefing for {ticker}")
    try:
        if ticker in ["IGV", "SOXL", "IVZ", "BLK", "BRKU"]:
            url = f"https://invest.zum.com/etf/{ticker}/"
        else:
            url = f"https://invest.zum.com/stock/{ticker}/"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        briefing_div = soup.find("div", class_="styles_briefingInner__WBq3C")
        briefing = briefing_div.text.strip() if briefing_div else "No daily briefing available."
        print(f"[NEWS] {ticker}: Briefing - {briefing}")
        return briefing
    except requests.exceptions.RequestException as e:
        print(f"[NEWS] {ticker}: Network error - {str(e)}")
        return "Briefing unavailable (network issue)"
    except Exception as e:
        print(f"[NEWS] {ticker}: Error - {str(e)}")
        return "Briefing unavailable"

# 아침 업데이트
async def send_morning_update():
    tickers = ["IGV", "SOXL", "IVZ", "BLK", "BRKU", "BTC-USD", "ETH-USD"]
    message = "🌞 Good Morning!\n\n"
    print("===== MORNING UPDATE START =====")

    for ticker in tickers:
        price, change = get_asset_data(ticker)
        if price is None or change is None:
            message += f"{ticker}: Data unavailable\n"
            continue
        briefing = get_zum_briefing(ticker)
        message += f"{ticker}: ${price:.2f} ({change:+.2f}%)\n{briefing}\n\n"

        char