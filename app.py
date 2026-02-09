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

st.set_page_config(page_title="Sprint Workload Analyzer", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1llUlTDfR413oZelu-AoMsC0lEzHqXOkB4SCwc_4zmAo/edit?pli=1&gid=982443592#gid=982443592"

try:
    # Đọc dữ liệu thô (ttl=0 để làm mới dữ liệu liên tục)
    df_raw = conn.read(spreadsheet=URL, header=None, ttl=0)
    header_idx = next((i for i, row in df_raw.iterrows() if "Userstory/Todo" in row.values), None)
            
    if header_idx is not None:
        df = conn.read(spreadsheet=URL, skiprows=header_idx, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]
        
        # --- TỰ ĐỘNG KHỚP CỘT (Tìm cột chứa chữ "Start") ---
        found_start_col = next((c for c in df.columns if "Start" in c), None)
        if found_start_col:
            df['Start_time_Logic'] = pd.to_datetime(df[found_start_col], errors='coerce')
            df['Start_time_Display'] = df[found_start_col].astype(str).replace(['nan', 'NaT'], '')
        else:
            df['Start_time_Logic'] = pd.NaT
            df['Start_time_Display'] = ""

        # Chuẩn hóa dữ liệu số
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
            if row['State_Clean'] == 'in progress' and not pd.isna(row['Start_time_Logic']):
                actual = calculate_working_hours(row['Start_time_Logic'], now)
                est = float(row['Estimate Dev'])
                if est > 0 and actual > est:
                    over_est_list.append({"PIC": row['PIC'], "Task": row['Userstory/Todo'], "Actual": round(actual, 1), "Est": est})

        st.title("🚀 Sprint Workload & Performance")

        if over_est_list:
            st.warning(f"🚨 Có {len(over_est_list)} task đang vượt quá thời gian Estimate!")
            st.table(pd.DataFrame(over_est_list))

        # --- KHÔI PHỤC THÔNG TIN SỐ TASK (STATS) ---
        pic_stats = df_team.groupby('PIC').agg(
            total_tasks=('Userstory/Todo', 'count'),
            done_tasks=('State_Clean', lambda x: x.isin(['done', 'cancel']).sum()),
            inprogress_tasks=('State_Clean', lambda x: (x == 'in progress').sum()),
            none_tasks=('State_Clean', lambda x: (x == 'none').sum()),
            active_real=('Real', 'sum'),
            total_est=('Estimate Dev', 'sum')
        ).reset_index()
        
        pic_stats['pending_total'] = pic_stats['total_tasks'] - pic_stats['done_tasks']
        pic_stats['Progress_Task'] = (pic_stats['done_tasks'] / pic_stats['total_tasks'] * 100).fillna(0).round(1)

        # --- HIỂN THỊ METRICS CŨ ---
        st.subheader("👤 Trạng thái Task theo PIC")
        cols = st.columns(5)
        for i, row in pic_stats.iterrows():
            with cols[i % 5]:
                st.markdown(f"### **{row['PIC']}**")
                st.metric("Tiến độ", f"{row['Progress_Task']}%")
                st.write(f"✅ Xong: **{int(row['done_tasks'])}** | 🚧 Làm: **{int(row['inprogress_tasks'])}**")
                st.write(f"⏳ Chưa làm: **{int(row['none_tasks'])}**")
                st.write(f"🚩 Còn lại: **{int(row['pending_total'])}** task")
                st.progress(min(row['Progress_Task']/100, 1.0))
                st.divider()

        # --- BIỂU ĐỒ & BẢNG CHI TIẾT ---
        st.plotly_chart(px.bar(pic_stats, x='PIC', y=['active_real', 'total_est'], barmode='group'), use_container_width=True)
        
        st.subheader("📋 Chi tiết danh sách Task")
        # Hiển thị Start_time_Display để chắc chắn nhìn thấy giá trị
        display_cols = ['Userstory/Todo', 'State', 'PIC', 'Estimate Dev', 'Real', 'Start_time_Display']
        st.dataframe(df_team[display_cols], use_container_width=True)

        # --- GỬI DISCORD ---
        st.sidebar.subheader("📢 Báo cáo Discord")
        webhook_url = st.sidebar.text_input("Webhook URL:", type="password")
        
        if st.sidebar.button("📤 Gửi báo cáo chi tiết"):
            if webhook_url:
                # 1. Tạo phần tiêu đề và báo cáo tiến độ chung
                msg = "📊 **SPRINT STATUS REPORT** 📊\n"
                msg += "━━━━━━━━━━━━━━━━━━━━━\n"
                for _, r in pic_stats.iterrows():
                    msg += f"👤 **{r['PIC']}** | `{r['Progress_Task']}%` Done\n"
                    msg += f"• Còn lại: `{int(r['pending_total'])}` task\n"
                
                # 2. Tự động kiểm tra và thêm phần Cảnh báo nếu có task vượt Estimate
                if over_est_list:
                    msg += "\n🚨 **CẢNH BÁO: TASK VƯỢT ESTIMATE**\n"
                    msg += "━━━━━━━━━━━━━━━━━━━━━\n"
                    for item in over_est_list:
                        # Liệt kê cụ thể: Tên PIC - Tên Task (Số giờ thực tế / Số giờ Estimate)
                        msg += f"🔥 **{item['PIC']}**: {item['Task']}\n"
                        msg += f"   ➔ Thực tế: `{item['Actual']}h` (Estimate: `{item['Est']}h`)\n"
                
                # Gửi dữ liệu đi
                response = requests.post(webhook_url, json={"content": msg})
                
                if response.status_code in [200, 204]:
                    st.sidebar.success("✅ Đã gửi báo cáo kèm cảnh báo!")
                else:
                    st.sidebar.error(f"❌ Lỗi gửi: {response.status_code}")
            else:
                st.sidebar.warning("Vui lòng nhập Webhook URL!")

    else:
        st.error("Không tìm thấy hàng tiêu đề 'Userstory/Todo'.")
except Exception as e:
    st.error(f"Lỗi hệ thống: {e}")
