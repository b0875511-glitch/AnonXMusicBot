import os, json, sqlite3
from telethon.tl.functions.channels import (
    GetParticipantRequest, GetParticipantsRequest
)
from telethon.tl.types import (
    ChannelParticipantAdmin, ChannelParticipantCreator,
    ChannelParticipantsAdmins, MessageEntityCustomEmoji
)
from telethon.errors import UserNotParticipantError

from config import (
    DEV_ID, SOURCE_USERNAME, DB, SETTINGS_FILE,
    PREMIUM_EMOJIS, FALLBACKS
)


# ============================================================
# Premium Emojis
# ============================================================
def utf16_len(s):
    return len(s.encode('utf-16-le')) // 2


def build_entities(text):
    entities = []
    for key, emoji_id in PREMIUM_EMOJIS.items():
        fallback = FALLBACKS[key]
        start = 0
        while True:
            idx = text.find(fallback, start)
            if idx == -1:
                break
            entities.append(
                MessageEntityCustomEmoji(
                    offset=utf16_len(text[:idx]),
                    length=utf16_len(fallback),
                    document_id=emoji_id
                )
            )
            start = idx + len(fallback)
    return entities


def premium(text):
    return text, build_entities(text)


def bold_num(s):
    mapping = {
        '0': '𝟎', '1': '𝟏', '2': '𝟐', '3': '𝟑', '4': '𝟒',
        '5': '𝟓', '6': '𝟔', '7': '𝟕', '8': '𝟖', '9': '𝟗',
        ':': ':'
    }
    return ''.join(mapping.get(c, c) for c in str(s))


# ============================================================
# Database
# ============================================================
def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = db()
    c.execute("""CREATE TABLE IF NOT EXISTS queue(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        file TEXT,
        title TEXT,
        duration INTEGER DEFAULT 0,
        requested_by TEXT DEFAULT 'Unknown',
        is_video INTEGER DEFAULT 0
    )""")
    c.commit()
    try:
        c.execute("ALTER TABLE queue ADD COLUMN is_video INTEGER DEFAULT 0")
        c.commit()
    except:
        pass
    c.close()


# ============================================================
# Settings
# ============================================================
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


def get_setting(key, default=None):
    return load_settings().get(key, default)


def set_setting(key, value):
    s = load_settings()
    s[key] = value
    save_settings(s)


# ============================================================
# Subscription
# ============================================================
async def check_subscription(bot, user_id, event=None):
    # في القناة → عبر post_author
    if event is not None and getattr(event, 'is_channel', False):
        post_author = getattr(event.message, 'post_author', None)
        if not post_author or not post_author.strip():
            return True
        try:
            result = await bot(GetParticipantsRequest(
                channel=event.chat_id,
                filter=ChannelParticipantsAdmins(),
                offset=0, limit=200, hash=0
            ))
            author = post_author.strip()
            author_clean = author.lstrip('@').strip()
            admin_id = None
            for admin in result.users:
                first = (admin.first_name or "").strip()
                last = (admin.last_name or "").strip()
                full_name = f"{first} {last}".strip()
                username = (admin.username or "").strip()
                if username and username.lower() == author_clean.lower():
                    admin_id = admin.id; break
                if full_name and full_name == author:
                    admin_id = admin.id; break
                if first and first == author:
                    admin_id = admin.id; break
            if admin_id is None:
                return True
            user_id = admin_id
        except Exception as e:
            print(f"[SUB CH] {type(e).__name__}: {e}")
            return True

    if user_id == DEV_ID:
        return True
    try:
        await bot(GetParticipantRequest(channel=SOURCE_USERNAME, participant=user_id))
        return True
    except UserNotParticipantError:
        return False
    except Exception as e:
        print(f"[SUB] {type(e).__name__}: {e}")
        return False


# ============================================================
# Admin check (تيليجرام)
# ============================================================
async def is_admin(bot, chat_id, user_id):
    """مشرف تيليجرام أو أدمن البوت"""
    if user_id == DEV_ID:
        return True
    # ✅ فحص أدمن البوت أولاً
    from ranks import is_bot_admin
    if is_bot_admin(chat_id, user_id):
        return True
    # فحص مشرف تيليجرام
    try:
        result = await bot(GetParticipantRequest(channel=chat_id, participant=user_id))
        p = result.participant
        return isinstance(p, (ChannelParticipantAdmin, ChannelParticipantCreator))
    except:
        return False


# ============================================================
# Sender name
# ============================================================
async def get_requested_by(bot, e):
    if e.is_channel:
        post_author = getattr(e.message, 'post_author', None)
        if post_author and post_author.strip():
            return post_author.strip()
        try:
            from_id = getattr(e.message, 'from_id', None)
            if from_id and hasattr(from_id, 'user_id') and from_id.user_id:
                user = await bot.get_entity(from_id.user_id)
                if user:
                    if getattr(user, 'username', None):
                        return f"@{user.username}"
                    if getattr(user, 'first_name', None):
                        return user.first_name
        except:
            pass
        try:
            chat = await e.get_chat()
            if chat and getattr(chat, 'title', None):
                return chat.title
        except:
            pass
        return "Admin"
    try:
        sender = await e.get_sender()
        if sender:
            if getattr(sender, 'username', None):
                return f"@{sender.username}"
            if getattr(sender, 'first_name', None):
                name = sender.first_name
                if getattr(sender, 'last_name', None):
                    name += f" {sender.last_name}"
                return name
    except:
        pass
    return "Unknown"