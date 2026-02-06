import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import requests

st.set_page_config(page_title="Sprint Workload Analyzer", layout="wide")

# Khởi tạo kết nối Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1llUlTDfR413oZelu-AoMsC0lEzHqXOkB4SCwc_4zmAo/edit?pli=1&gid=982443592#gid=982443592"

try:
    # 1. Đọc dữ liệu và xác định hàng tiêu đề
    raw_df = conn.read(spreadsheet=URL, header=None)
    header_idx = next((i for i, row in raw_df.iterrows() if "Userstory/Todo" in row.values), None)
            
    if header_idx is not None:
        df = conn.read(spreadsheet=URL, skiprows=header_idx)
        df.columns = [str(c).strip() for c in df.columns]
        
        # 2. Xử lý định dạng số
        for col in ['Estimate Dev', 'Real']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        
        # 3. Chuẩn hóa trạng thái (State)
        df['State_Clean'] = df['State'].fillna('None').replace('', 'None').str.strip().str.lower()
        
        # Danh sách Team PIC
        valid_pics = ['Tài', 'Dương', 'QA', 'Quân', 'Phú', 'Thịnh', 'Đô', 'Tùng', 'Anim', 'Thắng VFX']
        df_team = df[df['PIC'].isin(valid_pics)].copy()

        st.title("🚀 Sprint Workload & Performance")

        # --- LOGIC TÍNH TOÁN MỚI (Cancel = Done) ---
        # Done_List bao gồm cả 'done' và 'cancel'
        pic_stats = df_team.groupby('PIC').agg(
            total_tasks=('Userstory/Todo', 'count'),
            # Đếm task là done hoặc cancel
            done_tasks=('State_Clean', lambda x: x.isin(['done', 'cancel']).sum()),
            inprogress_tasks=('State_Clean', lambda x: (x == 'in progress').sum()),
            none_tasks=('State_Clean', lambda x: (x == 'none').sum()),
            active_real=('Real', 'sum'),
            total_est=('Estimate Dev', 'sum')
        ).reset_index()
        
        pic_stats['pending_total'] = pic_stats['total_tasks'] - pic_stats['done_tasks']
        pic_stats['Progress_Task'] = (pic_stats['done_tasks'] / pic_stats['total_tasks'] * 100).fillna(0).round(1)

        # --- HIỂN THỊ TRÊN TOOL ---
        st.subheader("👤 Trạng thái Task theo PIC (Cancel = Done)")
        cols = st.columns(5)
        for i, row in pic_stats.iterrows():
            with cols[i % 5]:
                st.markdown(f"### **{row['PIC']}**")
                st.metric("Tiến độ", f"{row['Progress_Task']}%")
                st.write(f"✅ Hoàn thành (+Cancel): **{int(row['done_tasks'])}**")
                st.write(f"🚧 In Progress: **{int(row['inprogress_tasks'])}**")
                st.write(f"⏳ Chưa làm (None): **{int(row['none_tasks'])}**")
                st.progress(min(row['Progress_Task']/100, 1.0))
                st.divider()

        # --- BIỂU ĐỒ ---
        st.subheader("📊 Phân bổ thời gian thực tế")
        fig_df = pic_stats[['PIC', 'active_real', 'total_est']].copy()
        fig_df.columns = ['PIC', 'Thực tế (Real)', 'Dự tính (Est)']
        fig = px.bar(fig_df.melt(id_vars='PIC'), x='PIC', y='value', color='variable', barmode='group', text_auto='.1f')
        st.plotly_chart(fig, use_container_width=True)

        # --- GỬI DISCORD ---
        st.sidebar.subheader("📢 Discord Report")
        webhook_url = st.sidebar.text_input("Webhook URL:", type="password")
        if st.sidebar.button("📤 Gửi báo cáo"):
            if webhook_url:
                msg = "📊 **SPRINT STATUS REPORT (Cancel = Done)** 📊\n"
                msg += "━━━━━━━━━━━━━━━━━━━━━\n"
