import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, time, timedelta

def calculate_working_hours(start_dt, end_dt):
    if pd.isna(start_dt) or start_dt > end_dt:
        return 0
    total_seconds = 0
    curr = start_dt
    while curr.date() <= end_dt.date():
        if curr.weekday() < 5: 
            morn_s, morn_e = datetime.combine(curr.date(), time(8, 30)), datetime.combine(curr.date(), time(12, 0))
            aft_s, aft_e = datetime.combine(curr.date(), time(13, 30)), datetime.combine(curr.date(), time(18, 0))
            s_m, e_m = max(curr, morn_s), min(end_dt, morn_e)
            if s_m < e_m: total_seconds += (e_m - s_m).total_seconds()
            s_a, e_a = max(curr, aft_s), min(end_dt, aft_e)
            if s_a < e_a: total_seconds += (e_a - s_a).total_seconds()
        curr = (curr + timedelta(days=1)).replace(hour=8, minute=30, second=0)
    return total_seconds / 3600

st.set_page_config(page_title="Sprint Workload Analyzer", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1llUlTDfR413oZelu-AoMsC0lEzHqXOkB4SCwc_4zmAo/edit?pli=1&gid=982443592#gid=982443592"

try:
    # Đọc dữ liệu với ttl=0 để ép tải mới nhất
    df_raw = conn.read(spreadsheet=URL, header=None, ttl=0)
    header_idx = next((i for i, row in df_raw.iterrows() if "Userstory/Todo" in row.values), None)
            
    if header_idx is not None:
        df = conn.read(spreadsheet=URL, skiprows=header_idx, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]
        
        # --- BƯỚC QUAN TRỌNG: XỬ LÝ RIÊNG START_TIME ---
        if 'Start_time' in df.columns:
            # Chuyển về dạng chuỗi trước để xem giá trị thô là gì
            df['Start_time_Display'] = df['Start_time'].astype(str).replace('nan', '').replace('NaT', '')
            # Ép kiểu datetime cho logic tính toán cảnh báo
            df['Start_time_DT'] = pd.to_datetime(df['Start_time'], errors='coerce')
        else:
            df['Start_time_Display'] = ''
            df['Start_time_DT'] = pd.NaT

        # Định dạng số
        for col in ['Estimate Dev', 'Real']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        
        df['State_Clean'] = df['State'].fillna('None').str.strip().str.lower()
        valid_pics = ['Tài', 'Dương', 'QA', 'Quân', 'Phú', 'Thịnh', 'Đô', 'Tùng', 'Anim', 'Thắng VFX']
        df_team = df[df['PIC'].isin(valid_pics)].copy()

        # LOGIC CẢNH BÁO
        now = datetime.now()
        over_est_list = []
        for _, row in df_team.iterrows():
            if row['State_Clean'] == 'in progress' and not pd.isna(row['Start_time_DT']):
                actual = calculate_working_hours(row['Start_time_DT'], now)
                est = float(row['Estimate Dev'])
                if est > 0 and actual > est:
                    over_est_list.append({"PIC": row['PIC'], "Task": row['Userstory/Todo'], "Actual": round(actual, 1), "Est": est})

        st.title("🚀 Sprint Workload & Performance")

        if over_est_list:
            st.warning(f"🚨 Có {len(over_est_list)} task đang vượt quá thời gian Estimate!")
            st.table(pd.DataFrame(over_est_list))

        # --- HIỂN THỊ STATS ---
        pic_stats = df_team.groupby('PIC').agg(
            total_tasks=('Userstory/Todo', 'count'),
            done_tasks=('State_Clean', lambda x: x.isin(['done', 'cancel']).sum())
        ).reset_index()
        pic_stats['Progress_Task'] = (pic_stats['done_tasks'] / pic_stats['total_tasks'] * 100).fillna(0).round(1)

        st.subheader("👤 Trạng thái Task theo PIC")
        cols = st.columns(5)
        for i, row in pic_stats.iterrows():
            with cols[i % 5]:
                st.markdown(f"### **{row['PIC']}**")
                st.metric("Tiến độ", f"{row['Progress_Task']}%")
                st.progress(min(row['Progress_Task']/100, 1.0))

        # --- BẢNG CHI TIẾT (DÙNG CỘT DISPLAY ĐỂ HIỆN GIÁ TRỊ) ---
        st.subheader("📋 Chi tiết danh sách Task")
        # Thay Start_time bằng Start_time_Display để chắc chắn hiện chữ
        st.dataframe(df_team[['Userstory/Todo', 'State', 'PIC', 'Estimate Dev', 'Real', 'Start_time_Display']], use_container_width=True)

    else:
        st.error("Không tìm thấy hàng tiêu đề 'Userstory/Todo'.")
except Exception as e:
    st.error(f"Lỗi hệ thống: {e}")
