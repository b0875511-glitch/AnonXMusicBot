import os, glob, asyncio, json, re
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.tl.functions.account import UpdateProfileRequest

from config import (
    API_ID, API_HASH, BOT_TOKEN, BOT_NAME,
    SESSIONS_DIR, ASSISTANTS_FILE
)
from utils import init_db
from handlers import register_handlers
from handlers_ranks import register_rank_handlers


# ============================================================
# Telegram Client
# ============================================================
bot = TelegramClient("bot_session", API_ID, API_HASH)
pending = {}


# ============================================================
# Assistant
# ============================================================
class Assistant:
    def __init__(self, session, name=None, uid=None, uname=None, file_key=None):
        self.session = session
        self.name = name
        self.uid = uid
        self.uname = uname
        self.file_key = file_key or name
        self.client = None
        self.call = None
        self.busy = False
        self.chat = None

    async def start(self):
        try:
            self.client = TelegramClient(StringSession(self.session), API_ID, API_HASH)
            await self.client.start()
            await self.call.start()
            me = await self.client.get_me()
            self.uid = me.id
            self.uname = me.username
            self.name = self.name or me.first_name
            print(f"[ASS] {self.name}")
            return True
        except Exception as e:
            print(f"[ASS ERR] {e}")
            return False

    async def set_name(self, n):
        try:
            await self.client(UpdateProfileRequest(first_name=n))
            self.name = n
            return True
        except:
            return False

    async def set_photo(self, p):
        try:
            f = await self.client.upload_file(p)
            await self.client(UploadProfilePhotoRequest(file=f))
            return True
        except:
            return False


# ============================================================
# Manager
# ============================================================
class Manager:
    def __init__(self):
        self.list = []

    async def load(self):
        if os.path.exists(ASSISTANTS_FILE):
            try:
                with open(ASSISTANTS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except:
                data = {}
        else:
            data = {}

        seen_uids = set()
        for key, info in data.items():
            if not info.get("is_active", True):
                continue
            session_file = f"{SESSIONS_DIR}/{key}.session"
            if not os.path.exists(session_file):
                continue
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    session_string = f.read().strip()
            except:
                continue
            a = Assistant(session_string, info.get("name", key),
                          info.get("user_id"), info.get("username"), file_key=key)
            if await a.start():
                if a.uid in seen_uids:
                    print(f"[MGR] ⚠️ {a.name} (UID {a.uid}) مكرر — تم تجاهله")
                    continue
                seen_uids.add(a.uid)
                self.list.append(a)
        print(f"[MGR] {len(self.list)} assistants loaded")

    def free(self):
        for a in self.list:
            if not a.busy:
                return a
        return None

    def find(self, chat):
        for a in self.list:
            if a.chat == chat:
                return a
        return None

    def find_by_uid(self, uid):
        for a in self.list:
            if a.uid == uid:
                return a
        return None

    async def add(self, session):
        try:
            a = Assistant(session)
            if not await a.start():
                return False, "فشل"

            # ✅ فحص التكرار
            for existing in self.list:
                if existing.uid == a.uid:
                    return False, f"المساعد موجود بالفعل ({a.name})"

            safe_name = f"assistant_{a.uid}"
            with open(f"{SESSIONS_DIR}/{safe_name}.session", "w", encoding="utf-8") as f:
                f.write(session)

            data = {}
            if os.path.exists(ASSISTANTS_FILE):
                try:
                    with open(ASSISTANTS_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except:
                    data = {}

            # ✅ تسمية تلقائية بالتسلسل
            final_name = a.name
            if len(self.list) > 0:
                base_name = self.list[0].name
                # إزالة الرقم التسلسلي من الاسم الأساسي
                base_clean = re.sub(r'\s+\d+$', '', base_name)
                final_name = f"{base_clean} {len(self.list) + 1}"
                await a.set_name(final_name)

            data[safe_name] = {
                "name": final_name,
                "username": a.uname,
                "user_id": a.uid,
                "is_active": True
            }
            with open(ASSISTANTS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            a.file_key = safe_name
            self.list.append(a)
            return True, final_name
        except Exception as e:
            return False, str(e)

    async def unify_name(self, base_name):
        """توحيد الأسماء مع تسلسل 2، 3، 4..."""
        results = []
        base_clean = re.sub(r'\s+\d+$', '', base_name.strip())

        for i, a in enumerate(self.list):
            if i == 0:
                new_name = base_clean
            else:
                new_name = f"{base_clean} {i + 1}"

            success = await a.set_name(new_name)
            results.append((new_name, success))
            print(f"[UNIFY] {a.file_key} → {new_name}")

        # ✅ حفظ الأسماء الجديدة في assistants.json
        data = {}
        if os.path.exists(ASSISTANTS_FILE):
            try:
                with open(ASSISTANTS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except:
                data = {}

        for a in self.list:
            if a.file_key in data:
                data[a.file_key]["name"] = a.name
            else:
                data[a.file_key] = {
                    "name": a.name,
                    "username": a.uname,
                    "user_id": a.uid,
                    "is_active": True
                }

        with open(ASSISTANTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return results

    async def unify_photo(self, p):
        return [(a.name, await a.set_photo(p)) for a in self.list]

    async def remove(self, uid):
        for a in self.list[:]:
            session_file = f"{SESSIONS_DIR}/{a.file_key}.session"
            if os.path.exists(session_file):
                try:
                    os.remove(session_file)
                except:
                    pass

            # ✅ حذف من assistants.json
            if os.path.exists(ASSISTANTS_FILE):
                try:
                    with open(ASSISTANTS_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if a.file_key in data:
                        del data[a.file_key]
                        with open(ASSISTANTS_FILE, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                except:
                    pass

            try:
                await a.client.disconnect()
            except:
                pass
            self.list.remove(a)
            return True
        return False

    async def remove_all(self):
        count = len(self.list)
        for a in self.list[:]:
            try:
                await a.client.disconnect()
            except:
                pass
        self.list.clear()
        for f in glob.glob(f"{SESSIONS_DIR}/*.session"):
            try:
                os.remove(f)
            except:
                pass
        with open(ASSISTANTS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
        return count


# ============================================================
# Main
# ============================================================
async def main():
    init_db()
    mgr = Manager()
    await mgr.load()

    # تسجيل المعالجات
    register_handlers(bot, mgr, pending)
    register_rank_handlers(bot, mgr)

    await bot.start(bot_token=BOT_TOKEN)
    print("=" * 50)
    print(f"{BOT_NAME} is running")
    print(f"Sessions: {SESSIONS_DIR}")
    print(f"Assistants loaded: {len(mgr.list)}")
    print("=" * 50)
    await idle()


if __name__ == "__main__":
    asyncio.run(main())
