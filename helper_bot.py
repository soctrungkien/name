"""
helper_bot.py - Trợ lý Telegram (Helper Bot) toàn năng điều khiển và cài đặt hệ thống.

Chức năng:
1. Giao diện bảng điều khiển trực quan với nút bấm Inline trên Telegram.
2. Hỗ trợ CÀI ĐẶT & SETUP toàn bộ qua Telegram:
   - Đăng nhập Telegram Userbot trực tiếp trong khung chat (Nhập SĐT -> Nhập OTP -> Nhập 2FA nếu có).
   - Cài đặt API_ID, API_HASH.
   - Cài đặt và kiểm tra OpenWeatherMap API Key.
   - Đổi Thành phố, Tên cố định (BASE_NAME), Múi giờ (TIMEZONE).
   - Tùy biến định dạng hiển thị NAME_FORMAT & BIO_FORMAT.
3. Điều khiển vòng đời Profile Updater:
   - Bắt đầu chạy (Start), Dừng (Stop), Tạm dừng (Pause), Tiếp tục (Resume).
   - Cập nhật tức thì (Force Update) không cần chờ.
   - Xem trước hiển thị (Preview).
4. Lệnh Userbot (.status, .update, .name, .city, .pause, .resume, .help).
"""

import os
import re
import json
import asyncio
import urllib.request
import urllib.parse
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    MessageNotModifiedError
)

from updater_state import state
from profile_engine import engine, generate_preview, get_lastfm_track

# Lưu trạng thái đàm thoại của user: user_id -> {"action": ..., "data": ...}
user_sessions = {}

def is_admin(user_id: int) -> bool:
    """Kiểm tra quyền truy cập của Admin"""
    admin_id = state.config.get("ADMIN_ID", "").strip()
    if not admin_id:
        # Nếu chưa cài ADMIN_ID, tự động cấp quyền cho người đầu tiên nhắn tin
        state.update_config({"ADMIN_ID": str(user_id)})
        return True
    return str(user_id) == admin_id

def test_weather_api_sync(api_key: str, city: str):
    """Kiểm tra API Key OpenWeatherMap đồng bộ"""
    if not api_key:
        return True, "Không dùng OpenWeatherMap API (chỉ hiện tên thành phố)."
    try:
        city_encoded = urllib.parse.quote(city)
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city_encoded}&appid={api_key}&units=metric&lang=vi"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                temp = data["main"]["temp"]
                desc = data["weather"][0]["description"]
                return True, f"Kết nối thời tiết tốt! {city}: {temp}°C, {desc}"
            return False, f"Mã HTTP: {resp.status}"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "API Key không hợp lệ (401). Nếu mới tạo, hãy chờ 15-30 phút để OpenWeatherMap kích hoạt."
        elif e.code == 404:
            return False, f"Không tìm thấy thành phố '{city}' (404)."
        return False, f"Lỗi HTTP {e.code}: {e.reason}"
    except Exception as e:
        return False, f"Lỗi kết nối: {e}"

def test_lastfm_user_sync(username: str, api_key: str = "b25b959554ed76058ac220b7b2e0a026") -> tuple:
    """Kiểm tra kết nối và tính hợp lệ của tài khoản Last.fm"""
    if not username:
        return True, "Chưa cấu hình Last.fm."
    try:
        key = api_key or "b25b959554ed76058ac220b7b2e0a026"
        url = f"https://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user={urllib.parse.quote(username)}&api_key={key}&format=json&limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "TelegramProfileUpdater/1.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                if "error" in data:
                    return False, f"Lỗi Last.fm: {data.get('message', 'Không tìm thấy user')}"
                recent = data.get("recenttracks", {})
                tracks = recent.get("track", [])
                total = recent.get("@attr", {}).get("total", "0")
                if tracks:
                    first = tracks[0] if isinstance(tracks, list) else tracks
                    t_name = first.get("name", "")
                    a_info = first.get("artist", {})
                    a_name = a_info.get("#text") if isinstance(a_info, dict) else str(a_info)
                    is_playing = first.get("@attr", {}).get("nowplaying") == "true"
                    status = "Đang phát 🎧" if is_playing else "Bài gần nhất 🎵"
                    return True, f"Kết nối Last.fm tốt! ({total} scrobbles). {status}: {t_name} - {a_name}"
                return True, f"Kết nối Last.fm tốt! (User {username} chưa có scrobbles)."
            return False, f"Mã HTTP: {resp.status}"
    except Exception as e:
        return False, f"Lỗi kết nối Last.fm: {e}"

# ============================================================
# BÀN PHÍM NÚT BẤM (INLINE KEYBOARDS)
# ============================================================

def get_main_keyboard():
    """Bàn phím Menu chính"""
    run_btn = Button.inline("⏹️ Dừng Updater", data="toggle_engine") if engine.is_running else Button.inline("▶️ Chạy Updater", data="toggle_engine")
    pause_btn = Button.inline("▶️ Tiếp tục" if state.is_paused else "⏸️ Tạm dừng", data="toggle_pause")

    return [
        [Button.inline("🔄 Cập nhật ngay", data="update_now"), Button.inline("👁️ Xem trước Profile", data="preview")],
        [Button.inline("📝 Xem trước Bio", data="preview_bio"), Button.inline("🌤️ Thời tiết chi tiết", data="weather_card")],
        [run_btn, pause_btn],
        [Button.inline("⚙️ Cài đặt & Cấu hình (Setup)", data="menu_settings")],
        [Button.inline("📊 Làm mới trạng thái", data="status"), Button.inline("ℹ️ Trợ giúp", data="help")]
    ]

def get_settings_keyboard():
    """Bàn phím Menu Cài đặt"""
    has_session = bool(state.config.get("SESSION_STRING"))
    session_label = "🔑 Đổi tài khoản Telegram" if has_session else "🔑 Đăng nhập Telegram"
    has_lastfm = "✔" if state.config.get("LASTFM_USERNAME") else "➕"

    return [
        [Button.inline(session_label, data="setup_login")],
        [Button.inline("✏️ Đổi Tên (BASE_NAME)", data="setup_name"), Button.inline("📍 Đổi Thành phố", data="setup_city")],
        [Button.inline(f"🎵 Last.fm ({has_lastfm})", data="setup_lastfm"), Button.inline("⛅ Cấu hình Thời tiết", data="setup_weather")],
        [Button.inline("🕒 Đổi Múi giờ", data="setup_timezone"), Button.inline("🆔 Cấu hình API ID & Hash", data="setup_api_creds")],
        [Button.inline("🎨 Mẫu hiển thị (Format)", data="setup_format")],
        [Button.inline("⬅️ Quay lại Menu chính", data="main_menu")]
    ]

def get_cancel_keyboard():
    """Nút bấm hủy thao tác"""
    return [[Button.inline("❌ Hủy bỏ thao tác", data="cancel_action")]]

def get_timezone_keyboard():
    """Bàn phím chọn nhanh múi giờ"""
    return [
        [Button.inline("🇻🇳 Việt Nam (Asia/Ho_Chi_Minh)", data="tz_Asia/Ho_Chi_Minh")],
        [Button.inline("🇹🇭 Thái Lan (Asia/Bangkok)", data="tz_Asia/Bangkok")],
        [Button.inline("🇯🇵 Nhật Bản (Asia/Tokyo)", data="tz_Asia/Tokyo")],
        [Button.inline("🌐 Tự nhập múi giờ khác", data="tz_custom")],
        [Button.inline("⬅️ Quay lại", data="menu_settings")]
    ]

def get_format_keyboard():
    """Bàn phím cài đặt định dạng với các mẫu có sẵn và tùy biến"""
    return [
        [Button.inline("🌟 Mẫu 1: {base_name} | HH:mm - DD/MM/YYYY", data="preset_1")],
        [Button.inline("📅 Mẫu 2: {base_name} | {thu}, DD/MM/YYYY - HH:mm", data="preset_2")],
        [Button.inline("🎵 Mẫu 3: {base_name} | {music_or_weather}", data="preset_6")],
        [Button.inline("🎧 Mẫu 4 (Bio): {music_or_weather} ⏰ HH:mm", data="preset_7")],
        [Button.inline("🌤️ Mẫu 5 (Bio): 📍 {city} • {weather_short} ⏰ HH:mm", data="preset_8")],
        [Button.inline("🎶 Mẫu 6 (Bio): {music_or_weather} | 📍 {city}", data="preset_9")],
        [Button.inline("⏰ Mẫu 7: {base_name} | {thu_ngan} • HH:mm", data="preset_3")],
        [Button.inline("⚡ Mẫu 8: {base_name} ⏰ HH:mm (DD/MM)", data="preset_4")],
        [Button.inline("📝 Xem trước Bio chi tiết", data="preview_bio")],
        [Button.inline("✏️ Tự nhập NAME_FORMAT", data="fmt_name"), Button.inline("📝 Tự nhập BIO_FORMAT", data="fmt_bio")],
        [Button.inline("🔄 Khôi phục mặc định", data="fmt_reset"), Button.inline("⬅️ Quay lại", data="menu_settings")]
    ]

# ============================================================
# ĐỊNH DẠNG NỘI DUNG TIN NHẮN
# ============================================================

