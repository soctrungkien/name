# Telegram Name & Bio Auto Updater + Helper Bot

Hệ thống tự động cập nhật tên và bio (tiểu sử) tài khoản Telegram theo thời gian thực, thời tiết chi tiết đa nguồn và âm nhạc đang nghe (**Last.fm / Spotify / Apple Music**), tích hợp **Helper Bot** để điều khiển, xem trước bio, hỗ trợ song ngữ **Tiếng Việt 🇻🇳 & English 🇬🇧**, và cấu hình từ xa qua nút bấm trực quan.

---

## 🌐 Hỗ trợ Đa Ngôn Ngữ / Bilingual Support (Vietnamese & English)

Hệ thống hỗ trợ chuyển đổi linh hoạt giữa **Tiếng Việt** và **English**:
- **Chuyển đổi tức thì**:
  - Gõ lệnh Helper Bot: `/lang en` hoặc `/lang vi` (hoặc `/lang` để mở menu chọn).
  - Gõ lệnh Userbot: `.lang en` hoặc `.lang vi`.
  - Bấm nút **[🌐 Ngôn ngữ / Language]** trong Menu chính hoặc Menu Cài đặt của Helper Bot.
- **Tự động dịch toàn diện**:
  - Toàn bộ giao diện Bảng điều khiển (Dashboard), Menu Cài đặt, Thông báo, Hướng dẫn `/help`.
  - Tự động địa phương hóa mô tả Thời tiết (OpenWeatherMap & wttr.in theo ngôn ngữ đã chọn).
  - Tự động địa phương hóa thứ trong tuần: `{thu}`, `{thu_ngan}` (Tiếng Việt) và `{day}`, `{day_short}`, `{day_name}` (English).
  - Lưu tùy chọn ngôn ngữ vào `LANGUAGE=vi` hoặc `LANGUAGE=en` trong `.env`.

---

## 📁 Cấu trúc thư mục

- `setup.py`: Công cụ tương tác trực quan cấu hình API, .env, đăng nhập Telegram, kiểm tra Helper Bot, OpenWeatherMap, wttr.in & Last.fm.
- `name.py`: Script chính khởi chạy hệ thống (tự động phát hiện và chạy Profile Updater + Helper Bot song song).
- `helper_bot.py`: Module Helper Bot với giao diện nút bấm inline, xem trước Bio chuyên sâu, thẻ thời tiết chi tiết và wizard đăng nhập.
- `profile_engine.py`: Bộ máy xử lý và áp dụng cập nhật Tên & Bio lên Telegram, tích hợp OpenWeatherMap + wttr.in fallback và Last.fm Scrobbler.
- `updater_state.py`: Quản lý trạng thái chia sẻ (status, pause, reload env, force update event, now playing music, weather data).
- `generate_session.py`: Script hỗ trợ đăng nhập lấy `SESSION_STRING`.
- `.env`: File cấu hình biến môi trường thực tế.
- `.env.example`: File mẫu biến môi trường.
- `requirements.txt`: Danh sách thư viện Python.

---

## 🌤️ Nâng cấp Thời tiết Chi tiết & Tự động Đa Nguồn

Hệ thống hỗ trợ lấy thời tiết theo thời gian thực:
- **Tự động không cần API Key**: Tự động fallback sang nguồn `wttr.in` với mô tả tiếng Việt chuẩn xác (nhiệt độ, cảm giác thực tế, độ ẩm, tốc độ gió).
- **Hỗ trợ OpenWeatherMap**: Cung cấp đầy đủ thông số áp suất, bình minh, hoàng hôn khi cấu hình `WEATHER_API`.
- **Thẻ thời tiết trực quan**: Xem nhanh bằng lệnh `/weather` hoặc nút `[🌤️ Thời tiết chi tiết]` trên Helper Bot.
- **Tự động cân đối độ dài Bio**: Placeholder `{weather}` tự động rút gọn để đảm bảo không vượt quá giới hạn 70 ký tự của Telegram.

---

## 📝 Tính năng Xem trước Bio (Bio Preview)

Telegram giới hạn Bio tài khoản tối đa **70 ký tự**:
- Lệnh `/previewbio` (hoặc `/bio`): Đánh giá chính xác độ dài ký tự của mẫu `BIO_FORMAT`.
- **Mô phỏng đa kịch bản**:
  1. *Khi đang phát nhạc*: Hiển thị bài hát từ Last.fm/Spotify.
  2. *Khi không nghe nhạc / ở chế độ chờ*: Tự chuyển sang hiển thị thời tiết hoặc trạng thái.
- Đưa ra cảnh báo trực quan `🟢 Hợp lệ` hoặc `🔴 VƯỢT GIỚI HẠN 70 KÝ TỰ` kèm số ký tự thừa/thiếu.

---

## 🎵 Tính năng Tích hợp Âm nhạc Last.fm (Spotify / Apple Music)

