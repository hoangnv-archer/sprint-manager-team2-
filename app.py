import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import requests
from datetime import datetime, time, timedelta

# --- HÀM TÍNH GIỜ LÀM VIỆC ---
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

st.set_page_config(page_title="Sprint Workload Analyzer", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1llUlTDfR413oZelu-AoMsC0lEzHqXOkB4SCwc_4zmAo/edit?pli=1&gid=982443592#gid=982443592"

try:
    # Đọc dữ liệu thô
    df_raw = conn.read(spreadsheet=URL, header=None, ttl=0)
    header_idx = next((i for i, row in df_raw.iterrows() if "Userstory/Todo" in row.values), None)
            
    if header_idx is not None:
        df = conn.read(spreadsheet=URL, skiprows=header_idx, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]
        
        # --- FIX LỖI 'Start_time' ---
        # Tự động tìm cột có chữ "Start" không phân biệt hoa thường
        actual_start_col = next((c for c in df.columns if "start" in c.lower()), None)
        
        if actual_start_col:
            df['Start_DT'] = pd.to_datetime(df[actual_start_col], errors='coerce')
        else:
            # Nếu không tìm thấy, tạo cột trống để tránh sập App
            df['Start_DT'] = pd.NaT
            st.error("⚠️ Không tìm thấy cột 'Start_time' trên Google Sheets. Vui lòng kiểm tra lại tiêu đề cột I.")

        # Chuẩn hóa dữ liệu
        df['Est_Num'] = pd.to_numeric(df['Estimate Dev'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        df['State_Clean'] = df['State'].fillna('None').str.strip().str.lower()
        
        valid_pics = ['Tài', 'Dương', 'QA', 'Quân', 'Phú', 'Thịnh', 'Đô', 'Tùng', 'Anim', 'Thắng VFX']
        df_team = df[df['PIC'].isin(valid_pics)].copy()

        # --- LOGIC CẢNH BÁO ---
        now = datetime.now()
        over_est_list = []
        for _, row in df_team.iterrows():
            if 'progress' in row['State_Clean'] and not pd.isna(row['Start_DT']):
                actual_h = calculate_working_hours(row['Start_DT'], now)
                estimate_h = float(row['Est_Num'])
                if estimate_h > 0 and actual_h > estimate_h:
                    over_est_list.append({
                        "PIC": row['PIC'], "Task": row['Userstory/Todo'], 
                        "Actual": round(actual_h, 1), "Est": estimate_h
                    })

        st.title("🚀 Sprint Performance & Alert")

        # Hiển thị bảng cảnh báo trên App
        if over_est_list:
            st.error(f"🚨 PHÁT HIỆN {len(over_est_list)} TASK VƯỢT ESTIMATE!")
            st.table(pd.DataFrame(over_est_list))

        # Thống kê tiến độ
        pic_stats = df_team.groupby('PIC').agg(
            total=('Userstory/Todo', 'count'),
            done=('State_Clean', lambda x: x.isin(['done', 'cancel']).sum())
        ).reset_index()
        pic_stats['percent'] = (pic_stats['done'] / pic_stats['total'] * 100).round(1)

        # --- GỬI DISCORD (Gồm logic Cảnh báo) ---
        st.sidebar.subheader("📢 Discord Settings")
        webhook_url = st.sidebar.text_input("Webhook URL:", type="password")
        
        if st.sidebar.button("📤 Gửi báo cáo & Cảnh báo"):
            if webhook_url:
                msg = "📊 **BÁO CÁO TIẾN ĐỘ SPRINT**\n"
                for _, r in pic_stats.iterrows():
                    msg += f"👤 **{r['PIC']}**: `{r['percent']}%` hoàn thành\n"
                
                # CHÈN PHẦN CẢNH BÁO VÀO TIN NHẮN DISCORD
                msg += "\n⚠️ **CẢNH BÁO VƯỢT GIỜ:**\n"
                if over_est_list:
                    for item in over_est_list:
                        msg += f"🔥 `{item['PIC']}`: {item['Task']} (Thực tế: `{item['Actual']}h` / Dự kiến: `{item['Est']}h`)\n"
                else:
                    msg += "✅ Hiện tại không có task nào vượt giờ.\n"
                
                res = requests.post(webhook_url, json={"content": msg})
                if res.status_code < 300:
                    st.sidebar.success("Đã gửi báo cáo lên Discord!")
                else:
                    st.sidebar.error(f"Lỗi Discord: {res.status_code}")

        st.subheader("📋 Bảng chi tiết")
        st.dataframe(df_team[['Userstory/Todo', 'State', 'PIC', 'Estimate Dev', 'Start_DT']], use_container_width=True)

    else:
        st.error("Lỗi: Không tìm thấy hàng chứa 'Userstory/Todo'.")
except Exception as e:
    # In ra lỗi cụ thể để debug
    st.error(f"Lỗi phát sinh: {e}")
