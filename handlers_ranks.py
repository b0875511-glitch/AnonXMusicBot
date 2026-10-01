import os, asyncio
from telethon import events
from telethon.tl.custom import Button
from telethon.errors import MessageNotModifiedError

from config import DEV_ID
from utils import premium, is_admin
from ranks import (
    add_bot_admin, remove_bot_admin, is_bot_admin, list_bot_admins,
    resolve_target
)


async def respond_premium(event, text, buttons=None, **kwargs):
    t, e = premium(text)
    try:
        return await event.respond(
            t, buttons=buttons, formatting_entities=e,
            reply_to=event.message.id, **kwargs
        )
    except Exception:
        return await event.respond(t, buttons=buttons, formatting_entities=e, **kwargs)


def register_rank_handlers(bot, mgr):

    # ============================================================
    # رفع ادمن
    # ============================================================
    @bot.on(events.NewMessage(pattern=r"^رفع (ادمن|أدمن)(?:\s+(.+))?$"))
    async def add_admin_cmd(e):
        if e.is_private:
            return
        if e.sender_id != DEV_ID:
            if not await is_admin(bot, e.chat_id, e.sender_id):
                await respond_premium(e, "هذا الأمر للأدمنية فقط")
                return

        arg = e.pattern_match.group(2)
        tid, name = await resolve_target(bot, e, arg)

        if tid == "BOT_NOT_ALLOWED":
            await respond_premium(e, "لا يمكن رفع البوتات كأدمن")
            return
        if not tid:
            await respond_premium(e, "الاستخدام:\nرفع ادمن @username\nرفع ادمن 123456789\nأو بالرد على رسالة")
            return
        if is_bot_admin(e.chat_id, tid):
            await respond_premium(e, f"{name} أدمن بالفعل")
            return

        add_bot_admin(e.chat_id, tid)
        await respond_premium(e, f"تم رفع {name} كأدمن ✓")

    # ============================================================
    # تنزيل ادمن
    # ============================================================
    @bot.on(events.NewMessage(pattern=r"^تنزيل (ادمن|أدمن)(?:\s+(.+))?$"))
    async def remove_admin_cmd(e):
        if e.is_private:
            return
        if e.sender_id != DEV_ID:
            if not await is_admin(bot, e.chat_id, e.sender_id):
                await respond_premium(e, "هذا الأمر للأدمنية فقط")
                return

        arg = e.pattern_match.group(2)
        tid, name = await resolve_target(bot, e, arg, allow_bots=True)

        if not tid:
            await respond_premium(e, "الاستخدام:\nتنزيل ادمن @username\nتنزيل ادمن 123456789")
            return
        if not is_bot_admin(e.chat_id, tid):
            await respond_premium(e, f"{name} ليس أدمن")
            return

        remove_bot_admin(e.chat_id, tid)
        await respond_premium(e, f"تم تنزيل {name} من الأدمنية ✓")

    # ============================================================
    # الأدمنية
    # ============================================================
    @bot.on(events.NewMessage(pattern=r"^(الأدمنية|الادمنية|الأدمنيه|الادمنيه|الادمن)$"))
    async def admins_list_cmd(e):
        if e.is_private:
            return
        admins = list_bot_admins(e.chat_id)

        txt = "⌯︙ قائمة الأدمنية\n━━━━━━━━━━━━\n"

        if admins:
            for uid in admins:
                try:
                    u = await bot.get_entity(uid)
                    n = f"@{u.username}" if getattr(u, 'username', None) else (u.first_name or str(uid))
                except:
                    n = str(uid)
                txt += f"⭐ {n}\n"
        else:
            txt += "لا يوجد أدمنية"

        await respond_premium(e, txt)