def format_dashboard():
    """Nội dung Bảng điều khiển chính"""
    if not engine.is_running:
        status_line = "🔴 <b>Đang dừng</b>"
    elif state.is_paused:
        status_line = "⏸️ <b>Đang tạm dừng</b>"
    else:
        status_line = "🟢 <b>Đang chạy bình thường</b>"

    account_text = f"{state.account_name} (ID: <code>{state.account_id}</code>)" if state.account_id else "<i>Chưa đăng nhập</i>"
    has_session = "✔ Đã có SESSION_STRING" if state.config.get("SESSION_STRING") else "✘ Chưa đăng nhập"
    music_line = f"• <b>Đang nghe (Last.fm):</b> {state.current_music}\n" if state.current_music else ""
    weather_display = state.weather_data.get("weather_full") if state.weather_data else (state.current_weather or "Chưa có thông tin")

    return (
        f"🤖 <b>BẢNG ĐIỀU KHIỂN TELEGRAM PROFILE UPDATER</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Tình trạng:</b> {status_line}\n"
        f"• <b>Tài khoản Userbot:</b> {account_text} ({has_session})\n"
        f"• <b>Tên hiển thị hiện tại:</b> <code>{state.current_name or 'Chưa cập nhật'}</code>\n"
        f"• <b>Bio hiện tại:</b> <code>{state.current_bio or 'Chưa cập nhật'}</code>\n"
        f"{music_line}"
        f"• <b>Thời tiết:</b> {weather_display}\n"
        f"• <b>Tên cố định (BASE_NAME):</b> <code>{state.config.get('BASE_NAME')}</code>\n"
        f"• <b>Thành phố:</b> <code>{state.config.get('CITY')}</code>\n"
        f"• <b>Múi giờ:</b> <code>{state.config.get('TIMEZONE')}</code>\n"
        f"• <b>Lần cập nhật cuối:</b> <code>{state.last_update_time}</code> (Tổng: {state.update_count})\n"
        + (f"• <b>Lỗi gần nhất:</b> <code>{state.last_error}</code>\n" if state.last_error else "")
    )

def format_settings_text():
    """Nội dung trang Cài đặt"""
    has_sess = "✔ Đã cấu hình" if state.config.get("SESSION_STRING") else "✘ Chưa có (Cần đăng nhập)"
    has_weather = "✔ OpenWeatherMap API" if state.config.get("WEATHER_API") else "✔ wttr.in (Tự động miễn phí)"
    lastfm_user = state.config.get("LASTFM_USERNAME") or "Chưa cấu hình"

    return (
        f"⚙️ <b>CÀI ĐẶT & CẤU HÌNH HỆ THỐNG</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Tài khoản Telegram:</b> {has_sess}\n"
        f"• <b>API_ID:</b> <code>{state.config.get('API_ID')}</code>\n"
        f"• <b>API_HASH:</b> <code>{state.config.get('API_HASH')[:8]}...</code>\n"
        f"• <b>Tên hiển thị cố định:</b> <code>{state.config.get('BASE_NAME')}</code>\n"
        f"• <b>Tài khoản Last.fm:</b> <code>{lastfm_user}</code>\n"
        f"• <b>Tỉnh / Thành phố:</b> <code>{state.config.get('CITY')}</code>\n"
        f"• <b>Nguồn Thời tiết:</b> {has_weather}\n"
        f"• <b>Múi giờ:</b> <code>{state.config.get('TIMEZONE')}</code>\n"
        f"• <b>Định dạng Tên:</b> <code>{state.config.get('NAME_FORMAT')}</code>\n"
        f"• <b>Định dạng Bio:</b> <code>{state.config.get('BIO_FORMAT')}</code>\n\n"
        f"<i>Bấm vào một mục bên dưới để cấu hình:</i>"
    )

def format_weather_card():
    """Nội dung thẻ Thời tiết chi tiết"""
    w = state.weather_data or {}
    city = state.config.get("CITY", "Bac Ninh")
    temp = w.get("temp") or state.weather_temp or "Chưa có"
    feels = w.get("feels_like") or state.weather_feels_like or temp
    desc = w.get("desc") or state.weather_desc or "Bình thường"
    icon = w.get("icon") or (state.weather_short[:2] if state.weather_short else "🌤️")
    hum = w.get("humidity") or state.weather_humidity or "N/A"
    wind = w.get("wind") or state.weather_wind or "N/A"
    pressure = w.get("pressure") or "1013hPa"
    sunrise = w.get("sunrise") or "N/A"
    sunset = w.get("sunset") or "N/A"
    short_str = w.get("weather_short") or f"{icon} {temp}"
    source = "OpenWeatherMap API" if state.config.get("WEATHER_API") else "wttr.in (Tự động đa nguồn)"

    return (
        f"🌤️ <b>THÔNG TIN THỜI TIẾT CHI TIẾT — {city.upper()}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Tình trạng:</b> {icon} <b>{desc}</b>\n"
        f"• <b>Nhiệt độ hiện tại:</b> <code>{temp}</code> (Cảm nhận thực tế: <code>{feels}</code>)\n"
        f"• <b>Độ ẩm không khí:</b> 💦 <code>{hum}</code>\n"
        f"• <b>Tốc độ gió:</b> 💨 <code>{wind}</code>\n"
        f"• <b>Áp suất khí quyển:</b> <code>{pressure}</code>\n"
        f"• <b>Mặt trời mọc (Bình minh):</b> 🌅 <code>{sunrise}</code>\n"
        f"• <b>Mặt trời lặn (Hoàng hôn):</b> 🌇 <code>{sunset}</code>\n"
        f"• <b>Nguồn cấp dữ liệu:</b> <i>{source}</i>\n\n"
        f"📌 <b>Các từ khóa thời tiết bạn có thể dùng trong Tên & Bio:</b>\n"
        f"• <code>{{weather}}</code> : Thời tiết tự động cân đối cho Bio\n"
        f"• <code>{{weather_short}}</code> : Cực ngắn gọn (ví dụ: <code>{short_str}</code>)\n"
        f"• <code>{{temp}}</code> : Chỉ lấy nhiệt độ (<code>{temp}</code>)\n"
        f"• <code>{{feels_like}}</code> : Cảm nhận (<code>{feels}</code>)\n"
        f"• <code>{{humidity}}</code> : Độ ẩm (<code>{hum}</code>)\n"
        f"• <code>{{wind}}</code> : Tốc độ gió (<code>{wind}</code>)\n"
        f"• <code>{{weather_desc}}</code> : Mô tả (<code>{desc}</code>)\n"
        f"• <code>{{weather_icon}}</code> : Icon (<code>{icon}</code>)"
    )

def format_bio_preview_card():
    """Nội dung thẻ Xem trước Bio chuyên sâu"""
    from profile_engine import generate_bio_preview
    bio_data = generate_bio_preview()
    cur_fmt = bio_data["template"]
    cur_bio = bio_data["current"]
    cur_len = bio_data["current_len"]
    status_icon = "🟢 Hợp lệ" if not bio_data["is_over_limit"] else "🔴 VƯỢT GIỚI HẠN 70 KÝ TỰ"

    music_user = state.config.get("LASTFM_USERNAME")
    music_status = f"✔ <code>{music_user}</code>" if music_user else "✘ Chưa kết nối (/lastfm)"

    return (
        f"📝 <b>XEM TRƯỚC TIỂU SỬ TELEGRAM (BIO PREVIEW)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Mẫu BIO_FORMAT đang cấu hình:</b>\n"
        f"  <code>{cur_fmt}</code>\n\n"
        f"• <b>Bio hiển thị thực tế trên Profile:</b>\n"
        f"  👉 <b>{cur_bio}</b>\n"
        f"  📊 <b>Độ dài:</b> <code>{cur_len}/70 ký tự</code> ({status_icon})\n"
        f"• <b>Tài khoản Last.fm:</b> {music_status}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎭 <b>CÁC KỊCH BẢN HIỂN THỊ CỦA MẪU NÀY:</b>\n\n"
        f"🎧 <b>1. Khi đang phát nhạc (Spotify / Apple Music):</b>\n"
        f"👉 <code>{bio_data['with_music']}</code> ({bio_data['with_music_len']}/70 ký tự)\n\n"
        f"🌤️ <b>2. Khi không nghe nhạc (hiển thị thời tiết):</b>\n"
        f"👉 <code>{bio_data['no_music']}</code> ({bio_data['no_music_len']}/70 ký tự)\n\n"
        f"💡 <i>Gợi ý: Dùng lệnh <code>/bioformat &lt;mẫu&gt;</code> để đổi ngay định dạng Bio!</i>"
    )

# ============================================================
# BỘ XỬ LÝ LỆNH USERBOT (SELF-COMMANDS)
# ============================================================

