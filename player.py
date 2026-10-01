import os, glob, asyncio
from yt_dlp import YoutubeDL
from telethon.tl.custom import Button

from config import DL, TEMP, YDL_OPTS, YDL_VIDEO_OPTS
from utils import db, bold_num, get_setting, premium


# ============================================================
# الحالة العامة
# ============================================================
current = {}
time_tasks = {}
video_streams = {}
paused_chats = {}
repeat_modes = {}
seek_offsets = {}


# ============================================================
# تحميل
# ============================================================
def clean(folder, exclude=None):
    for f in glob.glob(f"{folder}/*"):
        if f != exclude:
            try:
                os.remove(f)
            except:
                pass


def download_audio(query, folder=DL):
    opts = dict(YDL_OPTS)
    opts['outtmpl'] = f'{folder}/%(id)s.%(ext)s'
    with YoutubeDL(opts) as y:
        try:
            i = y.extract_info(query, download=True)
            v = i['entries'][0] if 'entries' in i else i
            vid = v.get('id')
            title = v.get('title') or vid
            dur = v.get('duration') or 0
            fs = glob.glob(f"{folder}/{vid}.mp3") or glob.glob(f"{folder}/{vid}.*")
            return (fs[0], title, dur) if fs else (None, None, 0)
        except Exception as e:
            print(f"[YT] {type(e).__name__}: {e}")
            return None, None, 0


def download_video(query, folder=DL):
    opts = dict(YDL_VIDEO_OPTS)
    opts['outtmpl'] = f'{folder}/%(id)s.%(ext)s'
    with YoutubeDL(opts) as y:
        try:
            i = y.extract_info(query, download=True)
            v = i['entries'][0] if 'entries' in i else i
            vid = v.get('id')
            title = v.get('title') or vid
            dur = v.get('duration') or 0
            fs = glob.glob(f"{folder}/{vid}.mp4") or glob.glob(f"{folder}/{vid}.mkv") or glob.glob(f"{folder}/{vid}.*")
            return (fs[0], title, dur) if fs else (None, None, 0)
        except Exception as e:
            print(f"[YT VIDEO] {type(e).__name__}: {e}")
            return None, None, 0


# ============================================================
# Queue helpers
# ============================================================
def qadd(chat, file, title, dur=0, requested_by="Unknown", is_video=0):
    c = db()
    c.execute("INSERT INTO queue(chat_id,file,title,duration,requested_by,is_video) VALUES(?,?,?,?,?,?)",
              (chat, file, title, dur, requested_by, is_video))
    c.commit()
    c.close()


def qnext(chat):
    c = db()
    r = c.execute("SELECT * FROM queue WHERE chat_id=? ORDER BY id LIMIT 1", (chat,)).fetchone()
    if r:
        c.execute("DELETE FROM queue WHERE id=?", (r['id'],))
        c.commit()
    c.close()
    return dict(r) if r else None


# ============================================================
# Captions
# ============================================================
def format_play_caption(title, duration=0, requested_by="Unknown"):
    dur_str = bold_num(f"{duration//60:02d}:{duration%60:02d}") if duration > 0 else bold_num("00:00")
    return f"🕸️ 𝐋𝐈𝐕𝐄 🎵\n⌯︙ 𝖳𝗂𝗍𝗅𝖾 : {title}\n⌯︙ 𝖣𝗎𝗋𝖺𝗍𝗂𝗈𝗇 : {dur_str}\n⌯︙ 𝖱𝖾𝗊𝗎𝖾𝗌𝗍𝖾𝖽 𝖡𝗒 : {requested_by}"


def format_video_caption(title, duration=0, requested_by="Unknown"):
    dur_str = bold_num(f"{duration//60:02d}:{duration%60:02d}") if duration > 0 else bold_num("00:00")
    return f"🕸️ 𝐕𝐈𝐃𝐄𝐎 𝐋𝐈𝐕𝐄 🎵\n⌯︙ 𝖳𝗂𝗍𝗅𝖾 : {title}\n⌯︙ 𝖣𝗎𝗋𝖺𝗍𝗂𝗈𝗇 : {dur_str}\n⌯︙ 𝖱𝖾𝗊𝗎𝖾𝗌𝗍𝖾𝖽 𝖡𝗒 : {requested_by}"


