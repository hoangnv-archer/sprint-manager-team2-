import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timezone, timedelta
from streamlit_autorefresh import st_autorefresh

# --- 1. CẤU HÌNH HỆ THỐNG ---
VN_TZ = timezone(timedelta(hours=7))
st_autorefresh(interval=30000, key="tele_report_check")

SCHEDULED_HOURS = ["15:30", "16:00"]

# Từ điển chứa link ảnh của từng người (Bạn hãy thay link ảnh thật vào đây)
PIC_AVATARS = {
    "Chuân": "https://cdn-icons-png.flaticon.com/512/6840/6840478.png",
    "Việt": "https://cdn-icons-png.flaticon.com/512/3135/3135715.png",
    "Thắng": "https://cdn-icons-png.flaticon.com/512/2202/2202112.png",
    "QA": "https://cdn-icons-png.flaticon.com/512/4439/4439197.png",
    "Mai": "https://cdn-icons-png.flaticon.com/512/6997/6997662.png",
    "Hải Anh": "https://cdn-icons-png.flaticon.com/512/4140/4140047.png",
    "Thuật": "https://cdn-icons-png.flaticon.com/512/236/236832.png",
    "Hiếu": "https://cdn-icons-png.flaticon.com/512/3048/3048122.png"
}

TG_TOKEN = "8535993887:AAFDNSLk9KRny99kQrAoQRbgpKJx_uHbkpw" 
TG_CHAT_ID = "-1002102856307" 
TG_TOPIC_ID = 18251

# --- 2. CÁC HÀM HỖ TRỢ ---
def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID, 
        "message_thread_id": TG_TOPIC_ID,
        "text": message, 
        "parse_mode": "Markdown",
        "disable_web_page_preview": False  # Cho phép hiển thị xem trước ảnh
    }
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        return {"ok": False, "description": str(e)}

def build_report(pic_stats, over_est_list, is_auto=False):
    now_str = datetime.now(VN_TZ).strftime('%d/%m %H:%M')
    prefix = "🤖 *AUTO REPORT*" if is_auto else "📊 *MANUAL REPORT*"
    msg = f"{prefix} ({now_str})\n"
    msg += "━━━━━━━━━━━━━━━━━━\n\n"
    
    for _, r in pic_stats.iterrows():
        # Lấy link ảnh từ từ điển, nếu không có thì dùng icon mặc định
        avatar_url = PIC_AVATARS.get(r['PIC'], "https://cdn-icons-png.flaticon.com/512/847/847969.png")
        
        # Gán link ảnh vào Emoji đầu dòng (Cách này giúp tin nhắn gọn mà vẫn có ảnh khi click)
        msg += f"[🖼️]({avatar_url}) *{r['PIC']}*\n"
        msg += f"┣ Tiến độ: **{r['percent']}%** \n"
        msg += f"┣ ✅ Xong: {int(r['done'])} | 🚧 Đang: {int(r['doing'])}\n"
        msg += f"┣ ⏳ *Tồn đọng: {int(r['pending'])} task*\n"
        msg += f"┗ ⏱ Giờ: `{round(r['real_sum'], 1)}h / {round(r['est_sum'], 1)}h`\n"
        msg += "──────────────────\n"
    
    if over_est_list:
        msg += "\n🚨 *CẢNH BÁO VƯỢT GIỜ:*\n"
        for item in over_est_list:
            msg += f"🔥 `{item['PIC']}`: {item['Task']}\n"
            msg += f"    └ Thực tế: **{item['Thực tế']}**\n"
    return msg

# --- 3. GIAO DIỆN & XỬ LÝ DỮ LIỆU (Giữ nguyên cấu trúc đã sửa lỗi thụt lề) ---
st.set_page_config(page_title="Team 2 Sprint Dashboard", layout="wide")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    URL_TEAM_2 = "https://docs.google.com/spreadsheets/d/1hentY_r7GNVwJWM3wLT7LsA3PrXQidWnYahkfSwR9Kw/edit?pli=1&gid=982443592#gid=982443592"

    df_raw = conn.read(spreadsheet=URL_TEAM_2, header=None, ttl=0)
    header_idx = next((i for i, row in df_raw.iterrows() if "Userstory/Todo" in row.values), None)
            
    if header_idx is not None:
        df = conn.read(spreadsheet=URL_TEAM_2, skiprows=header_idx, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]
        
        # ... (Toàn bộ logic xử lý df, pic_stats, over_est_list giữ nguyên như bản trước) ...
        # (Để tiết kiệm không gian, tôi tập trung vào phần gửi tin nhắn dưới đây)

        # --- LOGIC TỰ ĐỘNG GỬI ---
        now = datetime.now(VN_TZ)
        today_date = now.strftime("%Y-%m-%d")
        
        if "sent_log" not in st.session_state:
            st.session_state.sent_log = []

        for scheduled_time in SCHEDULED_HOURS:
            sched_h, sched_m = map(int, scheduled_time.split(":"))
            sched_dt = now.replace(hour=sched_h, minute=sched_m, second=0, microsecond=0)
            log_key = f"{today_date}_{scheduled_time}"
            
            if sched_dt <= now <= (sched_dt + timedelta(minutes=10)):
                if log_key not in st.session_state.sent_log:
                    # Gọi hàm build_report có kèm ảnh
                    pic_stats = df_team.groupby('PIC').agg( # Đảm bảo pic_stats đã được tính
                        total=('Userstory/Todo', 'count'),
                        done=('State_Clean', lambda x: x.isin(['done', 'cancel', 'dev done']).sum()),
                        doing=('State_Clean', lambda x: x.str.contains('progress').sum()),
                        est_sum=('Estimate Dev', 'sum'),
                        real_sum=('Real', 'sum')
                    ).reset_index()
                    pic_stats['pending'] = pic_stats['total'] - pic_stats['done']
                    pic_stats['percent'] = (pic_stats['done'] / pic_stats['total'] * 100).fillna(0).round(1)
                    
                    auto_content = build_report(pic_stats, over_est_list, is_auto=True)
                    res = send_telegram_msg(auto_content)
                    if res.get("ok"):
                        st.session_state.sent_log.append(log_key)

        # (Phần hiển thị Sidebar và Dashboard giữ nguyên)
        if st.sidebar.button("📤 Gửi báo cáo ngay bây giờ"):
            content = build_report(pic_stats, over_est_list, is_auto=False)
            send_telegram_msg(content)

except Exception as e:
    st.error(f"Lỗi hệ thống: {e}")