Bot tự động lấy thông tin bài hát bạn đang nghe theo thời gian thực từ Last.fm:
- Hỗ trợ **Spotify, Apple Music, YouTube Music, Deezer, Tidal**... (bất kỳ trình phát nào liên kết với Last.fm).
- Thẻ đặc biệt `{music_or_weather}`: Tự động hiển thị bài hát khi bạn đang nghe nhạc; tự động chuyển sang hiển thị thời tiết khi bạn tắt nhạc!
- Kiểm tra bài hát đang phát tức thì bằng lệnh `/music` hoặc `.music`.
- API Key mặc định đã có sẵn, bạn chỉ cần nhập Last.fm Username (`/lastfm <username>`).

---

## 🎨 Tùy biến Tên (BASE_NAME) & Định dạng hiển thị

Hệ thống hỗ trợ tùy biến định dạng tên và bio linh hoạt với các từ khóa ngày giờ, thời tiết và âm nhạc:

### 1. Các từ khóa hỗ trợ:
| Từ khóa | Ý nghĩa | Ví dụ |
| :--- | :--- | :--- |
| `{base_name}` | Tên cố định bạn cài đặt | `HzzMonet` |
| `HH` / `{HH}` | Giờ 24h (00 - 23) | `21` |
| `mm` / `{mm}` | Phút (00 - 59) | `09` |
| `ss` / `{ss}` | Giây (00 - 59) | `45` |
| `hh` / `{hh}` | Giờ 12h (01 - 12) | `09` |
| `ampm` | Buổi (AM / PM) | `PM` |
| `DD` / `{DD}` | Ngày trong tháng (01 - 31) | `12` |
| `MM` / `{MM}` | Tháng trong năm (01 - 12) | `09` |
| `YYYY` / `{YYYY}` | Năm 4 chữ số | `2026` |
| `YY` / `{YY}` | Năm 2 chữ số | `26` |
| `{thu}` | Thứ tiếng Việt | `Thứ Bảy` |
| `{thu_ngan}` | Thứ ngắn tiếng Việt | `T7` |
| `{day}` / `{day_name}` | Thứ tiếng Anh (English weekday) | `Saturday` |
| `{day_short}` | Thứ ngắn tiếng Anh (English short day) | `Sat` |
| `{city}` | Tên tỉnh / thành phố | `Bac Ninh` |
| `{weather}` | Chuỗi thời tiết tự động cân đối cho Bio | `📍 Bac Ninh` |
| `{weather_short}` | Thời tiết siêu ngắn (Icon + Nhiệt độ) | `⛅ 28°C` |
| `{weather_medium}` | Thời tiết vừa (Icon + Tỉnh + Nhiệt + Ẩm) | `⛅ Hanoi 28°C \| 75%` |
| `{weather_full}` | Toàn bộ thông số thời tiết chi tiết | `📍 Hanoi: ⛅ 28°C \| 75% \| 3m/s` |
| `{temp}` / `{nhiet_do}` | Nhiệt độ hiện tại | `28°C` |
| `{feels_like}` / `{cam_giac}` | Cảm giác thực tế | `30°C` |
| `{humidity}` / `{do_am}` | Độ ẩm không khí | `75%` |
| `{wind}` / `{gio_toc}` | Tốc độ gió | `3.5m/s` |
| `{weather_desc}` | Mô tả tình trạng thời tiết | `Mây thưa` |
| `{weather_icon}` | Icon thời tiết | `⛅` |
| `{sunrise}` / `{sunset}` | Giờ bình minh / hoàng hôn | `05:42` / `18:05` |
| `{music}` | Bài hát đang nghe (kèm icon 🎧/🎵) | `🎧 Blinding Lights - The Weeknd` |
| `{music_or_weather}` | Ưu tiên nhạc khi phát, về thời tiết khi tắt | `🎧 Blinding Lights - The Weeknd` |
| `{track}` | Tên bài hát | `Blinding Lights` |
| `{artist}` | Tên nghệ sĩ/ca sĩ | `The Weeknd` |
| `{album}` | Tên album | `After Hours` |
| `{scrobbles}` | Tổng số bài đã nghe trên Last.fm | `14250` |

### 2. Các mẫu định dạng phổ biến:
- `HzzMonet | HH:mm - DD/MM/YYYY` ➡️ **HzzMonet | 21:09 - 12/09/2026**
- `{base_name} | {music_or_weather}` ➡️ **HzzMonet | 🎧 Blinding Lights - The Weeknd**
- `{music_or_weather} ⏰ HH:mm` ➡️ **🎧 Blinding Lights - The Weeknd ⏰ 21:09**
- `📍 {city} • {weather_short} ⏰ HH:mm` ➡️ **📍 Bac Ninh • ⛅ 28°C ⏰ 21:09**
- `{music_or_weather} | 📍 {city}` ➡️ **🎧 Blinding Lights - The Weeknd | 📍 Bac Ninh**
- `{base_name} | {thu}, DD/MM/YYYY - HH:mm` ➡️ **HzzMonet | Thứ Bảy, 12/09/2026 - 21:09**
- `{base_name} | {day}, DD/MM/YYYY - HH:mm` ➡️ **HzzMonet | Saturday, 12/09/2026 - 21:09**
- `{base_name} ⏰ HH:mm (DD/MM)` ➡️ **HzzMonet ⏰ 21:09 (12/09)**
- `{base_name} | {thu_ngan} • HH:mm` ➡️ **HzzMonet | T7 • 21:09**
- `{base_name} | {day_short} • HH:mm` ➡️ **HzzMonet | Sat • 21:09**

