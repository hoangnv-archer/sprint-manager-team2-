import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import requests

from datetime import datetime, time, timedelta

def calculate_working_hours(start_dt, end_dt):
    """Tính tổng giờ làm việc thực tế (8h30-12h, 13h30-18h), loại bỏ cuối tuần và nghỉ trưa"""
    if pd.isna(start_dt) or start_dt > end_dt:
        return 0
    total_seconds = 0
    curr = start_dt
    while curr.date() <= end_dt.date():
        if curr.weekday() < 5: # Thứ 2 đến thứ 6
            morn_s = datetime.combine(curr.date(), time(8, 30))
            morn_e = datetime.combine(curr.date(), time(12, 0))
            aft_s = datetime.combine(curr.date(), time(13, 30))
            aft_e = datetime.combine(curr.date(), time(18, 0))
            # Ca sáng
            s = max(curr, morn_s)
            e = min(end_dt, morn_e)
            if s < e: total_seconds += (e - s).total_seconds()
            # Ca chiều
            s = max(curr, aft_s)
            e = min(end_dt, aft_e)
            if s < e: total_seconds += (e - s).total_seconds()
        curr = (curr + timedelta(days=1)).replace(hour=8, minute=30, second=0)
        if curr > end_dt: break
    return total_seconds / 3600
    
st.set_page_config(page_title="Sprint Workload Analyzer", layout="wide")

# Khởi tạo kết nối Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1llUlTDfR413oZelu-AoMsC0lEzHqXOkB4SCwc_4zmAo/edit?pli=1&gid=982443592#gid=982443592"

try:
    # 1. Đọc dữ liệu
    raw_df = conn.read(spreadsheet=URL, header=None)
    header_idx = next((i for i, row in raw_df.iterrows() if "Userstory/Todo" in row.values), None)
            
    if header_idx is not None:
        df = conn.read(spreadsheet=URL, skiprows=header_idx)
        df.columns = [str(c).strip() for c in df.columns]
        
        # 2. Xử lý định dạng số
        for col in ['Estimate Dev', 'Real']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        # Chuyển đổi cột Start_time sang datetime
        if 'Start_time' in df.columns:
            df['Start_time'] = pd.to_datetime(df['Start_time'], errors='coerce')

        # 2.1 Tính toán cảnh báo vượt Estimate
        now = datetime.now()
        over_est_list = []
        
        for idx, row in df.iterrows():
            if row['State_Clean'] == 'in progress' and not pd.isna(row['Start_time']):
                actual_h = calculate_working_hours(row['Start_time'], now)
                est_h = float(row['Estimate Dev'])
                if est_h > 0 and actual_h > est_h:
                    over_est_list.append({
                        "PIC": row['PIC'],
                        "Task": row['Userstory/Todo'],
                        "Actual": round(actual_h, 1),
                        "Est": est_h
                    })
        
        # 3. Chuẩn hóa trạng thái (State)
        df['State_Clean'] = df['State'].fillna('None').replace('', 'None').str.strip().str.lower()
        
        # Danh sách Team PIC
        valid_pics = ['Tài', 'Dương', 'QA', 'Quân', 'Phú', 'Thịnh', 'Đô', 'Tùng', 'Anim', 'Thắng VFX']
        df_team = df[df['PIC'].isin(valid_pics)].copy()

        st.title("🚀 Sprint Workload & Performance")

        # --- TÍNH TOÁN (Cancel = Done) ---
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

        if over_est_list:
            st.warning(f"🚨 Có {len(over_est_list)} task đang vượt quá thời gian Estimate!")
            with st.expander("Xem chi tiết các task vượt Estimate"):
                st.table(pd.DataFrame(over_est_list))
        # --- HIỂN THỊ METRICS ---
        st.subheader("👤 Trạng thái Task theo PIC")
        cols = st.columns(5)
        for i, row in pic_stats.iterrows():
            with cols[i % 5]:
                st.markdown(f"### **{row['PIC']}**")
                st.metric("Tiến độ", f"{row['Progress_Task']}%")
                st.write(f"✅ Hoàn thành: **{int(row['done_tasks'])}** (gồm Cancel)")
                st.write(f"🚧 In Progress: **{int(row['inprogress_tasks'])}**")
                st.write(f"⏳ Chưa làm: **{int(row['none_tasks'])}**")
                st.progress(min(row['Progress_Task']/100, 1.0))
                st.divider()

        # --- BIỂU ĐỒ ---
        st.subheader("📊 Biểu đồ thời gian làm việc")
        fig_df = pic_stats[['PIC', 'active_real', 'total_est']].copy()
        fig_df.columns = ['PIC', 'Thực tế (Real)', 'Dự tính (Est)']
        fig = px.bar(fig_df.melt(id_vars='PIC'), x='PIC', y='value', color='variable', barmode='group', text_auto='.1f')
        st.plotly_chart(fig, use_container_width=True)

        # --- GỬI DISCORD ---
        st.sidebar.subheader("📢 Báo cáo Discord")
        webhook_url = st.sidebar.text_input("Webhook URL:", type="password")
        if st.sidebar.button("📤 Gửi báo cáo chi tiết"):
            if webhook_url:
                msg = "📊 **SPRINT STATUS REPORT** 📊\n"
                msg += "━━━━━━━━━━━━━━━━━━━━━\n"
                for _, r in pic_stats.iterrows():
                    msg += f"👤 **{r['PIC']}** | `{r['Progress_Task']}%` Done\n"
                    msg += f"• Xong (+Cancel): `{int(r['done_tasks'])}` task\n"
                    msg += f"• Đang làm: `{int(r['inprogress_tasks'])}` | Chưa làm: `{int(r['none_tasks'])}` \n"
                    msg += "─────────────────────\n"
                
                response = requests.post(webhook_url, json={"content": msg})
                if response.status_code in [200, 204]:
                    st.sidebar.success("Đã gửi báo cáo!")
                else:
                    st.sidebar.error(f"Lỗi gửi Discord: {response.status_code}")
                if over_est_list:
                    msg += "\n🚨 **CẢNH BÁO VƯỢT ESTIMATE**\n"
                    for item in over_est_list:
                    msg += f"• {item['PIC']}: {item['Task']} (`{item['Actual']}h`/{item['Est']}h)\n"

        st.subheader("📋 Chi tiết danh sách Task")
        st.dataframe(df_team[['Userstory/Todo', 'State', 'PIC', 'Estimate Dev', 'Real']], use_container_width=True)
              
    else:
        st.error("Không tìm thấy hàng tiêu đề 'Userstory/Todo'.")

except Exception as e:
    st.error(f"Lỗi hệ thống: {e}")
