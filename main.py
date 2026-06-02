import os
import requests
import re
import traceback
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

@app.route("/")
def home():
    return "Bot is awake and running!"

CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")

print("LINE_CHANNEL_ACCESS_TOKEN exists:", bool(CHANNEL_ACCESS_TOKEN), flush=True)
print("LINE_CHANNEL_SECRET exists:", bool(CHANNEL_SECRET), flush=True)

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

def extract_and_clean_url(text: str) -> str:
    text = text.replace(" ", "").replace("\n", "")

    threads_match = re.search(r'(https?://(?:www\.)?threads\.(?:net|com)[^\?\s]+)', text)
    if threads_match:
        return threads_match.group(1).replace("threads.com", "threads.net")

    ig_match = re.search(r'(https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/[A-Za-z0-9_-]+)', text)
    if ig_match:
        return ig_match.group(1)

    return ""

def get_social_content(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    try:
        print("Fetching URL:", url, flush=True)
        response = requests.get(url, headers=headers, timeout=10)
        print("Fetch status:", response.status_code, flush=True)
        print("Final URL:", response.url, flush=True)
        print("HTML preview:", response.text[:300], flush=True)

        soup = BeautifulSoup(response.text, "html.parser")

        meta_desc = soup.find("meta", property="og:description")
        if meta_desc and meta_desc.get("content"):
            content = meta_desc.get("content")
            if "on Instagram" in content:
                content = content.split('"', 1)[-1].rsplit('"', 1)[0]
            return content.strip()

        meta_desc_alt = soup.find("meta", attrs={"name": "description"})
        if meta_desc_alt and meta_desc_alt.get("content"):
            return meta_desc_alt.get("content").strip()

        return f"無法取得貼文內容。HTTP 狀態碼：{response.status_code}"

    except Exception as e:
        print("get_social_content ERROR:", str(e), flush=True)
        traceback.print_exc()
        return f"讀取失敗：{str(e)}"

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    print("=== LINE WEBHOOK RECEIVED ===", flush=True)
    print("signature exists:", bool(signature), flush=True)
    print("body:", body, flush=True)

    try:
        handler.handle(body, signature)
        print("=== handler.handle OK ===", flush=True)
    except InvalidSignatureError:
        print("InvalidSignatureError", flush=True)
        abort(400)
    except Exception:
        print("=== handler.handle ERROR ===", flush=True)
        traceback.print_exc()

    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    print("=== MESSAGE EVENT ===", flush=True)
    print("reply_token:", event.reply_token, flush=True)
    print("text:", event.message.text, flush=True)

    text = event.message.text
    clean_url = extract_and_clean_url(text)

    print("clean_url:", clean_url, flush=True)

    if not clean_url:
        print("No valid URL found", flush=True)
        return

    content = get_social_content(clean_url)
    reply_text = f"{content}\n➖➖➖➖➖➖\n✅ {clean_url}"

    print("reply_text preview:", reply_text[:500], flush=True)

    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
        print("=== reply_message OK ===", flush=True)

    except Exception:
        print("=== reply_message ERROR ===", flush=True)
        traceback.print_exc()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
