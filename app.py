import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timezone, timedelta

# --- 1. CỐ ĐỊNH MÚI GIỜ VIỆT NAM ---
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

def send_telegram_msg(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    return requests.post(url, json=payload)

st.set_page_config(page_title="Team 2 Sprint Dashboard", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- THAY LINK GOOGLE SHEET TEAM 2 TẠI ĐÂY ---
URL_TEAM_2 = "https://docs.google.com/spreadsheets/d/1hentY_r7GNVwJWM3wLT7LsA3PrXQidWnYahkfSwR9Kw/edit?pli=1&gid=982443592#gid=982443592"

try:
    df_raw = conn.read(spreadsheet=URL_TEAM_2, header=None, ttl=0)
    header_idx = next((i for i, row in df_raw.iterrows() if "Userstory/Todo" in row.values), None)
            
    if header_idx is not None:
        df = conn.read(spreadsheet=URL_TEAM_2, skiprows=header_idx, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]

        # Tự động tìm cột Start dựa trên từ khóa để tránh lỗi 'not in index'
        t_col = next((c for c in df.columns if "start" in c.lower()), None)
        
        # Chuẩn hóa dữ liệu số
        for col in ['Estimate Dev', 'Real']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '.').replace('None', '0')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        df['State_Clean'] = df['State'].fillna('None').str.strip().str.lower()
        
        # --- CẬP NHẬT DANH SÁCH PIC CHO TEAM 2 ---
        valid_pics = ['Chuân', 'Việt', 'Thắng'] # Thay bằng tên PIC thực tế của Team 2
        df_team = df[df['PIC'].isin(valid_pics)].copy()

        # 2. LOGIC CẢNH BÁO LỐ GIỜ
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

        st.title("📊 Team 2 Sprint Performance")

        # Hiển thị Cảnh báo Đỏ (UI quan trọng)
        if over_est_list:
            st.error(f"🚨 PHÁT HIỆN {len(over_est_list)} TASK LÀM QUÁ DỰ KIẾN!")
            st.table(pd.DataFrame(over_est_list))

        # --- 3. KHÔI PHỤC TOÀN BỘ GIAO DIỆN METRICS ---
        pic_stats = df_team.groupby('PIC').agg(
