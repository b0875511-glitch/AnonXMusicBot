import os, asyncio, glob, time, platform
from telethon import events, types
from telethon.tl.custom import Button
from telethon.tl.types import DocumentAttributeAudio
from telethon.tl.functions.users import GetFullUserRequest
from telethon.errors import MessageNotModifiedError
from yt_dlp import YoutubeDL

from config import (
    BOT_NAME, DEV_ID, DEV_USERNAME, SOURCE_USERNAME, SOURCE_NAME,
    DL, TEMP, DATA_DIR, YDL_OPTS
)
from utils import (
    premium, bold_num,
    get_setting, set_setting,
    check_subscription, is_admin, get_requested_by, db
)
from ranks import (
    add_bot_admin, remove_bot_admin, is_bot_admin, list_bot_admins
)
from player import (
    current, time_tasks, paused_chats, repeat_modes, seek_offsets,
    download_audio, download_video, clean, qadd, qnext,
    format_play_caption, format_video_caption,
    play_buttons, settings_buttons,
    play, stop, seek_to
)


# ============================================================
# وقت بدء التشغيل
# ============================================================
BOT_START_TIME = time.time()


# ============================================================
# Premium wrappers
# ============================================================
async def send_premium(client, chat_id, text, buttons=None, **kwargs):
    t, e = premium(text)
    return await client.send_message(chat_id, t, buttons=buttons, formatting_entities=e, **kwargs)


async def respond_premium(event, text, buttons=None, **kwargs):
    """الرد على رسالة المستخدم (reply)"""
    t, e = premium(text)
    try:
        return await event.respond(
            t, buttons=buttons, formatting_entities=e,
            reply_to=event.message.id, **kwargs
        )
    except Exception:
        return await event.respond(t, buttons=buttons, formatting_entities=e, **kwargs)


async def edit_premium(event, text, buttons=None, **kwargs):
    t, e = premium(text)
    try:
        await event.edit(t, buttons=buttons, formatting_entities=e, **kwargs)
    except MessageNotModifiedError:
        pass


async def send_premium_file(client, chat_id, file, text, buttons=None, **kwargs):
    t, e = premium(text)
    return await client.send_file(chat_id, file, caption=t, buttons=buttons, formatting_entities=e, **kwargs)


# ============================================================
# ✅ دالة إرسال الصور مع ميزة التشويش (Spoiler)
# ============================================================
async def send_spoiler_photo(client, chat_id, photo_path, caption=None, buttons=None, formatting_entities=None, **kwargs):
    """
    إرسال صورة مع تفعيل ميزة التشويش (Spoiler) في تيليجرام
    """
    try:
        uploaded = await client.upload_file(photo_path)
        media = types.InputMediaUploadedPhoto(uploaded, spoiler=True)
        return await client.send_file(
            chat_id, media, caption=caption, buttons=buttons, 
            formatting_entities=formatting_entities, **kwargs
        )
    except Exception as ex:
        print(f"[SPOILER ERROR] {type(ex).__name__}: {ex}")
        # في حال حدوث خطأ، يتم الإرسال بشكل طبيعي
        return await client.send_file(
            chat_id, photo_path, caption=caption, buttons=buttons, 
            formatting_entities=formatting_entities, **kwargs
        )


# ============================================================
# Subscription message
# ============================================================
async def send_subscription_message(event):
    btns = [
        [Button.url("اشترك في القناة", f"https://t.me/{SOURCE_USERNAME.lstrip('@')}", style='primary')],
        [Button.inline("تحقق من الاشتراك", b"check_sub", style='success')],
    ]
    txt = f"عذراً، يجب الاشتراك في قناة السورس أولاً\nالقناة: {SOURCE_USERNAME}\n\nبعد الاشتراك، اضغط زر التحقق."
    try:
        await respond_premium(event, txt, buttons=btns)
    except Exception as e:
        print(f"[SUB MSG ERROR] {e}")