def register_userbot_handlers(client: TelegramClient):
    """Đăng ký các lệnh tự điều khiển trên Userbot (.status, .name, .update, ...)"""
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(help|status|update|name|city|pause|resume|nameformat|bioformat|lastfm|music|bio|previewbio|preview|weather)(?:\s+(.*))?$"))
    async def userbot_command_handler(event):
        cmd = event.pattern_match.group(1).lower()
        arg = (event.pattern_match.group(2) or "").strip()

        if cmd == "help":
            help_text = (
                "🛠 <b>LỆNH ĐIỀU KHIỂN PROFILE USERBOT</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "• <code>.name &lt;tên mới&gt;</code> : Đổi BASE_NAME (Ví dụ: <code>.name HzzMonet</code>)\n"
                "• <code>.nameformat &lt;mẫu&gt;</code> : Đổi định dạng tên (Ví dụ: <code>.nameformat {base_name} | HH:mm - DD/MM/YYYY</code>)\n"
                "• <code>.bioformat &lt;mẫu&gt;</code> : Đổi định dạng bio (Ví dụ: <code>.bioformat {music_or_weather} ⏰ HH:mm</code>)\n"
                "• <code>.bio</code> / <code>.previewbio</code> : Xem trước Bio & kiểm tra độ dài 70 ký tự\n"
                "• <code>.weather</code> : Xem chi tiết thời tiết (nhiệt độ, độ ẩm, gió, bình minh/hoàng hôn)\n"
                "• <code>.preview</code> : Xem trước Tên và Bio hiện tại\n"
                "• <code>.lastfm &lt;username&gt;</code> : Kết nối tài khoản Last.fm nghe nhạc\n"
                "• <code>.music</code> : Xem bài hát đang nghe trên Last.fm\n"
                "• <code>.city &lt;thành phố&gt;</code> : Đổi thành phố thời tiết\n"
                "• <code>.update</code> : Kích hoạt cập nhật profile ngay lập tức\n"
                "• <code>.status</code> : Xem trạng thái cập nhật\n"
                "• <code>.pause</code> / <code>.resume</code> : Tạm dừng hoặc tiếp tục\n"
                "• <code>.help</code> : Hiển thị bảng trợ giúp này\n\n"
                "<b>Từ khóa thời tiết:</b> <code>{weather}</code>, <code>{weather_short}</code>, <code>{temp}</code>, <code>{feels_like}</code>, <code>{humidity}</code>, <code>{wind}</code>, <code>{weather_desc}</code>\n"
                "<b>Từ khóa âm nhạc:</b> <code>{music}</code>, <code>{music_or_weather}</code>, <code>{track}</code>, <code>{artist}</code>"
            )
            await event.edit(help_text, parse_mode="html")

        elif cmd == "status":
            await event.edit(format_dashboard(), parse_mode="html")

        elif cmd == "update":
            state.trigger_update()
            await event.edit("🔄 <i>Đã gửi yêu cầu cập nhật profile ngay lập tức...</i>", parse_mode="html")

        elif cmd in ("previewbio", "bio"):
            await event.edit(format_bio_preview_card(), parse_mode="html")

        elif cmd == "preview":
            p_name, p_bio = generate_preview()
            preview_msg = (
                f"👁️ <b>XEM TRƯỚC (PREVIEW) PROFILE</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"• <b>Tên:</b> <code>{p_name}</code> ({len(p_name)}/64 ký tự)\n"
                f"• <b>Bio:</b> <code>{p_bio}</code> ({len(p_bio)}/70 ký tự)\n"
            )
            await event.edit(preview_msg, parse_mode="html")

        elif cmd == "weather":
            await event.edit(format_weather_card(), parse_mode="html")

        elif cmd == "name":
            if not arg:
                await event.edit("⚠️ <i>Vui lòng nhập tên mới. Ví dụ:</i> <code>.name HzzMonet</code>", parse_mode="html")
                return
            state.update_config({"BASE_NAME": arg})
            state.trigger_update()
            p_name, _ = generate_preview()
            await event.edit(f"✅ <i>Đã đổi BASE_NAME thành:</i> <b>{arg}</b>\n• <b>Tên hiển thị mới:</b> <code>{p_name}</code>", parse_mode="html")

        elif cmd == "nameformat":
            if not arg:
                await event.edit("⚠️ <i>Vui lòng nhập mẫu. Ví dụ:</i> <code>.nameformat {base_name} | HH:mm - DD/MM/YYYY</code>", parse_mode="html")
                return
            state.update_config({"NAME_FORMAT": arg})
            state.trigger_update()
            p_name, _ = generate_preview()
            await event.edit(f"✅ <i>Đã đổi NAME_FORMAT!</i>\n• <b>Tên hiển thị:</b> <code>{p_name}</code>", parse_mode="html")

        elif cmd == "bioformat":
            if not arg:
                await event.edit("⚠️ <i>Vui lòng nhập mẫu bio. Ví dụ:</i> <code>.bioformat {weather} ⏰ HH:mm</code>", parse_mode="html")
                return
            state.update_config({"BIO_FORMAT": arg})
            state.trigger_update()
            _, p_bio = generate_preview()
            await event.edit(f"✅ <i>Đã đổi BIO_FORMAT!</i>\n• <b>Bio hiển thị:</b> <code>{p_bio}</code>", parse_mode="html")

        elif cmd == "lastfm":
            if not arg:
                curr_u = state.config.get("LASTFM_USERNAME") or "Chưa cấu hình"
                await event.edit(f"🎵 <i>Tài khoản Last.fm hiện tại:</i> <code>{curr_u}</code>\n<i>Để đổi:</i> <code>.lastfm &lt;username&gt;</code>", parse_mode="html")
                return
            state.update_config({"LASTFM_USERNAME": arg})
            state.trigger_update()
            await event.edit(f"✅ <i>Đã kết nối Last.fm:</i> <b>{arg}</b> (Đang kiểm tra nhạc...)", parse_mode="html")

        elif cmd == "music":
            if state.current_music:
                await event.edit(f"🎧 <b>ĐANG NGHE:</b> {state.current_music}\n• <b>Bài:</b> <code>{state.music_track}</code>\n• <b>Ca sĩ:</b> <code>{state.music_artist}</code>\n• <b>Tổng scrobbles:</b> <code>{state.music_scrobbles}</code>", parse_mode="html")
            else:
                lastfm_user = state.config.get("LASTFM_USERNAME")
                if not lastfm_user:
                    await event.edit("⚠️ <i>Chưa cấu hình Last.fm! Gõ</i> <code>.lastfm &lt;username&gt;</code> <i>để kết nối.</i>", parse_mode="html")
                else:
                    await event.edit(f"🎵 <i>Không có bài hát nào đang phát trên tài khoản Last.fm:</i> <code>{lastfm_user}</code>", parse_mode="html")

        elif cmd == "city":
            if not arg:
                await event.edit("⚠️ <i>Vui lòng nhập thành phố mới. Ví dụ:</i> <code>.city Ha Noi</code>", parse_mode="html")
                return
            state.update_config({"CITY": arg})
            state.trigger_update()
            await event.edit(f"✅ <i>Đã đổi thành phố thành:</i> <b>{arg}</b> (Đang cập nhật...)", parse_mode="html")

        elif cmd == "pause":
            state.is_paused = True
            await event.edit("⏸️ <i>Đã tạm dừng tự động cập nhật profile!</i>", parse_mode="html")

        elif cmd == "resume":
            state.is_paused = False
            state.trigger_update()
            await event.edit("▶️ <i>Đã tiếp tục tự động cập nhật profile!</i>", parse_mode="html")

# ============================================================
# BỘ XỬ LÝ LỆNH & SỰ KIỆN HELPER BOT (BOTFATHER)
# ============================================================

