import os
import random
from flask import Flask, request
from dotenv import load_dotenv

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


# 讀取 .env
load_dotenv()

app = Flask(__name__)

# 取得 LINE 設定
CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")

configuration = Configuration(
    access_token=CHANNEL_ACCESS_TOKEN
)

handler = WebhookHandler(CHANNEL_SECRET)


# LINE Webhook
@app.route("/webhook", methods=["POST"])
def webhook():

    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return "Invalid signature", 400

    return "OK", 200


# 收到文字訊息
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    text = event.message.text

    print("收到 LINE 訊息：", text)

    # 如果使用者說「你好」
    if text == "!":

        number = random.randint(100, 999)

        with ApiClient(configuration) as api_client:

            line_bot_api = MessagingApi(api_client)

            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(
                            text=str(number)
                        )
                    ]
                )
            )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )