import os, json
from datetime import datetime
from config import DEV_ID, GROUPS_DIR


# ============================================================
# أدمن البوت (JSON لكل مجموعة)
# ============================================================
def _group_file(chat_id):
    return os.path.join(GROUPS_DIR, f"{chat_id}.json")


def _load_group(chat_id):
    f = _group_file(chat_id)
    if os.path.exists(f):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                return json.load(fp)
        except:
            pass
    return {
        "chat_id": chat_id,
        "admins": [],
        "created_at": datetime.now().isoformat()
    }


def _save_group(chat_id, data):
    with open(_group_file(chat_id), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_bot_admin(chat_id, user_id):
    """إضافة أدمن"""
    d = _load_group(chat_id)
    if user_id not in d["admins"]:
        d["admins"].append(user_id)
        _save_group(chat_id, d)
        return True
    return False


def remove_bot_admin(chat_id, user_id):
    """حذف أدمن"""
    d = _load_group(chat_id)
    if user_id in d["admins"]:
        d["admins"].remove(user_id)
        _save_group(chat_id, d)
        return True
    return False


def is_bot_admin(chat_id, user_id):
    """التحقق من أدمن البوت"""
    if user_id == DEV_ID:
        return True
    return user_id in _load_group(chat_id).get("admins", [])


def list_bot_admins(chat_id):
    """قائمة أدمن البوت"""
    return _load_group(chat_id).get("admins", [])


# ============================================================
# is_bot_user — التحقق أن المستخدم بوت
# ============================================================
def is_bot_user(user):
    if not user:
        return False
    return getattr(user, 'bot', False) or getattr(user, 'is_bot', False)


# ============================================================
# resolve_target — تحديد الهدف من reply/@username/ID
# ============================================================
async def resolve_target(bot, e, pattern_arg=None, allow_bots=False):
    """
    ترجع (user_id, display_name)
    """
    target_user = None
    target_id = None
    target_name = None

    # 1) reply
    if e.reply_to_msg_id:
        try:
            reply_msg = await e.get_reply_message()
            if reply_msg:
                sender = await reply_msg.get_sender()
                if sender:
                    target_user = sender
                    target_id = sender.id
                    if getattr(sender, 'username', None):
                        target_name = f"@{sender.username}"
                    else:
                        first = getattr(sender, 'first_name', None) or ""
                        last = getattr(sender, 'last_name', None) or ""
                        target_name = f"{first} {last}".strip() or "Unknown"
        except Exception as ex:
            print(f"[RESOLVE reply] {type(ex).__name__}: {ex}")

    # 2) @username أو ID
    if not target_id and pattern_arg:
        arg = pattern_arg.strip()
        if arg.startswith("@"):
            try:
                user = await bot.get_entity(arg)
                target_user = user
                target_id = user.id
                if getattr(user, 'username', None):
                    target_name = f"@{user.username}"
                else:
                    first = getattr(user, 'first_name', None) or ""
                    last = getattr(user, 'last_name', None) or ""
                    target_name = f"{first} {last}".strip() or "Unknown"
            except Exception as ex:
                print(f"[RESOLVE @] {type(ex).__name__}: {ex}")
                return None, None
        elif arg.isdigit():
            try:
                user = await bot.get_entity(int(arg))
                target_user = user
                target_id = user.id
                if getattr(user, 'username', None):
                    target_name = f"@{user.username}"
                else:
                    first = getattr(user, 'first_name', None) or ""
                    last = getattr(user, 'last_name', None) or ""
                    target_name = f"{first} {last}".strip() or str(target_id)
            except:
                target_id = int(arg)
                target_name = str(arg)

    if not allow_bots and target_user is not None:
        if is_bot_user(target_user):
            return "BOT_NOT_ALLOWED", target_name

    return target_id, target_name