def register_bot_handlers(bot_client: TelegramClient):
    """Đăng ký toàn bộ xử lý tin nhắn và nút bấm cho Helper Bot"""

    @bot_client.on(events.NewMessage(pattern=r"^/cancel$"))
    async def cancel_cmd(event):
        if not is_admin(event.sender_id): return
        sess = user_sessions.pop(event.sender_id, None)
        if sess and "temp_client" in sess:
            try:
                await sess["temp_client"].disconnect()
            except Exception:
                pass
        await event.reply("❌ <b>Đã hủy thao tác hiện tại!</b>", parse_mode="html", buttons=get_main_keyboard())

    @bot_client.on(events.NewMessage(pattern=r"^/start$"))
    async def start_cmd(event):
        if not is_admin(event.sender_id):
            await event.reply("⛔ <b>Bạn không có quyền sử dụng bot này!</b>", parse_mode="html")
            return
        user_sessions.pop(event.sender_id, None)
        await event.reply(format_dashboard(), parse_mode="html", buttons=get_main_keyboard())

    @bot_client.on(events.NewMessage(pattern=r"^/help$"))
    async def help_cmd(event):
        if not is_admin(event.sender_id): return
        msg = (
            "📖 <b>HƯỚNG DẪN CẤU HÌNH TÊN & ĐỊNH DẠNG (FORMAT GUIDE)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "<b>1. Đổi tên cố định (BASE_NAME):</b>\n"
            "• Gõ lệnh: <code>/setname HzzMonet</code> (hoặc <code>/basename HzzMonet</code>)\n"
            "• Hoặc bấm: <b>[⚙️ Cài đặt]</b> ➡️ <b>[✏️ Đổi Tên]</b>\n\n"
            "<b>2. Tùy biến cách hiển thị tên (NAME_FORMAT):</b>\n"
            "• Gõ lệnh: <code>/nameformat {base_name} | HH:mm - DD/MM/YYYY</code>\n"
            "• Hoặc viết thẳng tên: <code>/nameformat HzzMonet | HH:mm - DD/MM/YYYY</code>\n"
            "• Hoặc bấm: <b>[⚙️ Cài đặt]</b> ➡️ <b>[🎨 Mẫu hiển thị]</b> (có sẵn mẫu bấm chọn)\n\n"
            "<b>3. Các từ khóa thời gian hỗ trợ:</b>\n"
            "• <code>HH</code> : Giờ 24h (00 - 23)\n"
            "• <code>mm</code> : Phút (00 - 59)\n"
            "• <code>ss</code> : Giây (00 - 59)\n"
            "• <code>hh</code> : Giờ 12h (01 - 12) & <code>ampm</code> : AM/PM\n"
            "• <code>DD</code> : Ngày trong tháng (01 - 31)\n"
            "• <code>MM</code> : Tháng (01 - 12)\n"
            "• <code>YYYY</code> : Năm 4 chữ số (2026)\n"
            "• <code>YY</code> : Năm 2 chữ số (26)\n"
            "• <code>{thu}</code> : Thứ tiếng Việt (Thứ Hai, Thứ Ba...)\n"
            "• <code>{thu_ngan}</code> : Thứ viết tắt (T2, T3... CN)\n"
            "• <code>{city}</code> : Tên thành phố\n"
            "• <code>{base_name}</code> : Tên cố định bạn đã lưu\n\n"
            "<b>4. Từ khóa thời tiết nâng cao (OpenWeatherMap & wttr.in):</b>\n"
            "• <code>{weather}</code> : Thời tiết tự động cân đối cho Bio\n"
            "• <code>{weather_short}</code> : Cực ngắn gọn (VD: ⛅ 28°C)\n"
            "• <code>{weather_medium}</code> : Vừa đủ (VD: ⛅ Hanoi 28°C | 75%)\n"
            "• <code>{weather_full}</code> : Đầy đủ (VD: 📍 Hanoi: ⛅ 28°C | 75% | 3m/s)\n"
            "• <code>{temp}</code> / <code>{nhiet_do}</code> : Nhiệt độ (°C)\n"
            "• <code>{feels_like}</code> / <code>{cam_giac}</code> : Cảm giác thực tế (°C)\n"
            "• <code>{humidity}</code> / <code>{do_am}</code> : Độ ẩm (%)\n"
            "• <code>{wind}</code> / <code>{gio_toc}</code> : Tốc độ gió\n"
            "• <code>{weather_desc}</code> : Mô tả thời tiết tiếng Việt\n"
            "• <code>{weather_icon}</code> : Icon thời tiết\n"
            "• <code>{sunrise}</code> / <code>{sunset}</code> : Giờ bình minh / hoàng hôn\n\n"
            "<b>5. Từ khóa âm nhạc (Last.fm / Spotify / Apple Music):</b>\n"
            "• <code>{music}</code> : Bài hát đang nghe (kèm icon 🎧 khi phát hoặc 🎵 khi dừng)\n"
            "• <code>{music_or_weather}</code> : Tự động hiện nhạc khi đang nghe; tự chuyển về thời tiết khi không nghe nhạc\n"
            "• <code>{track}</code> : Tên bài hát\n"
            "• <code>{artist}</code> : Tên nghệ sĩ/ca sĩ\n"
            "• <code>{scrobbles}</code> : Tổng số lượt nghe trên Last.fm\n\n"
            "<b>6. Các mẫu ví dụ phổ biến:</b>\n"
            "• <code>HzzMonet | HH:mm - DD/MM/YYYY</code>\n"
            "  👉 Ra tên: <b>HzzMonet | 21:08 - 12/09/2026</b>\n"
            "• <code>{base_name} | {music_or_weather}</code>\n"
            "  👉 Ra tên: <b>HzzMonet | 🎧 Blinding Lights - The Weeknd</b>\n"
            "• <code>{music_or_weather} ⏰ HH:mm</code>\n"
            "  👉 Bio: <b>🎧 Blinding Lights - The Weeknd ⏰ 21:08</b>\n"
            "• <code>📍 {city} • {weather_short} ⏰ HH:mm</code>\n"
            "  👉 Bio: <b>📍 Bac Ninh • ⛅ 28°C ⏰ 21:08</b>\n"
            "• <code>{base_name} | {thu}, DD/MM/YYYY - HH:mm</code>\n"
            "  👉 Ra tên: <b>HzzMonet | Thứ Bảy, 12/09/2026 - 21:08</b>\n\n"
            "<b>7. Danh sách tất cả các lệnh:</b>\n"
            "• <code>/start</code> : Mở Bảng điều khiển chính\n"
            "• <code>/status</code> : Xem trạng thái chi tiết\n"
            "• <code>/update</code> : Cập nhật profile ngay lập tức\n"
            "• <code>/preview</code> : Xem trước Tên và Bio hiện tại\n"
            "• <code>/previewbio</code> (hoặc <code>/bio</code>) : Xem trước Bio & kiểm tra độ dài 70 ký tự\n"
            "• <code>/weather</code> : Xem chi tiết thời tiết (nhiệt độ, gió, độ ẩm, bình minh/hoàng hôn)\n"
            "• <code>/lastfm &lt;user&gt;</code> : Kết nối tài khoản Last.fm\n"
            "• <code>/music</code> : Xem bài hát đang nghe trên Last.fm\n"
            "• <code>/setname &lt;tên&gt;</code> : Đổi tên cố định\n"
            "• <code>/nameformat &lt;mẫu&gt;</code> : Đổi định dạng tên\n"
            "• <code>/bioformat &lt;mẫu&gt;</code> : Đổi định dạng bio\n"
            "• <code>/setcity &lt;thành phố&gt;</code> : Đổi thành phố thời tiết\n"
            "• <code>/pause</code> / <code>/resume</code> : Tạm dừng / Tiếp tục\n"
            "• <code>/cancel</code> : Hủy thao tác nhập liệu"
        )
        await event.reply(msg, parse_mode="html", buttons=get_main_keyboard())

    @bot_client.on(events.NewMessage(pattern=r"^/login$"))
    async def login_cmd(event):
        if not is_admin(event.sender_id): return
        user_sessions[event.sender_id] = {"action": "login_wait_phone"}
        msg = (
            "📱 <b>ĐĂNG NHẬP TELEGRAM USERBOT</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Vui lòng nhập <b>Số điện thoại</b> tài khoản Telegram của bạn:\n"
            "<i>(Bắt buộc có dấu '+' và mã quốc gia, ví dụ: <code>+84912345678</code>)</i>"
        )
        await event.reply(msg, parse_mode="html", buttons=get_cancel_keyboard())

    @bot_client.on(events.NewMessage(pattern=r"^/status$"))
    async def status_cmd(event):
        if not is_admin(event.sender_id): return
        await event.reply(format_dashboard(), parse_mode="html", buttons=get_main_keyboard())

    @bot_client.on(events.NewMessage(pattern=r"^/update$"))
    async def update_cmd(event):
        if not is_admin(event.sender_id): return
        state.trigger_update()
        await event.reply("🔄 <b>Đã gửi lệnh cập nhật profile!</b>", parse_mode="html", buttons=get_main_keyboard())

    @bot_client.on(events.NewMessage(pattern=r"^/preview$"))
    async def preview_cmd(event):
        if not is_admin(event.sender_id): return
        p_name, p_bio = generate_preview()
        msg = (
            f"👁️ <b>XEM TRƯỚC (PREVIEW) PROFILE</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Tên hiển thị:</b> <code>{p_name}</code> ({len(p_name)}/64 ký tự)\n"
            f"• <b>Tiểu sử (Bio):</b> <code>{p_bio}</code> ({len(p_bio)}/70 ký tự)\n"
        )
        await event.reply(msg, parse_mode="html", buttons=get_main_keyboard())

    @bot_client.on(events.NewMessage(pattern=r"^/(?:previewbio|bio)$"))
    async def previewbio_cmd(event):
        if not is_admin(event.sender_id): return
        await event.reply(format_bio_preview_card(), parse_mode="html", buttons=get_main_keyboard())

    @bot_client.on(events.NewMessage(pattern=r"^/weather$"))
    async def weather_cmd(event):
        if not is_admin(event.sender_id): return
        await event.reply(format_weather_card(), parse_mode="html", buttons=get_main_keyboard())

    @bot_client.on(events.NewMessage(pattern=r"^/(?:setname|basename)(?:\s+(.*))?$"))
    async def setname_cmd(event):
        if not is_admin(event.sender_id): return
        val = (event.pattern_match.group(1) or "").strip()
        if not val:
            user_sessions[event.sender_id] = {"action": "input_name"}
            curr = state.config.get("BASE_NAME", "tên")
            await event.reply(
                f"✏️ <b>ĐỔI TÊN CỐ ĐỊNH (BASE_NAME)</b>\n"
                f"Tên hiện tại: <code>{curr}</code>\n\n"
                f"👉 <b>Vui lòng gửi tên mới của bạn (Ví dụ: <code>HzzMonet</code>):</b>",
                parse_mode="html",
                buttons=get_cancel_keyboard()
            )
            return
        state.update_config({"BASE_NAME": val})
        state.trigger_update()
        p_name, _ = generate_preview()
        await event.reply(
            f"✅ <b>Đã đổi BASE_NAME thành:</b> <code>{val}</code>\n"
            f"• <b>Tên hiển thị mới:</b> <code>{p_name}</code> ({len(p_name)}/64 ký tự)\n\n"
            f"<i>Profile Telegram đang được cập nhật...</i>",
            parse_mode="html",
            buttons=get_main_keyboard()
        )

    @bot_client.on(events.NewMessage(pattern=r"^/(?:set)?nameformat(?:\s+(.*))?$"))
    async def nameformat_cmd(event):
        if not is_admin(event.sender_id): return
        val = (event.pattern_match.group(1) or "").strip()
        if not val:
            user_sessions[event.sender_id] = {"action": "input_fmt_name"}
            msg = (
                "🎨 <b>CÀI ĐẶT ĐỊNH DẠNG TÊN (NAME_FORMAT)</b>\n\n"
                "Ví dụ mẫu:\n"
                "• <code>{base_name} | HH:mm - DD/MM/YYYY</code>\n"
                "• <code>HzzMonet | HH:mm - DD/MM/YYYY</code>\n"
                "• <code>{base_name} | {thu}, DD/MM/YYYY - HH:mm</code>\n\n"
                "👉 <b>Vui lòng gửi mẫu định dạng mới của bạn:</b>"
            )
            await event.reply(msg, parse_mode="html", buttons=get_cancel_keyboard())
            return
        state.update_config({"NAME_FORMAT": val})
        state.trigger_update()
        p_name, _ = generate_preview()
        await event.reply(
            f"✅ <b>Đã cập nhật định dạng tên!</b>\n\n"
            f"• <b>Mẫu:</b> <code>{val}</code>\n"
            f"• <b>Tên hiển thị mới:</b> <code>{p_name}</code> ({len(p_name)}/64 ký tự)\n\n"
            f"<i>Profile Telegram đang được cập nhật...</i>",
            parse_mode="html",
            buttons=get_main_keyboard()
        )

    @bot_client.on(events.NewMessage(pattern=r"^/(?:set)?bioformat(?:\s+(.*))?$"))
    async def bioformat_cmd(event):
        if not is_admin(event.sender_id): return
        val = (event.pattern_match.group(1) or "").strip()
        if not val:
            user_sessions[event.sender_id] = {"action": "input_fmt_bio"}
            msg = (
                "📝 <b>CÀI ĐẶT ĐỊNH DẠNG TIỂU SỬ (BIO_FORMAT)</b>\n\n"
                "Ví dụ mẫu:\n"
                "• <code>{weather} ⏰ HH:mm</code>\n"
                "• <code>📍 {city} | ⏰ HH:mm - DD/MM</code>\n\n"
                "👉 <b>Vui lòng gửi mẫu bio mới của bạn:</b>"
            )
            await event.reply(msg, parse_mode="html", buttons=get_cancel_keyboard())
            return
        state.update_config({"BIO_FORMAT": val})
        state.trigger_update()
        _, p_bio = generate_preview()
        await event.reply(
            f"✅ <b>Đã cập nhật định dạng Bio!</b>\n\n"
            f"• <b>Mẫu:</b> <code>{val}</code>\n"
            f"• <b>Bio hiển thị mới:</b> <code>{p_bio}</code> ({len(p_bio)}/70 ký tự)\n\n"
            f"<i>Profile Telegram đang được cập nhật...</i>",
            parse_mode="html",
            buttons=get_main_keyboard()
        )

    @bot_client.on(events.NewMessage(pattern=r"^/setcity(?:\s+(.*))?$"))
    async def setcity_cmd(event):
        if not is_admin(event.sender_id): return
        val = (event.pattern_match.group(1) or "").strip()
        if not val:
            user_sessions[event.sender_id] = {"action": "input_city"}
            await event.reply("📍 <b>Vui lòng gửi tên Tỉnh/Thành phố mới:</b>\n<i>(Ví dụ: Hanoi, Ho Chi Minh, Da Nang, Bac Ninh)</i>", parse_mode="html", buttons=get_cancel_keyboard())
            return
        state.update_config({"CITY": val})
        state.trigger_update()
        await event.reply(f"✅ Đã đổi <b>Thành phố</b> thành: <code>{val}</code>", parse_mode="html", buttons=get_main_keyboard())

    @bot_client.on(events.NewMessage(pattern=r"^/pause$"))
    async def pause_cmd(event):
        if not is_admin(event.sender_id): return
        state.is_paused = True
        await event.reply("⏸️ <b>Đã tạm dừng tự động cập nhật profile!</b>", parse_mode="html", buttons=get_main_keyboard())

    @bot_client.on(events.NewMessage(pattern=r"^/resume$"))
    async def resume_cmd(event):
        if not is_admin(event.sender_id): return
        state.is_paused = False
        state.trigger_update()
        await event.reply("▶️ <b>Đã tiếp tục tự động cập nhật profile!</b>", parse_mode="html", buttons=get_main_keyboard())

    @bot_client.on(events.NewMessage(pattern=r"^/(?:set)?lastfm(?:\s+(.*))?$"))
    async def lastfm_cmd(event):
        if not is_admin(event.sender_id): return
        val = (event.pattern_match.group(1) or "").strip()
        if not val:
            user_sessions[event.sender_id] = {"action": "input_lastfm_user"}
            curr = state.config.get("LASTFM_USERNAME") or "Chưa cấu hình"
            await event.reply(
                f"🎵 <b>CẤU HÌNH TÀI KHOẢN LAST.FM (NGHE NHẠC)</b>\n"
                f"• Tài khoản hiện tại: <code>{curr}</code>\n\n"
                f"👉 <b>Vui lòng gửi Username Last.fm của bạn (hoặc gõ '0' để tắt):</b>",
                parse_mode="html",
                buttons=get_cancel_keyboard()
            )
            return
        lastfm_u = "" if val.lower() in ("0", "none", "null", "tat", "tắt") else val
        state.update_config({"LASTFM_USERNAME": lastfm_u})
        state.trigger_update()
        if lastfm_u:
            ok, msg = test_lastfm_user_sync(lastfm_u, state.config.get("LASTFM_API_KEY"))
            res_icon = "✔" if ok else "⚠️"
            await event.reply(f"✅ Đã kết nối Last.fm: <code>{lastfm_u}</code>\n{res_icon} <i>{msg}</i>", parse_mode="html", buttons=get_main_keyboard())
        else:
            await event.reply("✅ Đã tắt liên kết Last.fm.", parse_mode="html", buttons=get_main_keyboard())

    @bot_client.on(events.NewMessage(pattern=r"^/(?:music|nowplaying)$"))
    async def music_cmd(event):
        if not is_admin(event.sender_id): return
        lastfm_user = state.config.get("LASTFM_USERNAME")
        if not lastfm_user:
            await event.reply("⚠️ <i>Chưa cấu hình Last.fm! Dùng lệnh</i> <code>/lastfm &lt;username&gt;</code> <i>hoặc vào [⚙️ Cài đặt] để kết nối.</i>", parse_mode="html", buttons=get_main_keyboard())
            return
        if state.current_music:
            status_text = "Đang phát 🎧" if state.is_now_playing else "Bài gần nhất 🎵"
            msg = (
                f"🎵 <b>THÔNG TIN ÂM NHẠC (LAST.FM)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"• <b>Trạng thái:</b> {status_text}\n"
                f"• <b>Bài hát:</b> <code>{state.music_track}</code>\n"
                f"• <b>Nghệ sĩ:</b> <code>{state.music_artist}</code>\n"
                f"• <b>Tài khoản:</b> <code>{lastfm_user}</code>\n"
                f"• <b>Tổng scrobbles:</b> <code>{state.music_scrobbles}</code>\n"
                f"• <b>Chuỗi hiển thị:</b> <code>{state.current_music}</code>\n"
            )
        else:
            msg = f"🎵 <i>Tài khoản Last.fm:</i> <code>{lastfm_user}</code>\n<i>Hiện chưa có bài hát nào đang phát hoặc chưa nhận được dữ liệu. Hãy nghe nhạc trên Spotify/Apple Music và kiểm tra lại!</i>"
        await event.reply(msg, parse_mode="html", buttons=get_main_keyboard())

    # ========================================================
    # XỬ LÝ NỘI DUNG NHẬP TỪ NGƯỜI DÙNG (CONVERSATIONAL INPUT)
    # ========================================================
    @bot_client.on(events.NewMessage)
    async def user_input_handler(event):
        if not is_admin(event.sender_id): return
        if event.raw_text.startswith("/"): return

        sess = user_sessions.get(event.sender_id)
        if not sess: return

        action = sess.get("action")
        text = event.raw_text.strip()

        # 1. Đổi tên
        if action == "input_name":
            user_sessions.pop(event.sender_id, None)
            state.update_config({"BASE_NAME": text})
            state.trigger_update()
            await event.reply(f"✅ Đã cập nhật <b>BASE_NAME</b>: <code>{text}</code>", parse_mode="html", buttons=get_settings_keyboard())

        # 2. Đổi thành phố
        elif action == "input_city":
            user_sessions.pop(event.sender_id, None)
            state.update_config({"CITY": text})
            state.trigger_update()
            # Test thời tiết
            ok, msg = test_weather_api_sync(state.config.get("WEATHER_API"), text)
            extra = f"\n<i>{msg}</i>" if ok else f"\n⚠️ <i>{msg}</i>"
            await event.reply(f"✅ Đã cập nhật <b>Thành phố</b>: <code>{text}</code>{extra}", parse_mode="html", buttons=get_settings_keyboard())

        # Đổi tài khoản Last.fm
        elif action == "input_lastfm_user":
            user_sessions.pop(event.sender_id, None)
            lastfm_u = "" if text.lower() in ("0", "none", "null", "tat", "tắt", "trong", "trống") else text
            state.update_config({"LASTFM_USERNAME": lastfm_u})
            state.trigger_update()
            if lastfm_u:
                ok, msg = test_lastfm_user_sync(lastfm_u, state.config.get("LASTFM_API_KEY"))
                res_icon = "✔" if ok else "⚠️"
                await event.reply(f"✅ Đã kết nối Last.fm: <code>{lastfm_u}</code>\n{res_icon} <i>{msg}</i>", parse_mode="html", buttons=get_settings_keyboard())
            else:
                await event.reply("✅ Đã tắt liên kết Last.fm.", parse_mode="html", buttons=get_settings_keyboard())

        # 3. Đổi API Key thời tiết
        elif action == "input_weather_api":
            user_sessions.pop(event.sender_id, None)
            api_key = "" if text.lower() in ("none", "null", "trong", "trống", "0") else text
            state.update_config({"WEATHER_API": api_key})
            state.trigger_update()
            ok, msg = test_weather_api_sync(api_key, state.config.get("CITY"))
            res_icon = "✔" if ok else "⚠️"
            await event.reply(f"✅ Đã cập nhật <b>WEATHER_API</b>!\n{res_icon} <i>{msg}</i>", parse_mode="html", buttons=get_settings_keyboard())

        # 4. Đổi Múi giờ tùy chỉnh
        elif action == "input_tz_custom":
            user_sessions.pop(event.sender_id, None)
            state.update_config({"TIMEZONE": text})
            state.trigger_update()
            await event.reply(f"✅ Đã cập nhật <b>TIMEZONE</b>: <code>{text}</code>", parse_mode="html", buttons=get_settings_keyboard())

        # 5. Đổi API_ID & HASH
        elif action == "input_api_id":
            if not text.isdigit():
                await event.reply("⚠️ <b>API_ID phải là chữ số.</b> Vui lòng nhập lại (hoặc /cancel):", parse_mode="html")
                return
            sess["api_id"] = text
            sess["action"] = "input_api_hash"
            await event.reply("🔑 <b>Bước 2/2:</b> Nhập <b>API_HASH</b> của bạn:\n<i>(Ví dụ: b18441a1ff607e10a989891a5462e627)</i>", parse_mode="html", buttons=get_cancel_keyboard())

        elif action == "input_api_hash":
            api_id = sess.get("api_id")
            user_sessions.pop(event.sender_id, None)
            state.update_config({"API_ID": api_id, "API_HASH": text})
            await event.reply(f"✅ Đã lưu <b>API_ID</b>: <code>{api_id}</code> và <b>API_HASH</b>!", parse_mode="html", buttons=get_settings_keyboard())

        # 6. Sửa định dạng Format
        elif action == "input_fmt_name":
            user_sessions.pop(event.sender_id, None)
            state.update_config({"NAME_FORMAT": text})
            state.trigger_update()
            await event.reply(f"✅ Đã lưu <b>NAME_FORMAT</b>: <code>{text}</code>", parse_mode="html", buttons=get_format_keyboard())

        elif action == "input_fmt_bio":
            user_sessions.pop(event.sender_id, None)
            state.update_config({"BIO_FORMAT": text})
            state.trigger_update()
            await event.reply(f"✅ Đã lưu <b>BIO_FORMAT</b>: <code>{text}</code>", parse_mode="html", buttons=get_format_keyboard())

        # 7. QUY TRÌNH ĐĂNG NHẬP TELEGRAM (LOGIN WIZARD)
        elif action == "login_wait_phone":
            phone = text.replace(" ", "").replace("-", "")
            if not phone.startswith("+"):
                await event.reply("⚠️ <b>Số điện thoại phải kèm dấu '+' và mã quốc gia</b> (Ví dụ: <code>+84912345678</code>). Vui lòng nhập lại:", parse_mode="html", buttons=get_cancel_keyboard())
                return

            msg_wait = await event.reply("⏳ <i>Đang kết nối tới máy chủ Telegram và gửi mã OTP...</i>", parse_mode="html")

            raw_api_id = state.config.get("API_ID", "2040")
            api_id = int(raw_api_id) if raw_api_id.isdigit() else 2040
            api_hash = state.config.get("API_HASH", "b18441a1ff607e10a989891a5462e627")

            try:
                temp_client = TelegramClient(StringSession(), api_id, api_hash)
                await temp_client.connect()
                send_result = await temp_client.send_code_request(phone)

                sess["temp_client"] = temp_client
                sess["phone"] = phone
                sess["phone_code_hash"] = send_result.phone_code_hash
                sess["action"] = "login_wait_code"

                await msg_wait.delete()
                await event.reply(
                    f"📩 <b>Mã xác nhận (OTP) đã được gửi tới ứng dụng Telegram của số {phone}!</b>\n\n"
                    f"👉 <b>Vui lòng nhập mã OTP vào đây:</b>\n"
                    f"<i>(Nếu mã có định dạng 12345, bạn có thể gõ 12345 hoặc 1 2 3 4 5)</i>",
                    parse_mode="html",
                    buttons=get_cancel_keyboard()
                )
            except Exception as e:
                user_sessions.pop(event.sender_id, None)
                await msg_wait.delete()
                await event.reply(f"❌ <b>Không thể gửi mã OTP:</b> {e}\n\nVui lòng thử lại sau.", parse_mode="html", buttons=get_settings_keyboard())

        elif action == "login_wait_code":
            otp_code = text.replace(" ", "").replace("-", "")
            temp_client = sess.get("temp_client")
            phone = sess.get("phone")
            phone_code_hash = sess.get("phone_code_hash")

            msg_verifying = await event.reply("⏳ <i>Đang xác minh mã OTP...</i>", parse_mode="html")

            try:
                await temp_client.sign_in(phone=phone, code=otp_code, phone_code_hash=phone_code_hash)
                # Đăng nhập thành công (Không có 2FA)
                session_string = temp_client.session.save()
                me = await temp_client.get_me()
                await temp_client.disconnect()
                user_sessions.pop(event.sender_id, None)

                # Lưu vào .env
                state.update_config({"SESSION_STRING": session_string, "ADMIN_ID": str(me.id)})
                await msg_verifying.delete()

                success_msg = (
                    f"🎉 <b>ĐĂNG NHẬP THÀNH CÔNG!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"• <b>Tên tài khoản:</b> {me.first_name} {me.last_name or ''}\n"
                    f"• <b>Username:</b> @{me.username or 'Không có'}\n"
                    f"• <b>ID:</b> <code>{me.id}</code>\n\n"
                    f"✔ Đã tự động lưu <b>SESSION_STRING</b> vào file <code>.env</code>!\n"
                    f"Bạn có thể bấm <b>▶️ Chạy Updater</b> bên dưới để bắt đầu tự động đổi tên & bio ngay."
                )
                await event.reply(success_msg, parse_mode="html", buttons=get_main_keyboard())

                # Tự động kích hoạt updater nếu chưa chạy
                if not engine.is_running:
                    await engine.start()

            except SessionPasswordNeededError:
                # Cần mật khẩu 2 bước (2FA)
                sess["action"] = "login_wait_password"
                await msg_verifying.delete()
                await event.reply(
                    "🔐 <b>Tài khoản của bạn đã kích hoạt bảo mật 2 lớp (2FA)!</b>\n\n"
                    "👉 <b>Vui lòng gửi mật khẩu 2FA của bạn vào đây:</b>",
                    parse_mode="html",
                    buttons=get_cancel_keyboard()
                )
            except (PhoneCodeInvalidError, PhoneCodeExpiredError) as e:
                await msg_verifying.delete()
                await event.reply(f"⚠️ <b>Mã OTP không chính xác hoặc đã hết hạn ({e})!</b>\nVui lòng nhập lại mã:", parse_mode="html", buttons=get_cancel_keyboard())
            except Exception as e:
                user_sessions.pop(event.sender_id, None)
                if temp_client and temp_client.is_connected():
                    await temp_client.disconnect()
                await msg_verifying.delete()
                await event.reply(f"❌ <b>Lỗi đăng nhập:</b> {e}", parse_mode="html", buttons=get_settings_keyboard())

        elif action == "login_wait_password":
            temp_client = sess.get("temp_client")
            password = text
            msg_pwd = await event.reply("⏳ <i>Đang kiểm tra mật khẩu 2FA...</i>", parse_mode="html")

            try:
                await temp_client.sign_in(password=password)
                session_string = temp_client.session.save()
                me = await temp_client.get_me()
                await temp_client.disconnect()
                user_sessions.pop(event.sender_id, None)

                # Lưu vào .env
                state.update_config({"SESSION_STRING": session_string, "ADMIN_ID": str(me.id)})
                await msg_pwd.delete()

                success_msg = (
                    f"🎉 <b>ĐĂNG NHẬP 2FA THÀNH CÔNG!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"• <b>Tên tài khoản:</b> {me.first_name} {me.last_name or ''}\n"
                    f"• <b>Username:</b> @{me.username or 'Không có'}\n"
                    f"• <b>ID:</b> <code>{me.id}</code>\n\n"
                    f"✔ Đã tự động lưu <b>SESSION_STRING</b> vào file <code>.env</code>!"
                )
                await event.reply(success_msg, parse_mode="html", buttons=get_main_keyboard())

                if not engine.is_running:
                    await engine.start()

            except Exception as e:
                await msg_pwd.delete()
                await event.reply(f"⚠️ <b>Mật khẩu 2FA không đúng ({e})!</b>\nVui lòng nhập lại mật khẩu (hoặc bấm Hủy bỏ):", parse_mode="html", buttons=get_cancel_keyboard())

    # ========================================================
    # XỬ LÝ NÚT BẤM (CALLBACK QUERIES)
    # ========================================================
    @bot_client.on(events.CallbackQuery)
    async def callback_handler(event):
        try:
            await _callback_handler_impl(event)
        except MessageNotModifiedError:
            try:
                await event.answer("Nội dung đã ở trạng thái mới nhất!")
            except Exception:
                pass
        except Exception as e:
            print(f"[⚠️] Callback error: {e}")

    async def _callback_handler_impl(event):
        if not is_admin(event.sender_id):
            await event.answer("⛔ Bạn không có quyền truy cập!", alert=True)
            return

        data = event.data.decode("utf-8")

        # 1. Hủy thao tác
        if data == "cancel_action":
            sess = user_sessions.pop(event.sender_id, None)
            if sess and "temp_client" in sess:
                try:
                    await sess["temp_client"].disconnect()
                except Exception:
                    pass
            await event.edit(format_dashboard(), parse_mode="html", buttons=get_main_keyboard())
            await event.answer("Đã hủy thao tác.")

        # 2. Điều hướng Menu
        elif data == "main_menu":
            user_sessions.pop(event.sender_id, None)
            await event.edit(format_dashboard(), parse_mode="html", buttons=get_main_keyboard())
            await event.answer()

        elif data == "menu_settings":
            user_sessions.pop(event.sender_id, None)
            await event.edit(format_settings_text(), parse_mode="html", buttons=get_settings_keyboard())
            await event.answer()

        # 3. Làm mới trạng thái
        elif data == "status":
            await event.edit(format_dashboard(), parse_mode="html", buttons=get_main_keyboard())
            await event.answer("Đã làm mới thông tin!")

        # 4. Cập nhật profile ngay lập tức
        elif data == "update_now":
            if not engine.is_running:
                await event.answer("⚠️ Updater đang dừng. Vui lòng bấm '▶️ Chạy Updater' trước!", alert=True)
                return
            state.trigger_update()
            await event.answer("🔄 Đã kích hoạt cập nhật ngay...")
            await asyncio.sleep(1)
            await event.edit(format_dashboard(), parse_mode="html", buttons=get_main_keyboard())

        # 5. Bật / Tắt Profile Engine
        elif data == "toggle_engine":
            if engine.is_running:
                await engine.stop()
                await event.answer("⏹️ Đã dừng Profile Updater.")
            else:
                ok, msg = await engine.start()
                if ok:
                    await event.answer("▶️ Đã khởi chạy Profile Updater!")
                else:
                    await event.answer(f"⚠️ {msg}", alert=True)
            await event.edit(format_dashboard(), parse_mode="html", buttons=get_main_keyboard())

        # 6. Tạm dừng / Tiếp tục
        elif data == "toggle_pause":
            state.is_paused = not state.is_paused
            if not state.is_paused:
                state.trigger_update()
                await event.answer("▶️ Đã tiếp tục cập nhật!")
            else:
                await event.answer("⏸️ Đã tạm dừng cập nhật!")
            await event.edit(format_dashboard(), parse_mode="html", buttons=get_main_keyboard())

        # 7. Xem trước (Preview)
        elif data == "preview":
            p_name, p_bio = generate_preview()
            preview_msg = (
                f"👁️ <b>XEM TRƯỚC (PREVIEW) PROFILE</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"• <b>Tên:</b> <code>{p_name}</code> ({len(p_name)}/64 ký tự)\n"
                f"• <b>Bio:</b> <code>{p_bio}</code> ({len(p_bio)}/70 ký tự)\n"
            )
            await event.respond(preview_msg, parse_mode="html")
            await event.answer()

        # 7b. Xem trước Bio chuyên sâu
        elif data == "preview_bio":
            await event.respond(format_bio_preview_card(), parse_mode="html")
            await event.answer()

        # 7c. Thẻ thông tin thời tiết chi tiết
        elif data == "weather_card":
            await event.respond(format_weather_card(), parse_mode="html")
            await event.answer()

        # 8. Cài đặt Đăng nhập
        elif data == "setup_login":
            user_sessions[event.sender_id] = {"action": "login_wait_phone"}
            msg = (
                "📱 <b>ĐĂNG NHẬP TELEGRAM USERBOT</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "Vui lòng nhập <b>Số điện thoại</b> tài khoản Telegram của bạn:\n"
                "<i>(Bắt buộc có dấu '+' và mã quốc gia, ví dụ: <code>+84912345678</code>)</i>"
            )
            await event.respond(msg, parse_mode="html", buttons=get_cancel_keyboard())
            await event.answer()

        # 9. Cài đặt Tên cố định
        elif data == "setup_name":
            user_sessions[event.sender_id] = {"action": "input_name"}
            curr = state.config.get("BASE_NAME", "tên")
            await event.respond(f"✏️ <b>ĐỔI TÊN CỐ ĐỊNH (BASE_NAME)</b>\nHiện tại: <code>{curr}</code>\n\n👉 <b>Nhập tên mới của bạn:</b>", parse_mode="html", buttons=get_cancel_keyboard())
            await event.answer()

        # 10. Cài đặt Thành phố
        elif data == "setup_city":
            user_sessions[event.sender_id] = {"action": "input_city"}
            curr = state.config.get("CITY", "Bac Ninh")
            await event.respond(f"📍 <b>ĐỔI TỈNH / THÀNH PHỐ</b>\nHiện tại: <code>{curr}</code>\n\n👉 <b>Nhập tên thành phố mới:</b>\n<i>(Ví dụ: Hanoi, Ho Chi Minh, Da Nang, Bac Ninh)</i>", parse_mode="html", buttons=get_cancel_keyboard())
            await event.answer()

        # 11. Cài đặt Thời tiết
        elif data == "setup_weather":
            user_sessions[event.sender_id] = {"action": "input_weather_api"}
            curr = state.config.get("WEATHER_API") or "Chưa cấu hình"
            msg = (
                f"⛅ <b>CẤU HÌNH OPENWEATHERMAP API</b>\n"
                f"API Key hiện tại: <code>{curr}</code>\n\n"
                f"Lấy API Key miễn phí tại: https://home.openweathermap.org/api_keys\n\n"
                f"👉 <b>Gửi API Key mới vào đây (hoặc gõ '0' để tắt):</b>"
            )
            await event.respond(msg, parse_mode="html", buttons=get_cancel_keyboard())
            await event.answer()

        # 12. Cài đặt Last.fm (Nhạc)
        elif data == "setup_lastfm":
            user_sessions[event.sender_id] = {"action": "input_lastfm_user"}
            curr = state.config.get("LASTFM_USERNAME") or "Chưa cấu hình"
            msg = (
                "🎵 <b>CẤU HÌNH TÀI KHOẢN LAST.FM (NGHE NHẠC)</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"• Tài khoản hiện tại: <code>{curr}</code>\n\n"
                "Last.fm tự động scrobble (ghi nhận) bài hát bạn đang nghe từ Spotify, Apple Music, YouTube Music...\n\n"
                "👉 <b>Vui lòng gửi Username Last.fm của bạn (hoặc gõ '0' để tắt):</b>"
            )
            await event.respond(msg, parse_mode="html", buttons=get_cancel_keyboard())
            await event.answer()

        # 13. Cài đặt Múi giờ
        elif data == "setup_timezone":
            await event.edit("🕒 <b>CHỌN MÚI GIỜ (TIMEZONE)</b>\n\nVui lòng chọn múi giờ phổ biến bên dưới hoặc tự nhập:", parse_mode="html", buttons=get_timezone_keyboard())
            await event.answer()

        elif data.startswith("tz_"):
            tz_val = data.replace("tz_", "")
            if tz_val == "custom":
                user_sessions[event.sender_id] = {"action": "input_tz_custom"}
                await event.respond("🕒 <b>Nhập múi giờ chuẩn IANA:</b>\n<i>(Ví dụ: Asia/Ho_Chi_Minh, America/New_York, Europe/London)</i>", parse_mode="html", buttons=get_cancel_keyboard())
            else:
                state.update_config({"TIMEZONE": tz_val})
                state.trigger_update()
                await event.edit(f"✅ Đã chọn múi giờ: <code>{tz_val}</code>", parse_mode="html", buttons=get_settings_keyboard())
            await event.answer()

        # 14. Cài đặt API Creds
        elif data == "setup_api_creds":
            user_sessions[event.sender_id] = {"action": "input_api_id"}
            msg = (
                "🆔 <b>CẤU HÌNH TELEGRAM API_ID & API_HASH</b>\n"
                "Lấy tại https://my.telegram.org\n\n"
                f"• API_ID hiện tại: <code>{state.config.get('API_ID')}</code>\n"
                f"• API_HASH hiện tại: <code>{state.config.get('API_HASH')}</code>\n\n"
                "👉 <b>Bước 1/2: Nhập API_ID mới:</b>"
            )
            await event.respond(msg, parse_mode="html", buttons=get_cancel_keyboard())
            await event.answer()

        # 15. Cài đặt Định dạng Format
        elif data == "setup_format":
            p_name, p_bio = generate_preview()
            msg = (
                f"🎨 <b>TÙY BIẾN ĐỊNH DẠNG TÊN & BIO</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"• <b>NAME_FORMAT:</b> <code>{state.config.get('NAME_FORMAT')}</code>\n"
                f"  👉 Tên hiện tại: <code>{p_name}</code>\n"
                f"• <b>BIO_FORMAT:</b> <code>{state.config.get('BIO_FORMAT')}</code>\n"
                f"  👉 Bio hiện tại: <code>{p_bio}</code>\n\n"
                f"<b>Từ khóa hỗ trợ:</b> <code>HH</code>, <code>mm</code>, <code>ss</code>, <code>DD</code>, <code>MM</code>, <code>YYYY</code>, <code>{{base_name}}</code>, <code>{{thu}}</code>, <code>{{city}}</code>, <code>{{weather}}</code>, <code>{{music}}</code>, <code>{{music_or_weather}}</code>, <code>{{track}}</code>, <code>{{artist}}</code>\n\n"
                f"<i>Hãy bấm chọn một trong các mẫu bên dưới hoặc tự nhập mẫu riêng:</i>"
            )
            await event.edit(msg, parse_mode="html", buttons=get_format_keyboard())
            await event.answer()

        elif data.startswith("preset_"):
            presets = {
                "preset_1": ("{base_name} | HH:mm - DD/MM/YYYY", "NAME_FORMAT"),
                "preset_2": ("{base_name} | {thu}, DD/MM/YYYY - HH:mm", "NAME_FORMAT"),
                "preset_3": ("{base_name} | {thu_ngan} • HH:mm", "NAME_FORMAT"),
                "preset_4": ("{base_name} ⏰ HH:mm (DD/MM)", "NAME_FORMAT"),
                "preset_5": ("{base_name} | {city} • HH:mm", "NAME_FORMAT"),
                "preset_6": ("{base_name} | {music_or_weather}", "NAME_FORMAT"),
                "preset_7": ("{music_or_weather} ⏰ HH:mm", "BIO_FORMAT"),
                "preset_8": ("📍 {city} • {weather_short} ⏰ HH:mm", "BIO_FORMAT"),
                "preset_9": ("{music_or_weather} | 📍 {city}", "BIO_FORMAT"),
            }
            preset_info = presets.get(data)
            if preset_info:
                chosen, target_field = preset_info
                state.update_config({target_field: chosen})
                state.trigger_update()
                p_name, p_bio = generate_preview()
                field_title = "ĐỊNH DẠNG TÊN" if target_field == "NAME_FORMAT" else "ĐỊNH DẠNG BIO"
                await event.answer("✔ Đã áp dụng mẫu định dạng mới!", alert=True)
                msg = (
                    f"🎨 <b>ĐÃ ÁP DỤNG {field_title} MỚI!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"• <b>Mẫu:</b> <code>{chosen}</code>\n"
                    f"• <b>Tên xem trước:</b> <code>{p_name}</code> ({len(p_name)}/64 ký tự)\n"
                    f"• <b>Bio xem trước:</b> <code>{p_bio}</code> ({len(p_bio)}/70 ký tự)\n\n"
                    f"<i>Profile Telegram đang được cập nhật tự động...</i>"
                )
                await event.edit(msg, parse_mode="html", buttons=get_format_keyboard())

        elif data == "fmt_name":
            user_sessions[event.sender_id] = {"action": "input_fmt_name"}
            msg = (
                "✏️ <b>NHẬP MẪU NAME_FORMAT MỚI</b>\n\n"
                "Ví dụ mẫu:\n"
                "• <code>{base_name} | HH:mm - DD/MM/YYYY</code>\n"
                "• <code>HzzMonet | HH:mm - DD/MM/YYYY</code>\n"
                "• <code>{base_name} | {thu}, DD/MM/YYYY - HH:mm</code>\n\n"
                "👉 <b>Vui lòng gửi tin nhắn chứa mẫu định dạng của bạn:</b>"
            )
            await event.respond(msg, parse_mode="html", buttons=get_cancel_keyboard())
            await event.answer()

        elif data == "fmt_bio":
            user_sessions[event.sender_id] = {"action": "input_fmt_bio"}
            msg = (
                "📝 <b>NHẬP MẪU BIO_FORMAT MỚI</b>\n\n"
                "Ví dụ mẫu:\n"
                "• <code>{weather} ⏰ HH:mm</code>\n"
                "• <code>📍 {city} | ⏰ HH:mm - DD/MM</code>\n\n"
                "👉 <b>Vui lòng gửi tin nhắn chứa mẫu bio của bạn:</b>"
            )
            await event.respond(msg, parse_mode="html", buttons=get_cancel_keyboard())
            await event.answer()

        elif data == "fmt_reset":
            state.update_config({
                "NAME_FORMAT": "{base_name} | HH:mm - DD/MM/YYYY",
                "BIO_FORMAT": "{weather} ⏰ HH:mm"
            })
            state.trigger_update()
            await event.answer("✔ Đã đặt lại định dạng mặc định!", alert=True)
            p_name, p_bio = generate_preview()
            msg = (
                f"🎨 <b>ĐÃ KHÔI PHỤC ĐỊNH DẠNG MẶC ĐỊNH!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"• <b>Tên:</b> <code>{p_name}</code>\n"
                f"• <b>Bio:</b> <code>{p_bio}</code>\n"
            )
            await event.edit(msg, parse_mode="html", buttons=get_format_keyboard())

        # 15. Trợ giúp
        elif data == "help":
            msg = (
                "📖 <b>DANH SÁCH LỆNH & TÍNH NĂNG</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "• <b>Đăng nhập qua chat:</b> Bấm [⚙️ Cài đặt] -> [🔑 Đăng nhập Telegram] và làm theo hướng dẫn.\n"
                "• <b>Cập nhật tức thì:</b> Bấm [🔄 Cập nhật ngay] hoặc gõ <code>/update</code>.\n"
                "• <b>Đổi tên nhanh:</b> Gõ <code>/setname Tên Của Bạn</code>.\n"
                "• <b>Đổi thành phố nhanh:</b> Gõ <code>/setcity Ha Noi</code>.\n"
                "• <b>Bật / Tắt:</b> Bấm [▶️ Chạy] hoặc [⏹️ Dừng]."
            )
            await event.respond(msg, parse_mode="html")
            await event.answer()