# ============================================================
# Buttons
# ============================================================
def play_buttons(is_paused=False, repeat_mode="once", time_str="00:00"):
    if is_paused:
        pause_btn = Button.inline("▸", b"resume", style='success')
    else:
        pause_btn = Button.inline("𖣃", b"pause", style='primary')

    loop_btn = Button.inline(
        "↻", b"loop",
        style='success' if repeat_mode == "loop" else 'primary'
    )
    once_btn = Button.inline(
        "➊", b"once",
        style='success' if repeat_mode == "once" else 'primary'
    )
    stop_btn = Button.inline("✕", b"stop", style='danger')

    back_btn = Button.inline("≪", b"back_15", style='primary')
    time_btn = Button.inline(time_str, b"time", style='success')
    fwd_btn = Button.inline("≫", b"fwd_15", style='primary')

    settings_btn = Button.inline("☰", b"settings", style='primary')

    return [
        [pause_btn, loop_btn, once_btn, stop_btn],
        [back_btn, time_btn, fwd_btn],
        [settings_btn],
    ]


def settings_buttons():
    return [[Button.inline("رجوع", b"settings_back", style='primary')]]


# ============================================================
# ✅ ensure_assistant_in_chat — ضم تلقائي عبر رابط الدعوة
# ============================================================
async def ensure_assistant_in_chat(bot, chat, assistant, mgr):
    """
    ضم المساعد تلقائياً عبر رابط الدعوة
    """
    from telethon.tl.functions.channels import GetParticipantRequest, JoinChannelRequest
    from telethon.tl.functions.messages import (
        ExportChatInviteRequest, ImportChatInviteRequest
    )
    from telethon.errors import (
        UserNotParticipantError, UserAlreadyParticipantError,
        InviteHashExpiredError, InviteHashInvalidError,
        ChatAdminRequiredError, ChannelPrivateError, FloodWaitError,
        ChannelsTooMuchError, InviteRequestSentError
    )

    # تنظيف
    if assistant.busy and assistant.chat != chat:
        assistant.busy = False
        assistant.chat = None

    # 1) فحص هل المساعد عضو بالفعل
    try:
        entity = await assistant.client.get_entity(chat)
        try:
            await assistant.client(GetParticipantRequest(
                channel=entity, participant=assistant.uid
            ))
            print(f"[ENSURE] {assistant.name} — عضو بالفعل ✓")
            return True, assistant
        except UserNotParticipantError:
            print(f"[ENSURE] {assistant.name} — ليس عضواً")
    except ValueError:
        print(f"[ENSURE] {assistant.name} — لا يعرف المجموعة")
    except ChannelPrivateError:
        return False, f"{assistant.name}: محظور من المجموعة"
    except FloodWaitError as e:
        return False, f"{assistant.name}: انتظر {e.seconds} ثانية"
    except Exception as e:
        print(f"[ENSURE] {assistant.name} — {type(e).__name__}")

    # 2) البوت يجلب رابط دعوة
    try:
        result = await bot(ExportChatInviteRequest(
            peer=chat,
            expire_date=None,
            usage_limit=0,
            request_needed=False
        ))
        link = result.link
        print(f"[INVITE] رابط جاهز: {link[:50]}...")
    except ChatAdminRequiredError:
        return False, f"{assistant.name}: البوت ليس مشرفاً"
    except ChannelPrivateError:
        return False, f"{assistant.name}: البوت لا يستطيع الوصول"
    except FloodWaitError as e:
        return False, f"{assistant.name}: انتظر {e.seconds} ثانية"
    except Exception as e:
        return False, f"{assistant.name}: فشل الرابط ({type(e).__name__})"

    # 3) استخراج الـ hash من الرابط
    if '+' in link:
        hash_part = link.split('+')[-1]
    else:
        hash_part = link.split('/')[-1]

    # 4) محاولة الانضمام
    try:
        await assistant.client(ImportChatInviteRequest(hash_part))
        print(f"[ENSURE] {assistant.name} — انضم بنجاح ✓")
        return True, assistant
    except UserAlreadyParticipantError:
        print(f"[ENSURE] {assistant.name} — عضو بالفعل ✓")
        return True, assistant
    except InviteRequestSentError:
        return False, f"{assistant.name}: المجموعة تطلب موافقة المشرف (أضفه يدوياً)"
    except InviteHashExpiredError:
        print(f"[INVITE] رابط منتهي → إنشاء جديد")
        try:
            result2 = await bot(ExportChatInviteRequest(
                peer=chat, expire_date=None, usage_limit=0,
                request_needed=False
            ))
            new_hash = result2.link.split('+')[-1]
            await assistant.client(ImportChatInviteRequest(new_hash))
            print(f"[ENSURE] {assistant.name} — انضم بعد إعادة الإنشاء ✓")
            return True, assistant
        except Exception as e2:
            return False, f"{assistant.name}: رابط منتهي ({type(e2).__name__})"
    except InviteHashInvalidError:
        return False, f"{assistant.name}: رابط غير صالح"
    except ChannelsTooMuchError:
        return False, f"{assistant.name}: الحساب انضم لكثير من المجموعات"
    except FloodWaitError as e:
        print(f"[INVITE] FloodWait {e.seconds} ثانية")
        return False, f"{assistant.name}: انتظر {e.seconds} ثانية"
    except Exception as e:
        return False, f"{assistant.name}: فشل الانضمام ({type(e).__name__})"


