import telegram
import yfinance as yf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, UTC
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
from flask import Flask
import asyncio
import time
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.StreamHandler(), logging.FileHandler("debug.log")])
logger = logging.getLogger(__name__)

logger.info("===== NEW EXECUTION START =====")

app = Flask(__name__)

# 환경 변수 확인
logger.info("Loading environment variables...")
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
if TOKEN is None or CHAT_ID is None:
    logger.error("BOT_TOKEN or CHAT_ID is None!")
    exit(1)
logger.info(f"TOKEN loaded: {TOKEN[:5]}...")
logger.info(f"CHAT_ID loaded: {CHAT_ID}")

# 텔레그램 봇 초기화
logger.info("Initializing Telegram bot...")
try:
    bot = telegram.Bot(token=TOKEN)
    logger.info("Telegram bot initialized successfully!")
except Exception as e:
    logger.error(f"Initializing bot failed: {str(e)}")
    exit(1)

logger.info(f"Starting bot... TOKEN: {TOKEN[:5]}..., CHAT_ID: {CHAT_ID}")

# 마지막 실행 시간 저장
last_run_time = 0

# 데이터 가져오기
def get_asset_data(ticker):
    logger.info(f"Fetching data for {ticker}")
    try:
        asset = yf.Ticker(ticker)
        hist = asset.history(period="1d")
        if hist.empty:
            logger.warning(f"{ticker}: No data available")
            return None, None
        price = hist["Close"].iloc[-1]
        change = ((price - hist["Open"].iloc[0]) / hist["Open"].iloc[0]) * 100
        logger.info(f"{ticker}: Price = ${price:.2f}, Change = {change:.2f}%")
        return price, change
    except Exception as e:
        logger.error(f"{ticker}: Error - {str(e)}")
        return None, None

# 차트 생성
def create_chart(ticker):
    logger.info(f"Creating chart for {ticker}")
    try:
        asset = yf.Ticker(ticker)
        hist = asset.history(period="6mo")
        if hist.empty:
            logger.warning(f"{ticker}: No chart data")
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
        logger.info(f"{ticker}: Chart saved successfully")
        return chart_file
    except Exception as e:
        logger.error(f"{ticker}: Error - {str(e)}")
        return None

# Zum 데일리 브리핑 가져오기 (Playwright 사용)
def get_zum_briefing(ticker):
    logger.info(f"Fetching Zum briefing for {ticker}")
    try:
        if ticker in ["IGV", "SOXL", "IVZ", "BLK", "BRKU"]:
            url = f"https://invest.zum.com/etf/{ticker}/"
            briefing_class = "styles_briefingInner__WBq3C"
        else:
            url = f"https://invest.zum.com/stock/{ticker}/"
            briefing_class = "styles_briefingInner__1kI5J"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url)
            page.wait_for_timeout(3000)  # 페이지 로드 대기
            soup = BeautifulSoup(page.content(), "html.parser")
            briefing_div = soup.find("div", class_=briefing_class)
            if briefing_div:
                briefing = briefing_div.text.strip()
            else:
                logger.warning(f"{ticker}: No briefing found with class {briefing_class}, HTML sample: {str(soup)[:500]}")
                briefing = "No daily briefing available."
            browser.close()
        logger.info(f"{ticker}: Briefing - {briefing}")
        return briefing
    except Exception as e:
        logger.error(f"{ticker}: Error - {str(e)}")
        return "Briefing unavailable"

# 아침 업데이트
async def send_morning_update():
    tickers = ["IGV", "SOXL", "IVZ", "BLK", "BRKU", "BTC-USD", "ETH-USD"]
    message = "🌞 Good Morning!\n\n"
    logger.info("Starting morning update...")

    for ticker in tickers:
        price, change = get_asset_data(ticker)
        if price is None or change is None:
            message += f"{ticker}: Data unavailable\n\n"
            continue
        briefing = get_zum_briefing(ticker)
        message += f"{ticker}: ${price:.2f} ({change:+.2f}%)\n{briefing}\n\n"

        chart_file = create_chart(ticker)
        if chart_file:
            try:
                with open(chart_file, "rb") as photo:
                    logger.info(f"{ticker}: Sending chart image")
                    await bot.send_photo(chat_id=CHAT_ID, photo=photo)
                    logger.info(f"{ticker}: Chart image sent successfully")
            except Exception as e:
                logger.error(f"{ticker}: Error sending chart - {str(e)}")

    try:
        logger.info("Sending final message")
        await bot.send_message(chat_id=CHAT_ID, text=message.strip())
        logger.info("Morning update sent successfully!")
    except Exception as e:
        logger.error(f"Error sending message - {str(e)}")
    logger.info("Morning update completed!")

# Flask 엔드포인트
@app.route('/')
async def run_update():
    global last_run_time
    now = datetime.now(UTC) + timedelta(hours=9)  # KST
    current_time = time.time()
    logger.info(f"Request received at {now.hour}:{now.minute} KST")

    if current_time - last_run_time < 60:
        logger.info("Ignoring request: Too soon since last run")
        return "Update already sent recently!"

    last_run_time = current_time
    try:
        logger.info("Starting update process...")
        await send_morning_update()
        logger.info("Update process completed!")
        return "Update sent!"
    except Exception as e:
        logger.error(f"Error in update: {str(e)}\n{traceback.format_exc()}")
        return "Internal Server Error", 500

if __name__ == "__main__":
    logger.info("Starting Flask server...")
    app.run(host="0.0.0.0", port=3000, debug=True)