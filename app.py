import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
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
    df_raw = conn.read(spreadsheet=URL, header=None, ttl=0)
    header_idx = next((i for i, row in df_raw.iterrows() if "Userstory/Todo" in row.values), None)
            
    if header_idx is not None:
        df = conn.read(spreadsheet=URL, skiprows=header_idx, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]

        # --- FIX LỖI DẤU PHẨY (,) TRONG ESTIMATE ---
        # Chuyển đổi dấu phẩy thành dấu chấm để Python tính toán được
        for col in ['Estimate Dev', 'Real']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '.')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Xử lý Start_time
        start_col = next((c for c in df.columns if "start" in c.lower()), None)
        if start_col:
            df['Start_DT'] = pd.to_datetime(df[start_col], errors='coerce')
            df['Start_Display'] = df[start_col].astype(str).replace(['nan', 'NaT'], '')
        else:
            df['Start_DT'] = pd.NaT
            df['Start_Display'] = ""

        df['State_Clean'] = df['State'].fillna('None').str.strip().str.lower()
        valid_pics = ['Tài', 'Dương', 'QA', 'Quân', 'Phú', 'Thịnh', 'Đô', 'Tùng', 'Anim', 'Thắng VFX']
        df_team = df[df['PIC'].isin(valid_pics)].copy()

        # --- LOGIC CẢNH BÁO ---
        now = datetime.now()
        over_est_list = []
        for _, row in df_team.iterrows():
            if 'progress' in row['State_Clean'] and not pd.isna(row['Start_DT']):
                actual = calculate_working_hours(row['Start_DT'], now)
                est = float(row['Estimate Dev'])
                if est > 0 and actual > est:
                    over_est_list.append({
                        "PIC": row['PIC'], 
                        "Task": row['Userstory/Todo'], 
                        "Actual": round(actual, 1), 
                        "Est": est
                    })

        st.title("🚀 Sprint Workload & Alert")

        # Cảnh báo trên giao diện
        if over_est_list:
            st.error(f"🚨 PHÁT HIỆN {len(over_est_list)} TASK VƯỢT GIỜ!")
            st.table(pd.DataFrame(over_est_list))
        else:
            st.success("✅ Mọi task đều đang trong tiến độ.")

        # Thống kê PIC
        pic_stats = df_team.groupby('PIC').agg(
            total=('Userstory/Todo', 'count'),
            done=('State_Clean', lambda x: x.isin(['done', 'cancel']).sum()),
            doing=('State_Clean', lambda x: x.str.contains('progress').sum())
        ).reset_index()
        pic_stats['percent'] = (pic_stats['done'] / pic_stats['total'] * 100).fillna(0).round(1)

        # Gửi Discord
        st.sidebar.subheader("📢 Discord Report")
        webhook_url = st.sidebar.text_input("Webhook URL:", type="password")
        if st.sidebar.button("📤 Gửi báo cáo"):
            if webhook_url:
                msg = "📊 **SPRINT REPORT**\n"
                for _, r in pic_stats.iterrows():
                    msg += f"👤 **{r['PIC']}**: `{r['percent']}%` xong\n"
                
                msg += "\n⚠️ **TRẠNG THÁI CẢNH BÁO:**\n"
                if over_est_list:
                    for item in over_est_list:
                        msg += f"🚩 `{item['PIC']}` lố: **{item['Task']}** (`{item['Actual']}h`/{item['Est']}h)\n"
                else:
                    msg += "✅ Không có task nào vượt estimate.\n"
                
                requests.post(webhook_url, json={"content": msg})
                st.sidebar.success("Đã gửi báo cáo!")

        st.subheader("📋 Chi tiết danh sách")
        st.dataframe(df_team[['Userstory/Todo', 'State', 'PIC', 'Estimate Dev', 'Start_DT']], use_container_width=True)

    else:
        st.error("Không tìm thấy tiêu đề 'Userstory/Todo'.")
except Exception as e:
    st.error(f"Lỗi hệ thống: {e}")
