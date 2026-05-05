import os
import requests
import re
from flask import Flask, request, abort
from bs4 import BeautifulSoup

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

# 新增這段讓 cron-job 能夠順利讀取首頁
@app.route("/")
def home():
    return "Bot is awake and running!"

CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# 取出乾淨的 Threads 或 Instagram 網址
def extract_and_clean_url(text: str) -> str:
    text = text.replace(" ", "").replace("\n", "")
    
    # 判斷並處理 Threads 網址
    threads_match = re.search(r'(https?://(?:www\.)?threads\.(?:net|com)[^\?]+)', text)
    if threads_match:
        return threads_match.group(1).replace("threads.com", "threads.net")
        
    # 判斷並處理 Instagram 網址 (支援一般貼文 p、連續短片 reel、IGTV tv)
    ig_match = re.search(r'(https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/[A-Za-z0-9_-]+)', text)
    if ig_match:
        return ig_match.group(1)
        
    return ""

# 爬取貼文內容
def get_social_content(url: str) -> str:
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
            content = meta_desc.get("content")
            # Instagram 的 og:description 通常會帶有引號或固定格式，這裡嘗試清整
            if "on Instagram" in content:
                content = content.split('"', 1)[-1].rsplit('"', 1)[0]
            return content.strip()
            
        meta_desc_alt = soup.find("meta", attrs={"name": "description"})
        if meta_desc_alt and meta_desc_alt.get("content"):
            return meta_desc_alt.get("content").strip()

        return "無法取得貼文內容 (可能被系統阻擋或貼文不公開)"
    except Exception as e:
        return f"讀取失敗: {str(e)}"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    text = event.message.text
    
    clean_url = extract_and_clean_url(text)
    
    if clean_url:
        content = get_social_content(clean_url)
        
        # 依照指定格式組合回覆訊息
        reply_text = f"{content}\n➖➖➖➖➖➖\n✅ {clean_url}"
        
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