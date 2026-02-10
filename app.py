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

# Danh sách giờ gửi báo cáo tự động (Định dạng HH:MM)
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
        "parse_mode": "Markdown"
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
        msg += f"👤 *{r['PIC']}*\n"
        msg += f"┣ Tiến độ: **{r['percent']}%** \n"
        msg += f"┣ ✅ Đã xong: {int(r['done'])} | 🚧 Đang làm: {int(r['doing'])}\n"
        msg += f"┣ ⏳ *Tồn đọng: {int(r['pending'])} task*\n"
        msg += f"┗ ⏱ Giờ: `{round(r['real_sum'], 1)}h / {round(r['est_sum'], 1)}h`\n"
        msg += "──────────────────\n"
    
    if over_est_list:
        msg += "\n🚨 *CẢNH BÁO VƯỢT GIỜ DỰ KIẾN:*\n"
        for item in over_est_list:
            msg += f"🔥 `{item['PIC']}`: {item['Task']}\n"
            msg += f"    └ Thực tế: **{item['Thực tế']}** (Dự kiến: {item['Dự kiến']})\n"
    return msg

# --- 3. GIAO DIỆN & XỬ LÝ DỮ LIỆU ---
st.set_page_config(page_title="Team 2 Sprint Dashboard", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)
URL_TEAM_2 = "https://docs.google.com/spreadsheets/d/1hentY_r7GNVwJWM3wLT7LsA3PrXQidWnYahkfSwR9Kw/edit?pli=1&gid=982443592#gid=982443592"

try:
    df_raw = conn.read(spreadsheet=URL_TEAM_2, header=None, ttl=0)
    header_idx = next((i for i, row in df_raw.iterrows() if "Userstory/Todo" in row.values), None)
            
    if header_idx is not None:
        df = conn.read(spreadsheet=URL_TEAM_2, skiprows=header_idx, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]

        t_col = next((c for c in df.columns if "start" in c.lower()), None)
        
        for col in ['Estimate Dev', 'Real']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '.').replace('None', '0')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        df['State_Clean'] = df['State'].fillna('None').str.strip().str.lower()
        
        valid_pics = ['Chuân', 'Việt', 'Thắng', 'QA', 'Mai', 'Hải Anh', 'Thuật', 'Hiếu']
        df_team = df[df['PIC'].isin(valid_pics)].copy()

        # Logic lố giờ
        over_est_list = []
        if t_col:
            for _, row in df_team.iterrows():
                if 'progress' in row['State_Clean']:
                    actual_h = get_actual_hours(row[t_col])
                    est_h = float(row['Estimate Dev'])
                    if est_h > 0 and actual_h > est_h:
                        over_est_list.append({
                            "PIC": row['PIC'], "Task": row['Userstory/Todo'], 
                            "Thực tế": f"{round(actual_h * 60)}p", "Dự kiến": f"{round(est_h * 60)}p"
                        })

        # Thống kê PIC
        pic_stats = df_team.groupby('PIC').agg(
            total=('Userstory/Todo', 'count'),
            done=('State_Clean', lambda x: x.isin(['done', 'cancel', 'dev done']).sum()),
            doing=('State_Clean', lambda x: x.str.contains('progress').sum()),
            est_sum=('Estimate Dev', 'sum'),
            real_sum=('Real', 'sum')
        ).reset_index()
        pic_stats['pending'] = pic_stats['total'] - pic_stats['done']
        pic_stats['percent'] = (pic_stats['done'] / pic_stats['total'] * 100).fillna(0).round(1)

        # --- HIỂN THỊ DASHBOARD ---
        st.title("📊 Team 2 Sprint Performance")
        
        if over_est_list:
            st.error(f"🚨 PHÁT HIỆN {len(over_est_list)} TASK LÀM QUÁ DỰ KIẾN!")
            st.table(pd.DataFrame(over_est_list))

        st.subheader("👤 Trạng thái chi tiết PIC")
        m_cols = st.columns(min(len(pic_stats), 5))
        for i, row in pic_stats.iterrows():
            with m_cols[i % 5]:
                st.markdown(f"### **{row['PIC']}**")
                st.metric("Hoàn thành", f"{row['percent']}%")
                st.write(f"✅ Số task đã hoàn thành: {int(row['done'])} | 🚧 Số task đang tiến hành: {int(row['doing'])}")
                st.write(f"⏳ **Số task còn tồn đọng: {int(row['pending'])} task**")
                st.progress(min(row['percent']/100, 1.0))
                st.divider()

        st.plotly_chart(px.bar(pic_stats, x='PIC', y=['est_sum', 'real_sum'], barmode='group'), use_container_width=True)

        # --- XỬ LÝ GỬI TIN NHẮN ---
        st.sidebar.subheader("📢 Telegram Report")
        
        # 1. Nút bấm thủ công
        if st.sidebar.button("📤 Gửi báo cáo ngay bây giờ"):
            content = build_report(pic_stats, over_est_list, is_auto=False)
            res = send_telegram_msg(content)
            if res.get("ok"): st.sidebar.success("Đã gửi thủ công!")
            else: st.sidebar.error(f"Lỗi: {res.get('description')}")

        # 2. Logic tự động gửi theo giờ cố định
        now_time = datetime.now(VN_TZ).strftime("%H:%M")
        if "last_sent_time" not in st.session_state:
            st.session_state.last_sent_time = ""

        if now_time in SCHEDULED_HOURS and st.session_state.last_sent_time != now_time:
            auto_content = build_report(pic_stats, over_est_list, is_auto=True)
            res = send_telegram_msg(auto_content)
            if res.get("ok"):
                st.session_state.last_sent_time = now_time
                st.sidebar.info(f"Đã tự động gửi báo cáo lúc {now_time}")

        # Bảng chi tiết
        st.subheader("📋 Danh sách Task chi tiết")
        display_cols = ['Userstory/Todo', 'State', 'PIC', 'Estimate Dev', 'Real']
        if t_col: display_cols.append(t_col)
        st.dataframe(df_team[display_cols], use_container_width=True)

    else:
        st.error("Không tìm thấy hàng chứa 'Userstory/Todo'.")
except Exception as e:
    st.error(f"Lỗi hệ thống: {e}")