async def run_standalone_bot():
    """Chạy Helper Bot độc lập"""
    state.reload_config()
    raw_api_id = state.config.get("API_ID", "2040")
    api_id = int(raw_api_id) if raw_api_id.isdigit() else 2040
    api_hash = state.config.get("API_HASH", "b18441a1ff607e10a989891a5462e627")
    bot_token = state.config.get("BOT_TOKEN", "").strip()

    if not bot_token:
        print("[❌] Chưa cấu hình BOT_TOKEN trong file .env!")
        print("Vui lòng cấu hình BOT_TOKEN (lấy từ @BotFather) để khởi chạy Helper Bot.")
        return

    print("=" * 60)
    print("🤖 KHỞI ĐỘNG TELEGRAM HELPER BOT...")
    print("=" * 60)

    bot_client = TelegramClient("helper_bot_session", api_id, api_hash)
    register_bot_handlers(bot_client)

    await bot_client.start(bot_token=bot_token)
    me = await bot_client.get_me()
    print(f"[✅] Helper Bot đang hoạt động: @{me.username} (ID: {me.id})")
    print(f"[ℹ️] ADMIN_ID được cấp phép: {state.config.get('ADMIN_ID') or 'Tự động gán user đầu tiên'}")

    # Tự động khởi động Profile Updater nếu đã có SESSION_STRING
    if state.config.get("SESSION_STRING"):
        print("[🚀] Tự động khởi động Profile Updater...")
        ok, msg = await engine.start()
        print(f"[{'✅' if ok else '⚠️'}] {msg}")
    else:
        print("[ℹ️] Chưa có SESSION_STRING. Hãy nhắn tin /start với bot trên Telegram và chọn 'Đăng nhập Telegram' để bắt đầu!")

    print("\nNhấn Ctrl+C để dừng bot.")
    await bot_client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(run_standalone_bot())
    except (KeyboardInterrupt, SystemExit):
        print("\n[👋] Đã dừng Helper Bot.")
