import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timezone, timedelta

# --- 1. CÀI ĐẶT MÚI GIỜ VIỆT NAM ---
VN_TZ = timezone(timedelta(hours=7))

def get_actual_hours(start_val):
    if pd.isna(start_val) or str(start_val).strip().lower() in ['none', '', 'nat']:
        return 0
    try:
        start_dt = pd.to_datetime(start_val)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=VN_TZ)
        now_vn = datetime.now(VN_TZ)
        diff = now_vn - start_dt
        return diff.total_seconds() / 3600 
    except:
        return 0

# --- HÀM GỬI TELEGRAM ---
def send_telegram_msg(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    return requests.post(url, json=payload)

st.set_page_config(page_title="Sprint Dashboard Team 2", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- THAY LINK GOOGLE SHEETS CỦA TEAM MỚI TẠI ĐÂY ---
URL_TEAM_2 = "https://docs.google.com/spreadsheets/d/1hentY_r7GNVwJWM3wLT7LsA3PrXQidWnYahkfSwR9Kw/edit?pli=1&gid=982443592#gid=982443592"

try:
    df_raw = conn.read(spreadsheet=URL_TEAM_2, header=None, ttl=0)
    header_idx = next((i for i, row in df_raw.iterrows() if "Userstory/Todo" in row.values), None)
            
    if header_idx is not None:
        df = conn.read(spreadsheet=URL_TEAM_2, skiprows=header_idx, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]

        # Chuẩn hóa số
        for col in ['Estimate Dev', 'Real']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '.').replace('None', '0')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        t_col = next((c for c in df.columns if "start" in c.lower()), None)
        df['State_Clean'] = df['State'].fillna('None').str.strip().str.lower()
        
        # Danh sách PIC của team mới
        valid_pics = ['Chuân', 'Việt', 'Thắng'] # Thay tên thành viên team mới
        df_team = df[df['PIC'].isin(valid_pics)].copy()

        # Logic cảnh báo
        over_est_list = []
        if t_col:
            for _, row in df_team.iterrows():
                if 'progress' in row['State_Clean']:
                    actual_h = get_actual_hours(row[t_col])
                    est_h = float(row['Estimate Dev'])
                    if est_h > 0 and actual_h > est_h:
                        over_est_list.append({
                            "PIC": row['PIC'], "Task": row['Userstory/Todo'], 
                            "Actual": f"{round(actual_h * 60)}p", "Est": f"{round(est_h * 60)}p"
                        })

        st.title("🚀 Team 2 - Sprint Dashboard")

        if over_est_list:
            st.error(f"🚨 PHÁT HIỆN {len(over_est_list)} TASK VƯỢT GIỜ!")
            st.table(pd.DataFrame(over_est_list))

        # Thống kê tồn đọng
        pic_stats = df_team.groupby('PIC').agg(
            total=('Userstory/Todo', 'count'),
            done=('State_Clean', lambda x: x.isin(['done', 'cancel']).sum())
        ).reset_index()
        pic_stats['pending'] = pic_stats['total'] - pic_stats['done']

        st.subheader("👤 Trạng thái Team")
        cols = st.columns(len(valid_pics))
        for i, row in pic_stats.iterrows():
            with cols[i]:
                st.metric(row['PIC'], f"Tồn: {int(row['pending'])} task")

        # --- CẤU HÌNH GỬI TELEGRAM TRÊN SIDEBAR ---
        st.sidebar.subheader("📢 Telegram Bot Settings")
        tg_token = st.sidebar.text_input("Telegram Bot Token:", type="password")
        tg_chat_id = st.sidebar.text_input("Chat ID (Group):")
        
        if st.sidebar.button("📤 Gửi báo cáo Telegram"):
            if tg_token and tg_chat_id:
                msg = "📊 *SPRINT REPORT TEAM 2*\n\n"
                for _, r in pic_stats.iterrows():
                    msg += f"👤 *{r['PIC']}*: Còn `{int(r['pending'])}` task tồn đọng\n"
                
                if over_est_list:
                    msg += "\n🚨 *CẢNH BÁO LỐ GIỜ:*\n"
                    for item in over_est_list:
                        msg += f"🚩 `{item['PIC']}`: {item['Task']} ({item['Actual']}/{item['Est']})\n"
                
                res = send_telegram_msg(tg_token, tg_chat_id, msg)
                if res.status_code == 200:
                    st.sidebar.success("Đã gửi Telegram!")
                else:
                    st.sidebar.error("Lỗi gửi tin nhắn!")

        st.dataframe(df_team, use_container_width=True)

    else:
        st.error("Không tìm thấy tiêu đề Userstory/Todo.")
except Exception as e:
    st.error(f"Lỗi: {e}")
