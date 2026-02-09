import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, time, timedelta

# --- 1. HÀM TÍNH GIỜ LÀM VIỆC ---
def calculate_working_hours(start_dt, end_dt):
    if pd.isna(start_dt) or start_dt > end_dt:
        return 0
    total_seconds = 0
    curr = start_dt
    while curr.date() <= end_dt.date():
        if curr.weekday() < 5: 
            morn_s = datetime.combine(curr.date(), time(8, 30))
            morn_e = datetime.combine(curr.date(), time(12, 0))
            aft_s = datetime.combine(curr.date(), time(13, 30))
            aft_e = datetime.combine(curr.date(), time(18, 0))
            s_m, e_m = max(curr, morn_s), min(end_dt, morn_e)
            if s_m < e_m: total_seconds += (e_m - s_m).total_seconds()
            s_a, e_a = max(curr, aft_s), min(end_dt, aft_e)
            if s_a < e_a: total_seconds += (e_a - s_a).total_seconds()
        curr = (curr + timedelta(days=1)).replace(hour=8, minute=30, second=0)
    return total_seconds / 3600

st.set_page_config(page_title="Sprint Dashboard", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1llUlTDfR413oZelu-AoMsC0lEzHqXOkB4SCwc_4zmAo/edit?pli=1&gid=982443592#gid=982443592"

try:
    # Đọc dữ liệu thô để xác định header
    raw_df = conn.read(spreadsheet=URL, header=None, ttl=0)
    header_idx = next((i for i, row in raw_df.iterrows() if "Userstory/Todo" in row.values), None)
            
    if header_idx is not None:
        df = conn.read(spreadsheet=URL, skiprows=header_idx, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]

        # --- XỬ LÝ CỘT START_TIME (Dò tìm thông minh) ---
        # Ưu tiên tìm theo tên, nếu không thấy thì lấy cột thứ 9 (cột I)
        start_col_name = next((c for c in df.columns if "start" in c.lower()), None)
        if not start_col_name and len(df.columns) >= 9:
            start_col_name = df.columns[8] # Cột I thường là cột thứ 9
        
        if start_col_name:
            df['Start_DT'] = pd.to_datetime(df[start_col_name], errors='coerce')
            df['Start_Display'] = df[start_col_name].astype(str).replace(['nan', 'NaT'], '')
        else:
            df['Start_DT'] = pd.NaT
            df['Start_Display'] = ""

        # Chuẩn hóa số liệu
        for col in ['Estimate Dev', 'Real']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        
        df['State_Clean'] = df['State'].fillna('None').str.strip().str.lower()
        valid_pics = ['Tài', 'Dương', 'QA', 'Quân', 'Phú', 'Thịnh', 'Đô', 'Tùng', 'Anim', 'Thắng VFX']
        df_team = df[df['PIC'].isin(valid_pics)].copy()

        # --- LOGIC CẢNH BÁO OVER ESTIMATE ---
        now = datetime.now()
        over_est_list = []
        for _, row in df_team.iterrows():
            if 'progress' in row['State_Clean'] and not pd.isna(row['Start_DT']):
                actual = calculate_working_hours(row['Start_DT'], now)
                est = float(row['Estimate Dev'])
                if est > 0 and actual > est:
                    over_est_list.append({"PIC": row['PIC'], "Task": row['Userstory/Todo'], "Actual": round(actual, 1), "Est": est})

        st.title("🚀 Sprint Workload & Performance")

        # Hiển thị bảng cảnh báo trên App
        if over_est_list:
            st.error("🚨 PHÁT HIỆN TASK VƯỢT ESTIMATE!")
            st.table(pd.DataFrame(over_est_list))

        # --- KHÔI PHỤC TÍNH NĂNG CŨ (STATS) ---
        pic_stats = df_team.groupby('PIC').agg(
            total=('Userstory/Todo', 'count'),
            done=('State_Clean', lambda x: x.isin(['done', 'cancel']).sum()),
            doing=('State_Clean', lambda x: x.str.contains('progress').sum())
        ).reset_index()
        pic_stats['remain'] = pic_stats['total'] - pic_stats['done']
        pic_stats['percent'] = (pic_stats['done'] / pic_stats['total'] * 100).fillna(0).round(1)

        st.subheader("👤 Trạng thái PIC")
        cols = st.columns(5)
        for i, row in pic_stats.iterrows():
            with cols[i % 5]:
                st.markdown(f"### **{row['PIC']}**")
                st.metric("Tiến độ", f"{row['percent']}%")
                st.write(f"✅ Xong: {int(row['done'])} | 🚧 Làm: {int(row['doing'])}")
                st.write(f"⏳ Còn lại: **{int(row['remain'])}** task")
                st.progress(min(row['percent']/100, 1.0))
                st.divider()

        # --- GỬI DISCORD (Gồm cảnh báo) ---
        st.sidebar.subheader("📢 Discord Report")
        webhook_url = st.sidebar.text_input("Webhook URL:", type="password")
        if st.sidebar.button("📤 Gửi báo cáo"):
            if webhook_url:
                msg = "📊 **SPRINT PROGRESS REPORT**\n"
                for _, r in pic_stats.iterrows():
                    msg += f"👤 **{r['PIC']}**: `{r['percent']}%` (Còn {int(r['remain'])} task)\n"
                
                msg += "\n⚠️ **CẢNH BÁO VƯỢT GIỜ:**\n"
                if over_est_list:
                    for item in over_est_list:
                        msg += f"🚩 `{item['PIC']}` làm lố: **{item['Task']}** ({item['Actual']}h/{item['Est']}h)\n"
                else:
                    msg += "✅ Mọi task đều ổn.\n"
                
                requests.post(webhook_url, json={"content": msg})
                st.sidebar.success("Đã gửi!")

        # BIỂU ĐỒ & BẢNG
        st.plotly_chart(px.bar(pic_stats, x='PIC', y=['total', 'done'], barmode='group'), use_container_width=True)
        st.subheader("📋 Chi tiết Task")
        # Sử dụng Start_Display để chắc chắn hiện giá trị chuỗi
        st.dataframe(df_team[['Userstory/Todo', 'State', 'PIC', 'Estimate Dev', 'Start_Display']], use_container_width=True)

    else:
        st.error("Không tìm thấy tiêu đề 'Userstory/Todo'.")
except Exception as e:
    # Fix KeyError bằng cách in lỗi nhưng không sập app
    st.error(f"Lỗi hệ thống: {e}")