---

## 🤖 Điều khiển qua Helper Bot (@BotFather)

Khi nhắn tin riêng với bot của bạn trên Telegram:
- `/start` - Bật bảng điều khiển với các nút Inline:
  - 🔄 **Cập nhật ngay**: Kích hoạt đổi tên & bio ngay lập tức.
  - 👁️ **Xem trước Profile**: Kiểm tra hiển thị cả Tên & Bio.
  - 📝 **Xem trước Bio**: Kiểm tra chuyên sâu độ dài 70 ký tự và kịch bản nhạc/thời tiết.
  - 🌤️ **Thời tiết chi tiết**: Mở thẻ thông số thời tiết đầy đủ của thành phố.
  - 🌐 **Ngôn ngữ**: Đổi giao diện sang Tiếng Việt 🇻🇳 hoặc English 🇬🇧.
  - ✏️ **Đổi tên (BASE_NAME)**: Nhập tên mới bất kỳ lúc nào.
  - 🎵 **Last.fm**: Cài đặt username Last.fm để nghe nhạc.
  - 🎨 **Mẫu hiển thị (Format)**: Bấm chọn các mẫu có sẵn (Mẫu 1-8) hoặc tự nhập mẫu riêng.
  - ⏸️/▶️ **Tạm dừng / Tiếp tục**: Tạm ngừng hoặc kích hoạt lại auto-update.
- `/lang <en|vi>`: Đổi ngôn ngữ bot (Tiếng Việt / English).
- `/previewbio` (hoặc `/bio`): Mở thẻ phân tích và xem trước tiểu sử.
- `/weather`: Xem thông tin thời tiết chi tiết.
- `/lastfm <username>`: Kết nối tài khoản Last.fm.
- `/music` (hoặc `/nowplaying`): Xem thông tin bài hát đang phát.
- `/setname <tên>` (hoặc `/basename <tên>`): Đổi tên nhanh (ví dụ: `/setname HzzMonet`).
- `/nameformat <mẫu>`: Đổi mẫu định dạng tên (ví dụ: `/nameformat {base_name} | HH:mm - DD/MM/YYYY`).
- `/bioformat <mẫu>`: Đổi mẫu định dạng bio (ví dụ: `/bioformat {music_or_weather} ⏰ HH:mm`).
- `/setcity <thành phố>`: Đổi thành phố thời tiết.
- `/help` - Xem cẩm nang hướng dẫn đầy đủ từ khóa và ví dụ.

---

## ⚡ Tự gõ lệnh trên Userbot (Không cần Bot Token)
Gõ trực tiếp trong **Saved Messages** hoặc bất kỳ đoạn chat nào:
- `.lang <en|vi>` : Đổi ngôn ngữ (Tiếng Việt / English).
- `.bio` / `.previewbio` : Xem trước Bio & kiểm tra độ dài 70 ký tự.
- `.weather` : Xem chi tiết thời tiết (nhiệt độ, cảm giác thực tế, độ ẩm, gió, bình minh...).
- `.preview` : Xem trước Tên và Bio hiện tại.
- `.lastfm <username>` : Kết nối tài khoản Last.fm.
- `.music` : Xem bài hát đang phát.
- `.name <tên mới>` : Đổi `BASE_NAME` (ví dụ: `.name HzzMonet`).
- `.nameformat <mẫu>` : Đổi mẫu tên (ví dụ: `.nameformat {base_name} | HH:mm - DD/MM/YYYY`).
- `.bioformat <mẫu>` : Đổi mẫu bio (ví dụ: `.bioformat {music_or_weather} ⏰ HH:mm`).
- `.city <thành phố>` : Đổi thành phố thời tiết.
- `.update` : Cập nhật profile ngay lập tức.
- `.status` : Xem thông tin trạng thái.
- `.pause` / `.resume` : Tạm dừng / tiếp tục.
- `.help` : Bảng trợ giúp lệnh.

---

## 🚀 Khởi chạy hệ thống

```bash
# Cấu hình qua giao diện Setup Wizard
python3 setup.py

# Khởi chạy trực tiếp (Chạy cả Profile Updater + Helper Bot)
python3 name.py

# Hoặc khởi chạy nền với PM2
pm2 start name.py --name "tele-updater" --interpreter python3
pm2 save
```
