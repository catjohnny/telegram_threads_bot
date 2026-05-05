import os
import requests
import re
from flask import Flask, request, abort
from bs4 import BeautifulSoup

# 載入 LINE SDK v3 相關模組
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

app = Flask(__name__)

# 從環境變數讀取 LINE 金鑰
CHANNEL_ACCESS_TOKEN = os.environ.get('F9y7/jQO8gil7X1NKY7mgg6FaF6y/GstO3YqDSBIa3smgawdgFvdsDj4Tjiai+8VMw7wrs6PgIC5PXhd8Zxwcil5jHwzEPqV0s+C/hPWFJ2tFa3gq2FX2IOeY3tyI0KRqhEFMTZ32VryDoc32sEsowdB04t89/1O/w1cDnyilFU=')
CHANNEL_SECRET = os.environ.get('6b9eaa28ca0913a089b5337afd86551d')

# 設定 LINE API
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# 取出乾淨的 Threads 網址
def extract_and_clean_url(text: str) -> str:
    text = text.replace(" ", "").replace("\n", "")
    match = re.search(r'(https?://(?:www\.)?threads\.(?:net|com)[^\?]+)', text)
    if match:
        return match.group(1).replace("threads.com", "threads.net")
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

# 接收 LINE 傳來的 Webhook 請求
@app.route("/callback", methods=['POST'])
def callback():
    # 取得 X-Line-Signature 表頭標籤
    signature = request.headers['X-Line-Signature']
    # 取得請求內容
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Check your channel access token/channel secret.")
        abort(400)
    return 'OK'

# 處理文字訊息事件
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    text = event.message.text
    
    # 判斷是否包含 threads 網址
    if "threads" in text:
        clean_url = extract_and_clean_url(text)
        
        if clean_url:
            content = get_threads_content(clean_url)
            reply_text = f"{content}\n\n{clean_url}"
            
            # 使用 LINE API 回傳訊息
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply_text)]
                    )
                )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)