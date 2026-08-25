import os
from flask import Flask, request
from dotenv import load_dotenv

from services.command_router import GameSessionState, handle_command
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
game_state = GameSessionState()


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

    text = event.message.text.strip()

    print("收到 LINE 訊息：", text)

    source_key = get_source_key(event)
    line_user_id = get_line_user_id(event)

    reply = handle_command(text, source_key=source_key, line_user_id=line_user_id, state=game_state)
    if reply is not None:
        reply_text(event.reply_token, reply)


def get_source_key(event):
    source = getattr(event, "source", None)
    source_type = getattr(source, "type", "unknown")

    for source_id_name in ("group_id", "room_id", "user_id"):
        source_id = getattr(source, source_id_name, None)
        if source_id:
            return f"{source_type}:{source_id_name}:{source_id}"

    return "unknown"


def get_line_user_id(event):
    source = getattr(event, "source", None)
    return getattr(source, "user_id", None)


def reply_text(reply_token, text):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    TextMessage(
                        text=text
                    )
                ]
            )
        )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )
