import os

# ============================================================
# Telegram API
# ============================================================
API_ID = 36811374
API_HASH = "665ff540c95bc5fa68cbf143a927c199"
BOT_TOKEN = "8948715359:AAEcl3TDXve-p5bT6vBssDsGyqOzg0xleDM"

# ============================================================
# معلومات البوت
# ============================================================
BOT_NAME = "بوت ميوزك Musَic aa"
DEV_ID = 8937044017
DEV_USERNAME = "@Yvvvvvu"
SOURCE_USERNAME = "@ibib1s"
SOURCE_NAME = "سورس ميوزك Musَic aa"

# ============================================================
# المسارات
# ============================================================
BASE = os.path.dirname(os.path.abspath(__file__))
DL = os.path.join(BASE, "downloads")
TEMP = os.path.join(BASE, "temp")
SESSIONS_DIR = os.path.join(BASE, "sessions")
DATA_DIR = os.path.join(BASE, "data")
DB = os.path.join(BASE, "bot.db")
COOKIES = os.path.join(BASE, "cookies.txt")
ASSISTANTS_FILE = os.path.join(SESSIONS_DIR, "assistants.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
GROUPS_DIR = os.path.join(DATA_DIR, "groups")
SOURCE_DEVS_FILE = os.path.join(DATA_DIR, "source_devs.json")

for d in [DL, TEMP, SESSIONS_DIR, DATA_DIR, GROUPS_DIR]:
    os.makedirs(d, exist_ok=True)

# ============================================================
# Premium Emojis
# ============================================================
PREMIUM_EMOJIS = {
    "WEB": 5782785585567507068,      # 🕸️
    "MUSIC": 5785186979092110978,    # 🎵
    "NOTE": 5201669926233871452,     # 🎶
    "CROWN": 5798907432507808196,    # 👑
    "MIC": 5800807165262306582,      # 🎙
}
FALLBACKS = {
    "WEB": "🕸️",
    "MUSIC": "🎵",
    "NOTE": "🎶",
    "CROWN": "👑",
    "MIC": "🎙",
}

# ============================================================
# 🚀 yt-dlp — نسخة السرعة القصوى (2-3 ثواني)
# ============================================================
YDL_OPTS = {
    # ✅ m4a أو webm — بدون تحويل MP3
    'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best',
    'outtmpl': f'{DL}/%(id)s.%(ext)s',
    'quiet': True, 'no_warnings': True, 'noplaylist': True,
    'default_search': 'ytsearch1',
    'nocheckcertificate': True,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',

    # ❌ لا postprocessors — نحتفظ بالصيغة الأصلية

    # ✅ تخطي الـ 5 ثواني انتظار
    'sleep_interval': 0,
    'max_sleep_interval': 0,
    'sleep_interval_requests': 0,

    # ✅ موازاة عالية
    'concurrent_fragment_downloads': 10,
    'http_chunk_size': 10485760,

    # ✅ محاولات سريعة
    'retries': 3,
    'fragment_retries': 3,
    'socket_timeout': 15,

    'remote_components': 'ejs:github',
}

YDL_VIDEO_OPTS = {
    # ✅ 480p mp4 — بدون merge بطيء
    'format': 'best[height<=480][ext=mp4]/best[height<=480]/best[height<=360]/best',
    'outtmpl': f'{DL}/%(id)s.%(ext)s',
    'quiet': True, 'no_warnings': True, 'noplaylist': True,
    'default_search': 'ytsearch1',
    'nocheckcertificate': True,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',

    'sleep_interval': 0,
    'max_sleep_interval': 0,
    'sleep_interval_requests': 0,

    'concurrent_fragment_downloads': 10,
    'http_chunk_size': 10485760,

    'retries': 3,
    'fragment_retries': 3,
    'socket_timeout': 15,

    'merge_output_format': 'mp4',
    'remote_components': 'ejs:github',
}

if os.path.exists(COOKIES):
    YDL_OPTS['cookiefile'] = COOKIES
    YDL_VIDEO_OPTS['cookiefile'] = COOKIES
    print(f"[INFO] Using cookies from {COOKIES}")
