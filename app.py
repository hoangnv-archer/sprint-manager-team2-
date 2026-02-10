import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timezone, timedelta
from streamlit_autorefresh import st_autorefresh

# --- 1. CẤU HÌNH HỆ THỐNG ---
VN_TZ = timezone(timedelta(hours=7))
# Tự động refresh mỗi 30 giây để kiểm tra giờ gửi cố định
st_autorefresh(interval=30000, key="tele_report_check")

# Danh sách giờ gửi báo cáo tự động
SCHEDULED_HOURS = ["15:30", "16:00"]

# Thông tin Telegram
TG_TOKEN = "8535993887:AAFDNSLk9KRny99kQrAoQRbgpKJx_uHbkpw" 
TG_CHAT_ID = "-1002102856307" 
TG_TOPIC_ID = 18251

# --- 2. CÁC HÀM HỖ TRỢ ---
def get_actual_hours(start_val):
    if pd.isna(start_val) or str(start_val).strip().lower() in ['none', '']:
        return 0
    try:
        start_dt = pd.to_datetime(start_val)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=VN_TZ)
        now_vn = datetime.now(VN_TZ)
        diff = now_vn - start_dt
        return max(0, diff.total_seconds() / 3600)
    except:
        return 0

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID, 
        "message_thread_id": TG_TOPIC_ID,
        "text": message, 
        "parse_mode": "Markdown",
        "disable_web_page_preview": True # Tắt xem trước link vì không dùng ảnh
    }
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        return {"ok": False, "description": str(e)}

def build_report(stats_df, alerts_list, is_auto=False):
    now_str = datetime.now(VN_TZ).strftime('%d/%m %H:%M')
    prefix = "🤖 *AUTO REPORT*" if is_auto else "📊 *MANUAL REPORT*"
    msg = f"{prefix} ({now_str})\n"
    msg += "━━━━━━━━━━━━━━━━━━\n\n"

    # Emoji bổ trợ cho từng người (Gọn gàng thay cho Avatar)
    PIC_EMOJIS = {
        "Chuân": "👨‍💻", "Việt": "👨‍🎨", "Thắng": "🚀", "QA": "🔍",
        "Mai": "👩‍💻", "Hải Anh": "✨", "Thuật": "⚙️", "Hiếu": "🛠️"
    }

    for _, r in stats_df.iterrows():
        emoji = PIC_EMOJIS.get(r['PIC'], "👤")
        
        # Định dạng văn bản thuần túy, sạch sẽ
        msg += f"{emoji} *{r['PIC']}*\n"
        msg += f"┣ Tiến độ: **{r['percent']}%** \n"
        msg += f"┣ ✅ Xong: `{int(r['done'])}` | 🚧 Đang: `{int(r['doing'])}`\n"
        msg += f"┣ ⏳ *Tồn đọng: {int(r['pending'])} task*\n"
        msg += f"┗ ⏱ Giờ: `{round(r['real_sum'], 1)}h / {round(r['est_sum'], 1)}h`\n"
        msg += "──────────────────\n"
    
    if alerts_list:
        msg += "\n🚨 *CẢNH BÁO VƯỢT GIỜ:*\n"
        for item in alerts_list:
            msg += f"🔥 `{item['PIC']}`: {item['Task']}\n"
            msg += f"    └ Thực tế: **{item['Thực tế']}** (Dự kiến: {item['Dự kiến']})\n"
    return msg

# --- 3. GIAO DIỆN & XỬ LÝ DỮ LIỆU ---
st.set_page_config(page_title="Team 2 Sprint Dashboard", layout="wide")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    URL_TEAM_2 = "https://docs.google.com/spreadsheets/d/1hentY_r7GNVwJWM3wLT7LsA3PrXQidWnYahkfSwR9Kw/edit?pli=1&gid=982443592#gid=982443592"

    df_raw = conn.read(spreadsheet=URL_TEAM_2