# ============================================================
# register_handlers
# ============================================================
def register_handlers(bot, mgr, pending):

    # ============================================================
    # check_sub callback
    # ============================================================
    @bot.on(events.CallbackQuery(data=b"check_sub"))
    async def check_sub_cb(e):
        if await check_subscription(bot, e.sender_id):
            await e.answer("تم التحقق", alert=True)
            await e.delete()
        else:
            await e.answer("لم تشترك بعد", alert=True)

    # ============================================================
    # /start
    # ============================================================
    @bot.on(events.NewMessage(pattern=r"^/start$"))
    async def start_cmd(e):
        if not e.is_private:
            return
        if not await check_subscription(bot, e.sender_id, e):
            await send_subscription_message(e)
            return

        me = await bot.get_me()
        bot_name = get_setting("bot_name", BOT_NAME)
        start_photo = get_setting("start_photo", None)

        sender = await e.get_sender()
        user_name = sender.first_name or "User"

        txt = (
            f"⌯︙ Hi? {user_name}. 👑\n"
            f"⌯︙ I am {bot_name}.\n"
            f"⌯︙ To play music in group calls .🎙\n"
            f"⌯︙ To download song from YT Music .🕸️"
        )

        btns = [
            [
                Button.url("اضفني الى مجموعة", f"https://t.me/{me.username}?startgroup=true", style='primary'),
                Button.url("اضفني الى قناة", f"https://t.me/{me.username}?startchannel=true", style='primary'),
            ],
            [
                Button.inline("قـائـمـة الأوامـࢪ", b"cmd_menu", style='success'),
            ],
            [
                # ✅ زر قناة السورس باللون الأحمر (danger)
                Button.url(SOURCE_NAME, f"https://t.me/{SOURCE_USERNAME.lstrip('@')}", style='danger'),
                Button.url("𝐃𝐞𝐯𝐞𝐥𝐨𝐩𝐞𝐫", f"https://t.me/{DEV_USERNAME.lstrip('@')}", style='primary'),
            ],
        ]

        if start_photo and os.path.exists(start_photo):
            await send_premium_file(bot, e.chat_id, start_photo, txt, buttons=btns)
        else:
            await respond_premium(e, txt, buttons=btns)

    # ============================================================
    # الاوامر — قائمة الأوامر المستقلة (بدون رجوع)
    # ============================================================
    @bot.on(events.NewMessage(pattern=r"^(الاوامر|الأوامر|اوامر|أوامر)$"))
    async def help_cmd(e):
        if not await check_subscription(bot, e.sender_id, e):
            await send_subscription_message(e)
            return

        btns = [
            [
                Button.inline("المسـتـخـدمـيـن", b"cmd_users_help", style='primary'),
                Button.inline("المـشـࢪفـيـن", b"cmd_admins_help", style='primary'),
            ],
            [
                Button.inline("الـمـالـك", b"cmd_owner_help", style='success'),
            ],
        ]
        txt = (
            "⌯︙ قائمة الأوامر\n"
            "━━━━━━━━━━━━\n"
            "اختر الفئة:"
        )
        await respond_premium(e, txt, buttons=btns)

    # ============================================================
    # شغل فيديو
    # ============================================================
    @bot.on(events.NewMessage(pattern=r"^(شغل|تشغيل)\s+(فيديو|فديو)\s+(.+)"))
    async def play_video_cmd(e):
        if e.is_private:
            return
        if not await check_subscription(bot, e.sender_id, e):
            await send_subscription_message(e)
            return
        q = e.pattern_match.group(3).strip()
        chat_id = e.chat_id
        requested_by = await get_requested_by(bot, e)

        a = mgr.find(chat_id)
        if a and a.busy:
            m = await respond_premium(e, "🎶")
            file, title, dur = await asyncio.to_thread(download_video, q, DL)
            if not file:
                await m.edit("لم أجد")
                return
            qadd(chat_id, file, title, dur, requested_by, is_video=1)
            await m.edit(f"بالانتظار:\n{title}")
            return

        m = await respond_premium(e, "🎶")
        file, title, dur = await asyncio.to_thread(download_video, q, DL)
        if not file:
            await m.edit("لم أجد")
            return

        caption = format_video_caption(title, dur, requested_by)
        play_photo = get_setting("play_photo", None)
        btns = play_buttons(is_paused=False, repeat_mode="once")
        
        if play_photo and os.path.exists(play_photo):
            # ✅ استخدام التشويش لصورة التشغيل
            t, ent = premium(caption)
            play_msg = await send_spoiler_photo(bot, chat_id, play_photo, caption=t, buttons=btns, formatting_entities=ent)
        else:
            play_msg = await send_premium(bot, chat_id, caption, buttons=btns)

        ok, res = await play(bot, mgr, chat_id, file, title, dur,
                             message_id=play_msg.id, is_video=True,
                             requested_by=requested_by)
        if not ok:
            await play_msg.edit(f"خطأ: {res}")
            return
        await m.delete()

    # ============================================================
    # شغل صوت
    # ============================================================
    @bot.on(events.NewMessage(pattern=r"^(شغل|تشغيل)\s+(.+)"))
    async def play_cmd(e):
        if e.is_private:
            return
        if not await check_subscription(bot, e.sender_id, e):
            await send_subscription_message(e)
            return
        q = e.pattern_match.group(2).strip()
        if q.startswith("فيديو ") or q.startswith("فديو ") or q == "فيديو" or q == "فديو":
            return

        chat_id = e.chat_id
        requested_by = await get_requested_by(bot, e)

        a = mgr.find(chat_id)
        if a and a.busy:
            m = await respond_premium(e, "🎶")
            file, title, dur = await asyncio.to_thread(download_audio, q, DL)
            if not file:
                await m.edit("لم أجد")
                return
            qadd(chat_id, file, title, dur, requested_by, is_video=0)
            await m.edit(f"بالانتظار:\n{title}")
            return

        m = await respond_premium(e, "🎶")
        file, title, dur = await asyncio.to_thread(download_audio, q, DL)
        if not file:
            await m.edit("لم أجد")
            return

        caption = format_play_caption(title, dur, requested_by)
        play_photo = get_setting("play_photo", None)
        btns = play_buttons(is_paused=False, repeat_mode="once")
        
        if play_photo and os.path.exists(play_photo):
            # ✅ استخدام التشويش لصورة التشغيل
            t, ent = premium(caption)
            play_msg = await send_spoiler_photo(bot, chat_id, play_photo, caption=t, buttons=btns, formatting_entities=ent)
        else:
            play_msg = await send_premium(bot, chat_id, caption, buttons=btns)

        ok, res = await play(bot, mgr, chat_id, file, title, dur,
                             message_id=play_msg.id, is_video=False,
                             requested_by=requested_by)
        if not ok:
            await play_msg.edit(f"خطأ: {res}")
            return
        await m.delete()

    @bot.on(events.NewMessage(pattern=r"^(شغل|تشغيل)$"))
    async def play_no_query(e):
        if e.is_private:
            return
        if not await check_subscription(bot, e.sender_id, e):
            await send_subscription_message(e)
            return
        await respond_premium(e, "الاستخدام:\nتشغيل <اسم أو رابط>\nتشغيل فيديو <اسم أو رابط>")

    # ============================================================
    # Seek: تقديم / تاخير / ارجع
    # ============================================================
    @bot.on(events.NewMessage(pattern=r"^(تقديم|تاخير|تأخير|ارجع|أرجع)\s+(\d+)$"))
    async def seek_cmd(e):
        if e.is_private:
            return
        if not await is_admin(bot, e.chat_id, e.sender_id):
            await respond_premium(e, "هذا الأمر للأدمنية فقط")
            return
        cmd = e.pattern_match.group(1)
        seconds = int(e.pattern_match.group(2))
        if not (1 <= seconds <= 3600):
            await respond_premium(e, "الرقم 1-3600")
            return
        info = current.get(e.chat_id)
        if not info:
            await respond_premium(e, "لا يوجد تشغيل")
            return
        a = mgr.find(e.chat_id)
        if not a:
            return
        try:
            t = await a.call.time(e.chat_id)
        except:
            t = 0
        offset = seek_offsets.get(e.chat_id, 0)
        if cmd in ("تقديم",):
            new_start = offset + t + seconds
        else:
            new_start = max(0, offset + t - seconds)
        if new_start >= info["duration"] - 2:
            await respond_premium(e, "تجاوز المدة")
            return
        ok, res = await seek_to(bot, mgr, e.chat_id, new_start, info)
        if ok:
            await respond_premium(e, f"تم إلى {new_start//60:02d}:{new_start%60:02d}")
        else:
            await respond_premium(e, f"خطأ: {res}")

    # ============================================================
    # وقف (pause)
    # ============================================================
    @bot.on(events.NewMessage(pattern=r"^(وقف|توقف|ايقاف مؤقت)$"))
    async def pause_cmd(e):
        if e.is_private:
            return
        if not await is_admin(bot, e.chat_id, e.sender_id):
            await respond_premium(e, "هذا الأمر للأدمنية فقط")
            return
        a = mgr.find(e.chat_id)
        if not a:
            await respond_premium(e, "لا يوجد تشغيل")
            return
        try:
            await a.call.pause(e.chat_id)
            paused_chats[e.chat_id] = True
            await respond_premium(e, "‖ تم الإيقاف المؤقت")
        except Exception as ex:
            await respond_premium(e, f"خطأ: {ex}")

    # ============================================================
    # استئناف (resume)
    # ============================================================
    @bot.on(events.NewMessage(pattern=r"^(استئناف|كمل|كملي|اكمل|أكمل)$"))
    async def resume_cmd(e):
        if e.is_private:
            return
        if not await is_admin(bot, e.chat_id, e.sender_id):
            await respond_premium(e, "هذا الأمر للأدمنية فقط")
            return
        a = mgr.find(e.chat_id)
        if not a:
            await respond_premium(e, "لا يوجد تشغيل")
            return
        try:
            await a.call.resume(e.chat_id)
            paused_chats[e.chat_id] = False
            await respond_premium(e, "▸ تم الاستئناف")
        except Exception as ex:
            await respond_premium(e, f"خطأ: {ex}")

    # ============================================================
    # كتم (mute)
    # ============================================================
    @bot.on(events.NewMessage(pattern=r"^كتم$"))
    async def mute_cmd(e):
        if e.is_private:
            return
        if not await is_admin(bot, e.chat_id, e.sender_id):
            await respond_premium(e, "هذا الأمر للأدمنية فقط")
            return
        a = mgr.find(e.chat_id)
        if not a:
            await respond_premium(e, "لا يوجد تشغيل")
            return
        try:
            await a.call.mute(e.chat_id)
            await respond_premium(e, "تم كتم الصوت")
        except Exception as ex:
            await respond_premium(e, f"خطأ: {ex}")

    # ============================================================
    # الغاء الكتم (unmute)
    # ============================================================
    @bot.on(events.NewMessage(pattern=r"^(الغاء الكتم|إلغاء الكتم|فك الكتم|الغاء كتم|إلغاء كتم)$"))
    async def unmute_cmd(e):
        if e.is_private:
            return
        if not await is_admin(bot, e.chat_id, e.sender_id):
            await respond_premium(e, "هذا الأمر للأدمنية فقط")
            return
        a = mgr.find(e.chat_id)
        if not a:
            await respond_premium(e, "لا يوجد تشغيل")
            return
        try:
            await a.call.unmute(e.chat_id)
            await respond_premium(e, "تم إلغاء الكتم")
        except Exception as ex:
            await respond_premium(e, f"خطأ: {ex}")

    # ============================================================
    # تكرار (loop)
    # ============================================================
    @bot.on(events.NewMessage(pattern=r"^(تكرار|لوب)$"))
    async def loop_cmd(e):
        if e.is_private:
            return
        if not await is_admin(bot, e.chat_id, e.sender_id):
            await respond_premium(e, "هذا الأمر للأدمنية فقط")
            return
        if e.chat_id not in current:
            await respond_premium(e, "لا يوجد تشغيل")
            return
        cur = repeat_modes.get(e.chat_id, "once")
        if cur == "loop":
            repeat_modes[e.chat_id] = "once"
            await respond_premium(e, "↻ تم إلغاء التكرار")
        else:
            repeat_modes[e.chat_id] = "loop"
            await respond_premium(e, "↻ تم تفعيل التكرار")

    # ============================================================
    # حذف [رقم] — حذف من قائمة الانتظار
    # ============================================================
    @bot.on(events.NewMessage(pattern=r"^(حذف|مسح)\s+(\d+)$"))
    async def delete_queue_cmd(e):
        if e.is_private:
            return
        if not await is_admin(bot, e.chat_id, e.sender_id):
            await respond_premium(e, "هذا الأمر للأدمنية فقط")
            return
        idx = int(e.pattern_match.group(2))
        if idx < 1:
            await respond_premium(e, "الرقم يجب أن يكون 1 أو أكثر")
            return
        try:
            c = db()
            rows = c.execute("SELECT id FROM queue WHERE chat_id=? ORDER BY id", (e.chat_id,)).fetchall()
            if idx > len(rows):
                await respond_premium(e, f"لا يوجد سوى {len(rows)} مقطع في القائمة")
                c.close()
                return
            target_id = rows[idx - 1]['id']
            c.execute("DELETE FROM queue WHERE id=?", (target_id,))
            c.commit()
            c.close()
            await respond_premium(e, f"✓ تم حذف المقطع رقم {idx}")
        except Exception as ex:
            await respond_premium(e, f"خطأ: {ex}")

    # ============================================================
    # الانتظار — قائمة التشغيل
    # ============================================================
    @bot.on(events.NewMessage(pattern=r"^(الانتظار|الاغاني|قائمة|قائمه)$"))
    async def queue_cmd(e):
        if e.is_private:
            return
        chat_id = e.chat_id
        info = current.get(chat_id)

        try:
            c = db()
            rows = c.execute(
                "SELECT * FROM queue WHERE chat_id=? ORDER BY id",
                (chat_id,)
            ).fetchall()
            c.close()
        except Exception as ex:
            await respond_premium(e, f"خطأ: {ex}")
            return

        txt = "⌯︙ قائمة التشغيل\n━━━━━━━━━━━━\n\n"

        if info:
            try:
                a = mgr.find(chat_id)
                t = await a.call.time(chat_id) if a else 0
            except:
                t = 0
            offset = seek_offsets.get(chat_id, 0)
            display_t = t + offset
            dur = info.get("duration", 0)
            txt += f"▸ **الحالية:**\n"
            txt += f"  {info['title']}\n"
            txt += f"  {display_t//60:02d}:{display_t%60:02d} / {dur//60:02d}:{dur%60:02d}\n\n"
        else:
            txt += "لا يوجد تشغيل حالياً\n\n"

        if rows:
            txt += f"▤ **قائمة الانتظار ({len(rows)}):**\n"
            for i, row in enumerate(rows, 1):
                dur = row['duration'] or 0
                txt += f"  {i}. {row['title']} — {dur//60:02d}:{dur%60:02d}\n"
        else:
            txt += "▤ القائمة فارغة"

        await respond_premium(e, txt)

    # ============================================================
    # بنك — معلومات البوت (للمطور فقط)
    # ============================================================
    @bot.on(events.NewMessage(pattern=r"^(بنك|bank|ping)$"))
    async def bank_cmd(e):
        if e.sender_id != DEV_ID:
            return

        uptime_seconds = int(time.time() - BOT_START_TIME)
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60

        uptime_str = ""
        if days > 0:
            uptime_str += f"{days}ي "
        if hours > 0:
            uptime_str += f"{hours}س "
        uptime_str += f"{minutes}د {seconds}ث"

        t1 = time.time()
        try:
            msg = await e.respond("▸")
            ping_ms = int((time.time() - t1) * 1000)
            try:
                await msg.delete()
            except:
                pass
        except:
            ping_ms = 0

        total_assistants = len(mgr.list)
        busy_assistants = sum(1 for a in mgr.list if a.busy)
        free_assistants = total_assistants - busy_assistants

        active_chats = len(current)

        try:
            c = db()
            total_queue = c.execute("SELECT COUNT(*) FROM queue").fetchone()[0]
            c.close()
        except:
            total_queue = 0

        txt = (
            f"⌯︙ بنك البوت\n"
            f"━━━━━━━━━━━━\n"
            f"▸ وقت التشغيل: {uptime_str}\n"
            f"▸ سرعة الاستجابة: {ping_ms}ms\n"
            f"▸ المساعدون: {total_assistants}\n"
            f"  ✓ متاح: {free_assistants}\n"
            f"  ✗ مشغول: {busy_assistants}\n"
            f"♫ مجموعات نشطة: {active_chats}\n"
            f"▤ في الانتظار: {total_queue}\n"
            f"▸ النظام: {platform.system()}\n"
            f"▸ Python: {platform.python_version()}"
        )
        await respond_premium(e, txt)

    # ============================================================
    # يوت
    # ============================================================
    @bot.on(events.NewMessage(pattern=r"^يوت\s+(.+)"))
    async def yt_download(e):
        if not await check_subscription(bot, e.sender_id, e):
            await send_subscription_message(e)
            return
        query = e.pattern_match.group(1).strip()
        msg = await respond_premium(e, "🎶")
        try:
            clean(TEMP)
            opts = dict(YDL_OPTS)
            opts['outtmpl'] = f'{TEMP}/%(id)s.%(ext)s'
            with YoutubeDL(opts) as y:
                i = y.extract_info(query, download=True)
                v = i['entries'][0] if 'entries' in i else i
                vid = v.get('id')
                title = v.get('title') or vid
                dur = v.get('duration') or 0
            fs = glob.glob(f"{TEMP}/{vid}.mp3") or glob.glob(f"{TEMP}/{vid}.*")
            if not fs:
                await msg.edit("لم أجد")
                return
            file_path = fs[0]
            me = await bot.get_me()
            bot_name = get_setting("bot_name", BOT_NAME)
            dur_str = f"{dur//60:02d}:{dur%60:02d}"
            bot_caption = f'<a href="https://t.me/{me.username}">{bot_name}</a> ~ {dur_str}'
            await bot.send_file(e.chat_id, file_path,
                                attributes=[DocumentAttributeAudio(duration=dur, title=title, performer="YouTube")],
                                caption=bot_caption, parse_mode='html',
                                reply_to=e.message.id)
            await msg.delete()
            try:
                os.remove(file_path)
            except:
                pass
        except Exception as ex:
            await msg.edit(f"خطأ: {ex}")

    # ============================================================
    # ايقاف
    # ============================================================
    @bot.on(events.NewMessage(pattern=r"^(ايقاف|انهاء|إنهاء|اسكت|كافي)$"))
    async def stop_cmd(e):
        if e.is_private:
            return
        if not await is_admin(bot, e.chat_id, e.sender_id):
            await respond_premium(e, "هذا الأمر للأدمنية فقط")
            return
        info = current.get(e.chat_id)
        is_video = info.get("is_video", False) if info else False
        ok = await stop(mgr, e.chat_id)
        if ok:
            if is_video:
                await respond_premium(e, "تم ايقاف تشغيل الفيديو")
            else:
                await respond_premium(e, "تم ايقاف تشغيل الأغنية")
        else:
            await respond_premium(e, "لا يوجد تشغيل")

    # ============================================================
    # تخطي (مع صورة) ✅
    # ============================================================
    @bot.on(events.NewMessage(pattern=r"^تخطي$"))
    async def skip_cmd(e):
        if e.is_private:
            return
        if not await is_admin(bot, e.chat_id, e.sender_id):
            await respond_premium(e, "هذا الأمر للأدمنية فقط")
            return
        n = qnext(e.chat_id)
        if not n:
            await stop(mgr, e.chat_id)
            await respond_premium(e, "لا يوجد التالي")
            return
        old = time_tasks.pop(e.chat_id, None)
        if old and old.get("task"):
            old["task"].cancel()
        paused_chats.pop(e.chat_id, None)
        seek_offsets.pop(e.chat_id, None)
        is_video = bool(n.get('is_video', 0))
        btns = play_buttons(is_paused=False, repeat_mode="once")
        if is_video:
            caption = format_video_caption(n['title'], n.get('duration', 0), n.get('requested_by', 'Unknown'))
        else:
            caption = format_play_caption(n['title'], n.get('duration', 0), n.get('requested_by', 'Unknown'))

        # ✅ استخدم صورة التشغيل إن وجدت مع التشويش
        play_photo = get_setting("play_photo", None)
        if play_photo and os.path.exists(play_photo):
            t, ent = premium(caption)
            msg = await send_spoiler_photo(bot, e.chat_id, play_photo, caption=t, buttons=btns, formatting_entities=ent)
        else:
            msg = await send_premium(bot, e.chat_id, caption, buttons=btns)

        await play(bot, mgr, e.chat_id, n['file'], n['title'], n['duration'],
                   message_id=msg.id, is_video=is_video,
                   requested_by=n.get('requested_by', 'Unknown'))

    # ============================================================
    # سورس
    # ============================================================
    @bot.on(events.NewMessage(pattern=r"^(سورس|السورس)$"))
    async def source_cmd(e):
        if not await check_subscription(bot, e.sender_id, e):
            await send_subscription_message(e)
            return
        source_photo = get_setting("source_photo", None)
        
        # ✅ زر قناة السورس باللون الأحمر (danger)
        btns = [[Button.url(SOURCE_NAME, f"https://t.me/{SOURCE_USERNAME.lstrip('@')}", style='danger')]]
        
        if source_photo and os.path.exists(source_photo):
            # ✅ استخدام التشويش لصورة السورس
            await send_spoiler_photo(bot, e.chat_id, source_photo, caption=SOURCE_NAME, buttons=btns)
        else:
            await respond_premium(e, SOURCE_NAME, buttons=btns)

    # ============================================================
    # المطور
    # ============================================================
    @bot.on(events.NewMessage(pattern=r"^المطور$"))
    async def dev_cmd(e):
        if not await check_subscription(bot, e.sender_id, e):
            await send_subscription_message(e)
            return
        try:
            user = await bot.get_entity(DEV_USERNAME)
            name = user.first_name or "المطور"
            bio = ""
            try:
                full = await bot(GetFullUserRequest(DEV_USERNAME))
                bio = full.full_user.about or ""
            except:
                pass
            txt = f"Dev Bot ↦ {name}\n━━━━━━━━━━━━\nDev ↦ {DEV_USERNAME}\nBio ↦ {bio}"
            btns = [[Button.url("𝐃𝐞𝐯𝐞𝐥𝐨𝐩𝐞𝐫", f"https://t.me/{DEV_USERNAME.lstrip('@')}", style='primary')]]
            
            if user.photo:
                p = await bot.download_profile_photo(user, file=os.path.join(DATA_DIR, "dev.jpg"))
                # ✅ استخدام التشويش لصورة المطور
                await send_spoiler_photo(bot, e.chat_id, p, caption=txt, buttons=btns)
            else:
                await respond_premium(e, txt, buttons=btns)
        except Exception as ex:
            await respond_premium(e, f"خطأ: {ex}")

    # ============================================================
    # مسار /start — قائمة الأوامر
    # ============================================================
    @bot.on(events.CallbackQuery(data=b"cmd_menu"))
    async def cmd_menu_cb(e):
        """القائمة الرئيسية — من زر /start (مع رجوع لـ /start)"""
        btns = [
            [
                Button.inline("المسـتـخـدمـيـن", b"cmd_users_start", style='primary'),
                Button.inline("المـشـࢪفـيـن", b"cmd_admins_start", style='primary'),
            ],
            [
                Button.inline("الـمـالـك", b"cmd_owner_start", style='success'),
            ],
            [
                Button.inline("رجوع", b"cmd_back_start", style='danger'),
            ],
        ]
        txt = (
            "⌯︙ قائمة الأوامر\n"
            "━━━━━━━━━━━━\n"
            "اختر الفئة:"
        )
        try:
            t, ent = premium(txt)
            await e.edit(t, buttons=btns, formatting_entities=ent)
        except MessageNotModifiedError:
            pass
        await e.answer()

    @bot.on(events.CallbackQuery(data=b"cmd_users_start"))
    async def cmd_users_start_cb(e):
        txt = (
            "⌯︙ أوامر المستخدمين\n"
            "━━━━━━━━━━━━\n\n"
            "**قائمة التشغيل:**\n"
            "⌯︙ شغل اسم الأغنية — تشغيل مقطع صوتي\n"
            "⌯︙ شغل فيديو اسم الفيديو — تشغيل فيديو مرئي\n"
            "⌯︙ الانتظار — عرض قائمة التشغيل\n"
            "⌯︙ يوت اسم الأغنية — يحمل الأغنية ويرسلها بصيغة MP3"
        )
        btns = [[Button.inline("رجوع", b"cmd_menu", style='primary')]]
        try:
            t, ent = premium(txt)
            await e.edit(t, buttons=btns, formatting_entities=ent)
        except MessageNotModifiedError:
            pass
        await e.answer()

    @bot.on(events.CallbackQuery(data=b"cmd_admins_start"))
    async def cmd_admins_start_cb(e):
        txt = (
            "⌯︙ أوامر المشرفين\n"
            "━━━━━━━━━━━━\n\n"
            "**التحكم بالتشغيل:**\n"
            "⌯︙ تخطي — لتخطي المقطع الحالي\n"
            "⌯︙ وقف — إيقاف التشغيل مؤقتاً\n"
            "⌯︙ استئناف — استئناف التشغيل\n"
            "⌯︙ انهاء — إيقاف التشغيل نهائياً\n\n"
            "**أدوات إضافية:**\n"
            "⌯︙ تقديم [عدد الثواني] — لتقديم وقت المقطع\n"
            "⌯︙ ارجع [عدد الثواني] — لإرجاع وقت المقطع\n"
            "⌯︙ تكرار — تكرار المقطع الحالي\n"
            "⌯︙ حذف [رقم] — حذف مقطع من القائمة\n"
            "⌯︙ كتم — كتم صوت البوت بالمكالمة\n"
            "⌯︙ الغاء الكتم — إلغاء كتم الصوت"
        )
        btns = [[Button.inline("رجوع", b"cmd_menu", style='primary')]]
        try:
            t, ent = premium(txt)
            await e.edit(t, buttons=btns, formatting_entities=ent)
        except MessageNotModifiedError:
            pass
        await e.answer()

    @bot.on(events.CallbackQuery(data=b"cmd_owner_start"))
    async def cmd_owner_start_cb(e):
        txt = (
            "⌯︙ أوامر المالك\n"
            "━━━━━━━━━━━━\n\n"
            "**الادمنيه:**\n"
            "⌯︙ رفع ادمن — منح صلاحية ادمن للتحكم\n"
            "⌯︙ تنزيل ادمن — سحب صلاحية الادمن\n"
            "⌯︙ الادمنيه — قائمة الادمنيه المُصرح لهم"
        )
        btns = [[Button.inline("رجوع", b"cmd_menu", style='primary')]]
        try:
            t, ent = premium(txt)
            await e.edit(t, buttons=btns, formatting_entities=ent)
        except MessageNotModifiedError:
            pass
        await e.answer()

    # ============================================================
    # مسار الاوامر — قائمة الأوامر المستقلة
    # ============================================================
    @bot.on(events.CallbackQuery(data=b"cmd_users_help"))
    async def cmd_users_help_cb(e):
        txt = (
            "⌯︙ أوامر المستخدمين\n"
            "━━━━━━━━━━━━\n\n"
            "**قائمة التشغيل:**\n"
            "⌯︙ شغل اسم الأغنية — تشغيل مقطع صوتي\n"
            "⌯︙ شغل فيديو اسم الفيديو — تشغيل فيديو مرئي\n"
            "⌯︙ الانتظار — عرض قائمة التشغيل\n"
            "⌯︙ يوت اسم الأغنية — يحمل الأغنية ويرسلها بصيغة MP3"
        )
        btns = [[Button.inline("رجوع", b"cmd_back_help", style='primary')]]
        try:
            t, ent = premium(txt)
            await e.edit(t, buttons=btns, formatting_entities=ent)
        except MessageNotModifiedError:
            pass
        await e.answer()

    @bot.on(events.CallbackQuery(data=b"cmd_admins_help"))
    async def cmd_admins_help_cb(e):
        txt = (
            "⌯︙ أوامر المشرفين\n"
            "━━━━━━━━━━━━\n\n"
            "**التحكم بالتشغيل:**\n"
            "⌯︙ تخطي — لتخطي المقطع الحالي\n"
            "⌯︙ وقف — إيقاف التشغيل مؤقتاً\n"
            "⌯︙ استئناف — استئناف التشغيل\n"
            "⌯︙ انهاء — إيقاف التشغيل نهائياً\n\n"
            "**أدوات إضافية:**\n"
            "⌯︙ تقديم [عدد الثواني] — لتقديم وقت المقطع\n"
            "⌯︙ ارجع [عدد الثواني] — لإرجاع وقت المقطع\n"
            "⌯︙ تكرار — تكرار المقطع الحالي\n"
            "⌯︙ حذف [رقم] — حذف مقطع من القائمة\n"
            "⌯︙ كتم — كتم صوت البوت بالمكالمة\n"
            "⌯︙ الغاء الكتم — إلغاء كتم الصوت"
        )
        btns = [[Button.inline("رجوع", b"cmd_back_help", style='primary')]]
        try:
            t, ent = premium(txt)
            await e.edit(t, buttons=btns, formatting_entities=ent)
        except MessageNotModifiedError:
            pass
        await e.answer()

    @bot.on(events.CallbackQuery(data=b"cmd_owner_help"))
    async def cmd_owner_help_cb(e):
        txt = (
            "⌯︙ أوامر المالك\n"
            "━━━━━━━━━━━━\n\n"
            "**الادمنيه:**\n"
            "⌯︙ رفع ادمن — منح صلاحية ادمن للتحكم\n"
            "⌯︙ تنزيل ادمن — سحب صلاحية الادمن\n"
            "⌯︙ الادمنيه — قائمة الادمنيه المُصرح لهم"
        )
        btns = [[Button.inline("رجوع", b"cmd_back_help", style='primary')]]
        try:
            t, ent = premium(txt)
            await e.edit(t, buttons=btns, formatting_entities=ent)
        except MessageNotModifiedError:
            pass
        await e.answer()

    @bot.on(events.CallbackQuery(data=b"cmd_back_help"))
    async def cmd_back_help_cb(e):
        """العودة إلى قائمة الأوامر (مسار الاوامر — بدون رجوع)"""
        btns = [
            [
                Button.inline("المسـتـخـدمـيـن", b"cmd_users_help", style='primary'),
                Button.inline("المـشـࢪفـيـن", b"cmd_admins_help", style='primary'),
            ],
            [
                Button.inline("الـمـالـك", b"cmd_owner_help", style='success'),
            ],
        ]
        txt = (
            "⌯︙ قائمة الأوامر\n"
            "━━━━━━━━━━━━\n"
            "اختر الفئة:"
        )
        try:
            t, ent = premium(txt)
            await e.edit(t, buttons=btns, formatting_entities=ent)
        except MessageNotModifiedError:
            pass
        await e.answer()

    @bot.on(events.CallbackQuery(data=b"cmd_back_start"))
    async def cmd_back_start_cb(e):
        me = await bot.get_me()
        bot_name = get_setting("bot_name", BOT_NAME)
        start_photo = get_setting("start_photo", None)

        sender = await e.get_sender()
        user_name = sender.first_name or "User"

        txt = (
            f"⌯︙ Hi? {user_name}. 👑\n"
            f"⌯︙ I am {bot_name}.\n"
            f"⌯︙ To play music in group calls .🎙\n"
            f"⌯︙ To download song from YT Music .🕸️"
        )

        btns = [
            [
                Button.url("اضفني الى مجموعة", f"https://t.me/{me.username}?startgroup=true", style='primary'),
                Button.url("اضفني الى قناة", f"https://t.me/{me.username}?startchannel=true", style='primary'),
            ],
            [
                Button.inline("قـائـمـة الأوامـࢪ", b"cmd_menu", style='success'),
            ],
            [
                # ✅ زر قناة السورس باللون الأحمر (danger)
                Button.url(SOURCE_NAME, f"https://t.me/{SOURCE_USERNAME.lstrip('@')}", style='danger'),
                Button.url("𝐃𝐞𝐯𝐞𝐥𝐨𝐩𝐞𝐫", f"https://t.me/{DEV_USERNAME.lstrip('@')}", style='primary'),
            ],
        ]

        try:
            t, ent = premium(txt)
            await e.edit(t, buttons=btns, formatting_entities=ent)
        except MessageNotModifiedError:
            pass
        await e.answer()

    # ============================================================
    # /admin لوحة المطور
    # ============================================================
    @bot.on(events.NewMessage(pattern=r"^/admin$"))
    async def admin_panel(e):
        if not e.is_private or e.sender_id != DEV_ID:
            return
        btns = [
            [Button.inline("اضافة مساعد", b"add_ass", style='success'),
             Button.inline("حذف مساعد", b"del_ass", style='danger')],
            [Button.inline("توحيد الصورة", b"uni_photo", style='primary'),
             Button.inline("توحيد الاسم", b"uni_name", style='primary')],
            [Button.inline("عرض المساعدين", b"list_ass", style='primary')],
            [Button.inline("تعيين اسم البوت", b"set_bot_name", style='primary')],
            [Button.inline("تعيين صورة /start", b"set_start_photo", style='primary')],
            [Button.inline("تعيين صورة سورس", b"set_source_photo", style='primary')],
            [Button.inline("تعيين صورة التشغيل", b"set_play_photo", style='primary')],
        ]
        await respond_premium(e, "لوحة المطور:", buttons=btns)

    @bot.on(events.CallbackQuery(data=b"add_ass"))
    async def add_ass(e):
        if e.sender_id != DEV_ID:
            return
        pending[e.sender_id] = "waiting_session"
        await edit_premium(e, "أرسل Session String:")

    @bot.on(events.CallbackQuery(data=b"uni_photo"))
    async def uni_photo(e):
        if e.sender_id != DEV_ID:
            return
        pending[e.sender_id] = "waiting_photo"
        await edit_premium(e, "أرسل الصورة:")

    @bot.on(events.CallbackQuery(data=b"uni_name"))
    async def uni_name(e):
        if e.sender_id != DEV_ID:
            return
        pending[e.sender_id] = "waiting_name"
        await edit_premium(e, "أرسل الاسم:")

    @bot.on(events.CallbackQuery(data=b"list_ass"))
    async def list_ass(e):
        if e.sender_id != DEV_ID:
            return
        if not mgr.list:
            await edit_premium(e, "لا يوجد")
            return
        txt = "\n".join([f"{a.name} (@{a.uname})" for a in mgr.list])
        await edit_premium(e, txt)

    @bot.on(events.CallbackQuery(data=b"del_ass"))
    async def del_ass(e):
        if e.sender_id != DEV_ID:
            return
        btns = []
        for a in mgr.list:
            btns.append([Button.inline(a.name, f"del_{a.uid}".encode(), style='danger')])
        btns.append([Button.inline("حذف الكل", b"del_all", style='danger')])
        await edit_premium(e, "اختر:", buttons=btns)

    @bot.on(events.CallbackQuery(data=b"del_all"))
    async def del_all(e):
        if e.sender_id != DEV_ID:
            return
        count = await mgr.remove_all()
        await edit_premium(e, f"تم حذف {count}")

    @bot.on(events.CallbackQuery(pattern=rb"^del_(\d+)$"))
    async def del_specific(e):
        if e.sender_id != DEV_ID:
            return
        uid = int(e.pattern_match.group(1))
        await mgr.remove(uid)
        await edit_premium(e, "تم الحذف")

    @bot.on(events.CallbackQuery(data=b"set_bot_name"))
    async def set_bot_name_cb(e):
        if e.sender_id != DEV_ID:
            return
        pending[e.sender_id] = "waiting_bot_name"
        await edit_premium(e, "أرسل اسم البوت:")

    @bot.on(events.CallbackQuery(data=b"set_start_photo"))
    async def set_start_photo_cb(e):
        if e.sender_id != DEV_ID:
            return
        pending[e.sender_id] = "waiting_start_photo"
        await edit_premium(e, "أرسل صورة /start:")

    @bot.on(events.CallbackQuery(data=b"set_source_photo"))
    async def set_source_photo_cb(e):
        if e.sender_id != DEV_ID:
            return
        pending[e.sender_id] = "waiting_source_photo"
        await edit_premium(e, "أرسل صورة السورس:")

    @bot.on(events.CallbackQuery(data=b"set_play_photo"))
    async def set_play_photo_cb(e):
        if e.sender_id != DEV_ID:
            return
        pending[e.sender_id] = "waiting_play_photo"
        await edit_premium(e, "أرسل صورة التشغيل:")

    # ============================================================
    # handle_input
    # ============================================================
    @bot.on(events.NewMessage())
    async def handle_input(e):
        if not e.is_private or e.sender_id != DEV_ID:
            return
        action = pending.get(e.sender_id)
        if not action:
            return
        pending.pop(e.sender_id, None)

        if action == "waiting_session":
            ok, name = await mgr.add(e.text.strip())
            await respond_premium(e, f"تمت اضافة: {name}" if ok else f"خطأ: {name}")
        elif action == "waiting_photo":
            if not e.photo:
                return
            path = await e.download_media(file=os.path.join(DATA_DIR, "unified.jpg"))
            await mgr.unify_photo(path)
            await respond_premium(e, "تم")
        elif action == "waiting_name":
            await mgr.unify_name(e.text.strip())
            await respond_premium(e, "تم")
        elif action == "waiting_bot_name":
            set_setting("bot_name", e.text.strip())
            await respond_premium(e, "تم")
        elif action == "waiting_start_photo":
            if not e.photo:
                return
            path = await e.download_media(file=os.path.join(DATA_DIR, "start.jpg"))
            set_setting("start_photo", path)
            await respond_premium(e, "تم")
        elif action == "waiting_source_photo":
            if not e.photo:
                return
            path = await e.download_media(file=os.path.join(DATA_DIR, "source.jpg"))
            set_setting("source_photo", path)
            await respond_premium(e, "تم")
        elif action == "waiting_play_photo":
            if not e.photo:
                return
            path = await e.download_media(file=os.path.join(DATA_DIR, "play.jpg"))
            set_setting("play_photo", path)
            await respond_premium(e, "تم")

    # ============================================================
    # أزرار التشغيل
    # ============================================================
    @bot.on(events.CallbackQuery())
    async def play_cb(e):
        a = mgr.find(e.chat_id)
        if not a:
            return await e.answer("لا يوجد تشغيل")
        d = e.data.decode()
        admin_only = ["stop", "pause", "resume", "skip", "loop", "once", "back_15", "fwd_15"]
        if d in admin_only:
            if not await is_admin(bot, e.chat_id, e.sender_id):
                return await e.answer("هذا الأمر للأدمنية فقط", alert=True)
        try:
            if d == "pause":
                await a.call.pause(e.chat_id)
                paused_chats[e.chat_id] = True
                rm = repeat_modes.get(e.chat_id, "once")
                try:
                    await e.edit(buttons=play_buttons(is_paused=True, repeat_mode=rm))
                except MessageNotModifiedError:
                    pass
                await e.answer("‖")

            elif d == "resume":
                await a.call.resume(e.chat_id)
                paused_chats[e.chat_id] = False
                rm = repeat_modes.get(e.chat_id, "once")
                try:
                    await e.edit(buttons=play_buttons(is_paused=False, repeat_mode=rm))
                except MessageNotModifiedError:
                    pass
                await e.answer("▸")

            elif d == "stop":
                info = current.get(e.chat_id)
                is_video = info.get("is_video", False) if info else False
                await stop(mgr, e.chat_id)
                if is_video:
                    await edit_premium(e, "تم ايقاف تشغيل الفيديو")
                else:
                    await edit_premium(e, "تم ايقاف تشغيل الأغنية")

            elif d == "loop":
                cur = repeat_modes.get(e.chat_id, "once")
                repeat_modes[e.chat_id] = "once" if cur == "loop" else "loop"
                await e.answer("↻")
                try:
                    await e.edit(buttons=play_buttons(
                        is_paused=paused_chats.get(e.chat_id, False),
                        repeat_mode=repeat_modes.get(e.chat_id, "once")
                    ))
                except MessageNotModifiedError:
                    pass

            elif d == "once":
                repeat_modes[e.chat_id] = "once"
                try:
                    await e.edit(buttons=play_buttons(
                        is_paused=paused_chats.get(e.chat_id, False),
                        repeat_mode="once"
                    ))
                except MessageNotModifiedError:
                    pass
                await e.answer("➊")

            elif d in ("back_15", "fwd_15"):
                seconds = -15 if d == "back_15" else 15
                info = current.get(e.chat_id)
                if not info:
                    return await e.answer("لا يوجد تشغيل", alert=True)
                try:
                    t = await a.call.time(e.chat_id)
                except:
                    t = 0
                offset = seek_offsets.get(e.chat_id, 0)
                new_start = max(0, offset + t + seconds)
                if new_start >= info["duration"] - 2:
                    return await e.answer("تجاوز المدة", alert=True)
                ok, res = await seek_to(bot, mgr, e.chat_id, new_start, info)
                if ok:
                    await e.answer(f"{'+' if seconds > 0 else '-'}{abs(seconds)}s")
                else:
                    await e.answer(f"خطأ: {res}", alert=True)

            elif d == "settings":
                info = current.get(e.chat_id)
                if not info:
                    return await e.answer("لا يوجد تشغيل", alert=True)
                try:
                    t = await a.call.time(e.chat_id)
                except:
                    t = 0
                offset = seek_offsets.get(e.chat_id, 0)
                display_t = t + offset
                is_paused = paused_chats.get(e.chat_id, False)
                rm = repeat_modes.get(e.chat_id, "once")
                txt = (
                    f"☰ الإعدادات\n"
                    f"━━━━━━━━━━\n"
                    f"الأغنية: {info['title']}\n"
                    f"الوقت: {display_t//60:02d}:{display_t%60:02d} / {info['duration']//60:02d}:{info['duration']%60:02d}\n"
                    f"الحالة: {'متوقف' if is_paused else 'يعمل'}\n"
                    f"التكرار: {'مفعّل' if rm == 'loop' else 'معطّل'}"
                )
                t_p, e_p = premium(txt)
                try:
                    await e.edit(t_p, buttons=settings_buttons(), formatting_entities=e_p)
                except MessageNotModifiedError:
                    pass

            elif d == "settings_back":
                info = current.get(e.chat_id)
                if not info:
                    return await e.answer("لا يوجد تشغيل", alert=True)
                try:
                    t = await a.call.time(e.chat_id)
                except:
                    t = 0
                offset = seek_offsets.get(e.chat_id, 0)
                display_t = t + offset
                time_str = bold_num(f"{display_t//60:02d}:{display_t%60:02d}")
                is_paused = paused_chats.get(e.chat_id, False)
                rm = repeat_modes.get(e.chat_id, "once")
                if info.get("is_video"):
                    caption = format_video_caption(info['title'], info.get('duration', 0), info.get('requested_by', 'Unknown'))
                else:
                    caption = format_play_caption(info['title'], info.get('duration', 0), info.get('requested_by', 'Unknown'))
                btns = play_buttons(is_paused=is_paused, repeat_mode=rm, time_str=time_str)
                t_p, e_p = premium(caption)
                try:
                    await e.edit(t_p, buttons=btns, formatting_entities=e_p)
                except MessageNotModifiedError:
                    pass

            elif d == "time":
                try:
                    t = await a.call.time(e.chat_id)
                    offset = seek_offsets.get(e.chat_id, 0)
                    await e.answer(bold_num(f"{(t+offset)//60:02d}:{(t+offset)%60:02d}"))
                except:
                    await e.answer("غير متاح")

            elif d == "skip":
                n = qnext(e.chat_id)
                if n:
                    old = time_tasks.pop(e.chat_id, None)
                    if old and old.get("task"):
                        old["task"].cancel()
                    paused_chats.pop(e.chat_id, None)
                    seek_offsets.pop(e.chat_id, None)

                    # ✅ احذف الرسالة القديمة
                    try:
                        await e.delete()
                    except:
                        pass

                    is_video = bool(n.get('is_video', 0))
                    btns = play_buttons(is_paused=False, repeat_mode="once")
                    if is_video:
                        caption = format_video_caption(n['title'], n.get('duration', 0), n.get('requested_by', 'Unknown'))
                    else:
                        caption = format_play_caption(n['title'], n.get('duration', 0), n.get('requested_by', 'Unknown'))

                    # ✅ أرسل رسالة جديدة مع الصورة والتشويش
                    play_photo = get_setting("play_photo", None)
                    if play_photo and os.path.exists(play_photo):
                        t, ent = premium(caption)
                        msg = await send_spoiler_photo(bot, e.chat_id, play_photo, caption=t, buttons=btns, formatting_entities=ent)
                    else:
                        msg = await send_premium(bot, e.chat_id, caption, buttons=btns)

                    await play(bot, mgr, e.chat_id, n['file'], n['title'], n['duration'],
                               message_id=msg.id, is_video=is_video,
                               requested_by=n.get('requested_by', 'Unknown'))
                else:
                    await stop(mgr, e.chat_id)
                    await edit_premium(e, "لا يوجد التالي")
            else:
                await e.answer()
        except Exception as ex:
            await e.answer(f"خطأ: {ex}")

    # ============================================================
    # إضافة البوت
    # ============================================================
    @bot.on(events.ChatAction())
    async def bot_added_to_group(e):
        try:
            if not (e.user_added or e.user_joined):
                return
            me = await bot.get_me()
            added_user = await e.get_user()
            if not added_user or added_user.id != me.id:
                return
            chat = await e.get_chat()
            title = chat.title or "المجموعة"
            await respond_premium(e, f"تم اضافة البوت الى: {title}")
        except Exception as ex:
            print(f"[BOT ADDED] {type(ex).__name__}: {ex}")

    @bot.on(events.NewMessage(pattern=r"^تفعيل$"))
    async def manual_join(e):
        if e.is_private or e.sender_id != DEV_ID:
            return
        from player import ensure_assistant_in_chat
        a = mgr.free() or (mgr.list[0] if mgr.list else None)
        if not a:
            await respond_premium(e, "لا يوجد مساعدين")
            return
        msg = await respond_premium(e, f"جاري انضمام {a.name}...")
        ok, result = await ensure_assistant_in_chat(bot, e.chat_id, a, mgr)
        await msg.edit(f"انضم: {a.name}" if ok else f"فشل: {result}")

    @bot.on(events.ChatAction())
    async def welcome_dev(e):
        try:
            if not (e.user_added or e.user_joined):
                return
            user = await e.get_user()
            if user and user.username and f"@{user.username}".lower() == DEV_USERNAME.lower():
                await respond_premium(e, f"اهلا بك سيدي مطور السورس\n{DEV_USERNAME}")
        except:
            pass