# ============================================================
# ✅ play — يجرّب كل المساعدين بالتسلسل
# ============================================================
async def play(bot, mgr, chat, file, title, dur=0, message_id=None,
               is_video=False, repeat_mode="once", start_at=0,
               requested_by="Unknown"):

    # 1) نظّف الحالة القديمة
    old_a = mgr.find(chat)
    if old_a:
        old_a.busy = False
        old_a.chat = None

    current.pop(chat, None)
    paused_chats.pop(chat, None)
    seek_offsets.pop(chat, None)
    old_task = time_tasks.pop(chat, None)
    if old_task and old_task.get("task"):
        old_task["task"].cancel()

    if not mgr.list:
        return False, "لا يوجد مساعدين مسجلين"

    print(f"[PLAY-INFO] المتاحون: {len(mgr.list)}")

    # 2) جرّب كل المساعدين بالتسلسل
    working_assistant = None
    errors = []

    for idx, a in enumerate(mgr.list):
        print(f"[PLAY-TRY] [{idx+1}/{len(mgr.list)}] محاولة مع {a.name}")

        try:
            ok, result = await ensure_assistant_in_chat(bot, chat, a, mgr)
        except Exception as e:
            err = f"{a.name}: استثناء ({type(e).__name__})"
            errors.append(err)
            print(f"[PLAY-ERR] {err}")
            continue

        if not ok:
            errors.append(result)
            print(f"[PLAY-SKIP] {result}")
            continue

        working_assistant = result
        print(f"[PLAY-OK] المساعد: {a.name}")
        break

    if not working_assistant:
        if not errors:
            return False, "فشل جميع المساعدين"
        return False, f"فشل — {errors[0]}"

    a = working_assistant

    # 3) التشغيل
    try:
        clean(DL, exclude=file)
        ffmpeg_params = f"-ss {start_at}" if start_at > 0 else None

        if is_video:
            await a.call.play(
                chat,
                MediaStream(file, audio_parameters=AudioQuality.HIGH,
                            video_parameters=VideoQuality.HD_720p,
                            ffmpeg_parameters=ffmpeg_params),
                config=GroupCallConfig(auto_start=True)
            )
            video_streams[chat] = True
        else:
            await a.call.play(
                chat,
                MediaStream(file, audio_parameters=AudioQuality.HIGH,
                            video_flags=MediaStream.Flags.IGNORE,
                            ffmpeg_parameters=ffmpeg_params),
                config=GroupCallConfig(auto_start=True)
            )
            video_streams[chat] = False

        a.busy = True
        a.chat = chat
        current[chat] = {
            "title": title, "file": file, "duration": dur,
            "is_video": is_video, "msg_id": message_id,
            "requested_by": requested_by
        }
        paused_chats[chat] = False
        repeat_modes[chat] = repeat_mode
        seek_offsets[chat] = start_at

        old = time_tasks.pop(chat, None)
        if old and old.get("task"):
            old["task"].cancel()
        if message_id:
            task = asyncio.create_task(auto_update_time(bot, mgr, chat, message_id))
            time_tasks[chat] = {"task": task, "msg_id": message_id}
        asyncio.create_task(monitor_and_play_next(bot, mgr, chat, dur))
        return True, a
    except Exception as e:
        print(f"[PLAY ERROR] {type(e).__name__}: {e}")
        a.busy = False
        a.chat = None
        current.pop(chat, None)
        paused_chats.pop(chat, None)
        seek_offsets.pop(chat, None)
        return False, f"فشل التشغيل: {type(e).__name__}"


