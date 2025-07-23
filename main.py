from flask import Flask, request
import requests
import os
import re

app = Flask(__name__)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET")
BOT_USERNAME = os.environ.get("BOT_USERNAME")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
OWNER_ID = 8141547148  # Your Telegram ID

LINK_PATTERN = r"(https?://\S+|www\.\S+|t\.me/\S+|telegram\.me/\S+)"

def send_message(chat_id, text, parse_mode=None):
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    requests.post(f"{API_URL}/sendMessage", json=payload)

def send_photo(chat_id, file_id, caption=None):
    payload = {"chat_id": chat_id, "photo": file_id}
    if caption:
        payload["caption"] = caption
    requests.post(f"{API_URL}/sendPhoto", json=payload)

def delete_message(chat_id, message_id):
    requests.post(f"{API_URL}/deleteMessage", json={"chat_id": chat_id, "message_id": message_id})

def is_admin(chat_id, user_id):
    response = requests.get(f"{API_URL}/getChatAdministrators?chat_id={chat_id}").json()
    return any(admin["user"]["id"] == user_id for admin in response.get("result", []))

def get_admin_usernames(chat_id):
    response = requests.get(f"{API_URL}/getChatAdministrators?chat_id={chat_id}").json()
    return [f"@{a['user']['username']}" for a in response.get("result", []) if a["user"].get("username")]

def broadcast_text_to_all_groups(text):
    if not os.path.exists("group.txt"):
        return
    with open("group.txt", "r") as f:
        groups = f.read().splitlines()
    for group_id in groups:
        if group_id.strip():
            send_message(group_id.strip(), text)

def broadcast_photo_to_all_groups(file_id, caption=None):
    if not os.path.exists("group.txt"):
        return
    with open("group.txt", "r") as f:
        groups = f.read().splitlines()
    for group_id in groups:
        if group_id.strip():
            send_photo(group_id.strip(), file_id, caption)

def save_group(chat_id):
    chat_id = str(chat_id)
    if not os.path.exists("group.txt"):
        open("group.txt", "w").close()
    with open("group.txt", "r+") as f:
        groups = f.read().splitlines()
        if chat_id not in groups:
            f.write(f"{chat_id}\n")
            send_message(OWNER_ID, f"🔔 New group added:\nGroup ID: `{chat_id}`", parse_mode="Markdown")

@app.route(f"/webhook/{WEBHOOK_SECRET}", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" not in data:
        return "ok"

    msg = data["message"]
    chat_id = msg["chat"]["id"]
    chat_type = msg["chat"]["type"]
    user_id = msg["from"]["id"]
    message_id = msg.get("message_id", "")
    text = msg.get("text", "")

    # Save group when bot is added
    if "new_chat_members" in msg:
        for member in msg["new_chat_members"]:
            username = member.get("username", "").lower()
            if member.get("is_bot") and BOT_USERNAME and username == BOT_USERNAME.lower():
                save_group(chat_id)
                send_message(chat_id, "SAFEGUARD YOUR GROUP FROM LINKS")

    # Save group always
    if chat_type in ["group", "supergroup"]:
        save_group(chat_id)

    # Handle /start in private
    if text == "/start" and chat_type == "private":
        start_text = (
            "Welcome\n"
            "This advance bot will delete links sended by members in your group\n"
            "Make this bot admin"
        )
        send_message(chat_id, start_text)
        return "ok"

    # /groupid for owner
    if text == "/groupid" and chat_type == "private" and user_id == OWNER_ID:
        if os.path.exists("group.txt"):
            with open("group.txt") as f:
                group_ids = f.read().strip()
            if group_ids:
                send_message(chat_id, f"📂 Saved Group IDs:\n```{group_ids}```", parse_mode="Markdown")
            else:
                send_message(chat_id, "No groups saved yet.")
        else:
            send_message(chat_id, "group.txt not found.")
        return "ok"

    # /lemonchus broadcast
    if text == "/lemonchus" and chat_type == "private" and "reply_to_message" in msg:
        original = msg["reply_to_message"]
        if "photo" in original:
            file_id = original["photo"][-1]["file_id"]
            caption = original.get("caption", "")
            broadcast_photo_to_all_groups(file_id, caption)
        elif "text" in original:
            content = original["text"]
            broadcast_text_to_all_groups(content)
        return "ok"

    # Link filtering in group
    if chat_type in ["group", "supergroup"] and text:
        if re.search(LINK_PATTERN, text, re.IGNORECASE):
            if not is_admin(chat_id, user_id):
                delete_message(chat_id, message_id)
                send_message(chat_id, "⚠️ Warning\nLinks is not allowed in this group")

    return "ok"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"[INFO] Bot running at port {port}")
    app.run(host="0.0.0.0", port=port)