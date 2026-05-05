import os
import threading
import requests
import re
from flask import Flask
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# 建立 Flask 伺服器以通過 Render 系統檢查
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# 取出乾淨的 Threads 網址
def extract_and_clean_url(text: str) -> str:
    text = text.replace(" ", "").replace("\n", "")
    match = re.search(r'(https?://(?:www\.)?threads\.(?:net|com)[^\?]+)', text)
    if match:
        clean_url = match.group(1).replace("threads.com", "threads.net")
        return clean_url
    return ""

# 爬取 Threads 貼文內容
def get_threads_content(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        meta_desc = soup.find("meta", property="og:description")
        if meta_desc and meta_desc.get("content"):
            return meta_desc.get("content")
            
        meta_desc_alt = soup.find("meta", attrs={"name": "description"})
        if meta_desc_alt and meta_desc_alt.get("content"):
            return meta_desc_alt.get("content")

        return "無法取得貼文內容 (可能被系統阻擋或貼文不公開)"
    except Exception as e:
        return f"讀取失敗: {str(e)}"

# Telegram Bot 處理訊息的非同步函式
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "threads" in text:
        clean_url = extract_and_clean_url(text)
        if clean_url:
            content = get_threads_content(clean_url)
            reply_text = f"{content}\n\n{clean_url}"
            await update.message.reply_text(reply_text)

def main():
    # 啟動網頁伺服器執行緒
    threading.Thread(target=run_web, daemon=True).start()
    
    # 從環境變數讀取 Token
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    if not TOKEN:
        print("啟動失敗：請設定 TELEGRAM_TOKEN 環境變數")
        return

    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()