# ============================================================
# stop
# ============================================================
async def stop(mgr, chat):
    a = mgr.find(chat)
    if not a:
        current.pop(chat, None)
        paused_chats.pop(chat, None)
        seek_offsets.pop(chat, None)
        old = time_tasks.pop(chat, None)
        if old and old.get("task"):
            old["task"].cancel()
        try:
            c = db()
            c.execute("DELETE FROM queue WHERE chat_id=?", (chat,))
            c.commit()
            c.close()
        except:
            pass
        clean(DL)
        return False
    try:
        t = time_tasks.pop(chat, None)
        if t and t.get("task"):
            t["task"].cancel()
        try:
            await a.call.leave_call(chat)
        except:
            pass
        a.busy = False
        a.chat = None
        current.pop(chat, None)
        video_streams.pop(chat, None)
        paused_chats.pop(chat, None)
        repeat_modes.pop(chat, None)
        seek_offsets.pop(chat, None)
        c = db()
        c.execute("DELETE FROM queue WHERE chat_id=?", (chat,))
        c.commit()
        c.close()
        clean(DL)
        return True
    except:
        return False


# ============================================================
# seek
# ============================================================
async def seek_to(bot, mgr, chat_id, new_start, info):
    a = mgr.find(chat_id)
    if not a:
        return False, "لا يوجد مساعد"
    
    is_video = info.get("is_video", False)
    
    try:
        if is_video:
            # فيديو → video_parameters (بدون IGNORE)
            await a.call.play(
                chat_id,
                MediaStream(
                    info["file"],
                    audio_parameters=AudioQuality.HIGH,
                    video_parameters=VideoQuality.HD_720p,
                    ffmpeg_parameters=f"-ss {new_start}"
                ),
                config=GroupCallConfig(auto_start=True)
            )
        else:
            # صوت → IGNORE (طبيعي)
            await a.call.play(
                chat_id,
                MediaStream(
                    info["file"],
                    audio_parameters=AudioQuality.HIGH,
                    video_flags=MediaStream.Flags.IGNORE,
                    ffmpeg_parameters=f"-ss {new_start}"
                ),
                config=GroupCallConfig(auto_start=True)
            )
        
        seek_offsets[chat_id] = new_start
        print(f"[SEEK] {new_start}s ✓")
        return True, new_start
    except Exception as ex:
        print(f"[SEEK ERR] {type(ex).__name__}: {ex}")
        return False, str(ex)


