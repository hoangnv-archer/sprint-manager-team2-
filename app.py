import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import requests
from datetime import datetime, time, timedelta

# --- 1. HÀM TÍNH GIỜ LÀM VIỆC CHUẨN ---
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

st.set_page_config(page_title="Sprint Analyzer PRO", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1llUlTDfR413oZelu-AoMsC0lEzHqXOkB4SCwc_4zmAo/edit?pli=1&gid=982443592#gid=982443592"

try:
    df_raw = conn.read(spreadsheet=URL, header=None, ttl=0)
    header_idx = next((i for i, row in df_raw.iterrows() if "Userstory/Todo" in row.values), None)
            
    if header_idx is not None:
        df = conn.read(spreadsheet=URL, skiprows=header_idx, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]
        
        # --- CHUẨN HÓA DỮ LIỆU ---
        df['Start_DT'] = pd.to_datetime(df['Start_time'], errors='coerce')
        df['Est_Num'] = pd.to_numeric(df['Estimate Dev'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        df['State_Clean'] = df['State'].fillna('None').str.strip().str.lower()
        
        valid_pics = ['Tài', 'Dương', 'QA', 'Quân', 'Phú', 'Thịnh', 'Đô', 'Tùng', 'Anim', 'Thắng VFX']
        df_team = df[df['PIC'].isin(valid_pics)].copy()

        # --- LOGIC CẢNH BÁO (KIỂM TRA TỪNG DÒNG) ---
        now = datetime.now()
        over_est_list = []
        for _, row in df_team.iterrows():
            # Điều kiện: Đang làm (in progress) VÀ có giờ bắt đầu VÀ estimate > 0
            if 'in progress' in row['State_Clean'] and not pd.isna(row['Start_DT']):
                actual_h = calculate_working_hours(row['Start_DT'], now)
                estimate_h = float(row['Est_Num'])
                
                if actual_h > estimate_h and estimate_h > 0:
                    over_est_list.append({
                        "PIC": row['PIC'],
                        "Task": row['Userstory/Todo'],
                        "Actual": round(actual_h, 1),
                        "Est": estimate_h
                    })

        st.title("🚀 Sprint Workload & Discord Alert")

        # 1. Hiển thị bảng cảnh báo ngay đầu App để kiểm chứng
        if over_est_list:
            st.error("🚨 PHÁT HIỆN TASK VƯỢT ESTIMATE!")
            st.table(pd.DataFrame(over_est_list))
        else:
            st.info("✅ Hiện tại không có task nào vượt Estimate.")

        # 2. Thống kê số lượng task
        pic_stats = df_team.groupby('PIC').agg(
            total=('Userstory/Todo', 'count'),
            done=('State_Clean', lambda x: x.isin(['done', 'cancel']).sum()),
            doing=('State_Clean', lambda x: x.str.contains('progress').sum())
        ).reset_index()
        pic_stats['remain'] = pic_stats['total'] - pic_stats['done']
        pic_stats['percent'] = (pic_stats['done'] / pic_stats['total'] * 100).round(1)

        # Hiển thị Metrics
        cols = st.columns(5)
        for i, row in pic_stats.iterrows():
            with cols[i % 5]:
                st.metric(row['PIC'], f"{row['percent']}%", f"Còn {int(row['remain'])} task")

        # --- 3. GỬI DISCORD (PHẦN QUAN TRỌNG NHẤT) ---
        st.sidebar.subheader("📢 Discord Webhook")
        webhook_url = st.sidebar.text_input("Dán Webhook vào đây:", type="password")
        
        if st.sidebar.button("📤 GỬI BÁO CÁO & CẢNH BÁO"):
            if webhook_url:
                # Tạo nội dung báo cáo
                msg = "📊 **BÁO CÁO TIẾN ĐỘ SPRINT**\n"
                for _, r in pic_stats.iterrows():
                    msg += f"👤 **{r['PIC']}**: `{r['percent']}%` (Xong {int(r['done'])}/{int(r['total'])})\n"
                
                # CHÈN CẢNH BÁO VÀO GIỮA TIN NHẮN
                msg += "\n⚠️ **TRẠNG THÁI CẢNH BÁO:**\n"
                if over_est_list:
                    for item in over_est_list:
                        msg += f"🚩 `{item['PIC']}` làm lố: **{item['Task']}**\n"
                        msg += f"   (Đã làm `{item['Actual']}h` / Dự kiến `{item['Est']}h`)\n"
                else:
                    msg += "✅ Mọi task đều trong tầm kiểm soát.\n"
                
                # Gửi đi
                res = requests.post(webhook_url, json={"content": msg})
                if res.status_code in [200, 204]:
                    st.sidebar.success("Đã gửi báo cáo kèm cảnh báo!")
                else:
                    st.sidebar.error(f"Lỗi Discord: {res.status_code}")

        st.subheader("📋 Chi tiết dữ liệu")
        st.dataframe(df_team[['Userstory/Todo', 'State', 'PIC', 'Estimate Dev', 'Start_DT']], use_container_width=True)

    else:
        st.error("Không tìm thấy tiêu đề 'Userstory/Todo' trên Sheet.")
except Exception as e:
    st.error(f"Lỗi phát sinh: {e}")