# ============================================================
# monitor_and_play_next
# ============================================================
async def monitor_and_play_next(bot, mgr, chat_id, duration):
    try:
        if duration <= 0:
            return
        while chat_id in current:
            a = mgr.find(chat_id)
            if not a:
                return
            if paused_chats.get(chat_id, False):
                await asyncio.sleep(2)
                continue
            try:
                t = await a.call.time(chat_id)
                offset = seek_offsets.get(chat_id, 0)
                if (t + offset) >= duration - 1:
                    break
            except:
                pass
            await asyncio.sleep(5)
        await asyncio.sleep(2)

        info = current.get(chat_id)
        repeat_mode = repeat_modes.get(chat_id, "once")

        # Loop
        if repeat_mode == "loop" and info:
            a = mgr.find(chat_id)
            if a:
                try:
                    if info.get("is_video"):
                        await a.call.play(
                            chat_id,
                            MediaStream(info["file"], audio_parameters=AudioQuality.HIGH,
                                        video_parameters=VideoQuality.HD_720p),
                            config=GroupCallConfig(auto_start=True)
                        )
                    else:
                        await a.call.play(
                            chat_id,
                            MediaStream(info["file"], audio_parameters=AudioQuality.HIGH,
                                        video_flags=MediaStream.Flags.IGNORE),
                            config=GroupCallConfig(auto_start=True)
                        )
                    seek_offsets[chat_id] = 0
                    msg_id = info.get("msg_id")
                    if msg_id:
                        old = time_tasks.pop(chat_id, None)
                        if old and old.get("task"):
                            old["task"].cancel()
                        task = asyncio.create_task(auto_update_time(bot, mgr, chat_id, msg_id))
                        time_tasks[chat_id] = {"task": task, "msg_id": msg_id}
                    asyncio.create_task(monitor_and_play_next(bot, mgr, chat_id, duration))
                    return
                except Exception as ex:
                    print(f"[LOOP ERR] {type(ex).__name__}: {ex}")

        # حذف الملف
        if info and info.get("file"):
            try:
                if os.path.exists(info["file"]):
                    os.remove(info["file"])
            except:
                pass

        current.pop(chat_id, None)
        video_streams.pop(chat_id, None)
        paused_chats.pop(chat_id, None)
        seek_offsets.pop(chat_id, None)
        old = time_tasks.pop(chat_id, None)
        if old and old.get("task"):
            old["task"].cancel()

        n = qnext(chat_id)
        if n:
            a = mgr.find(chat_id)
            if a:
                from handlers import send_spoiler_photo, send_premium
                play_photo = get_setting("play_photo", None)
                btns = play_buttons(is_paused=False, repeat_mode="once")
                is_video_next = bool(n.get('is_video', 0))
                if is_video_next:
                    caption = format_video_caption(n['title'], n.get('duration', 0), n.get('requested_by', 'Unknown'))
                else:
                    caption = format_play_caption(n['title'], n.get('duration', 0), n.get('requested_by', 'Unknown'))
                if play_photo and os.path.exists(play_photo):
                    # ✅ استخدام التشويش لصورة التشغيل التلقائي
                    t, ent = premium(caption)
                    msg = await send_spoiler_photo(bot, chat_id, play_photo, caption=t, buttons=btns, formatting_entities=ent)
                else:
                    msg = await send_premium(bot, chat_id, caption, buttons=btns)
                await play(bot, mgr, chat_id, n['file'], n['title'], n['duration'],
                           message_id=msg.id, is_video=is_video_next,
                           requested_by=n.get('requested_by', 'Unknown'))
        else:
            a = mgr.find(chat_id)
            if a:
                try:
                    await a.call.leave_call(chat_id)
                except:
                    pass
                a.busy = False
                a.chat = None
            clean(DL)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"[AUTO-NEXT ERROR] {type(e).__name__}: {e}")


# ============================================================
# auto_update_time
# ============================================================
async def auto_update_time(bot, mgr, chat_id, message_id):
    try:
        last_key = None
        while chat_id in current:
            a = mgr.find(chat_id)
            if not a:
                return
            try:
                t = await a.call.time(chat_id)
                offset = seek_offsets.get(chat_id, 0)
                display_t = t + offset
                time_str = bold_num(f"{display_t//60:02d}:{display_t%60:02d}")
            except:
                time_str = bold_num("00:00")

            is_paused = paused_chats.get(chat_id, False)
            rm = repeat_modes.get(chat_id, "once")
            key = f"{time_str}_{is_paused}_{rm}"

            if key != last_key:
                last_key = key
                try:
                    btns = play_buttons(is_paused=is_paused, repeat_mode=rm, time_str=time_str)
                    await bot.edit_message(chat_id, message_id, buttons=btns)
                except Exception as e:
                    if "MessageNotModified" not in type(e).__name__:
                        print(f"[TIME] {type(e).__name__}: {e}")
            await asyncio.sleep(10)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"[TIME TASK ERROR] {type(e).__name__}: {e}")