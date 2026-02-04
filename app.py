import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Sprint Analyzer", layout="wide")

conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1llUlTDfR413oZelu-AoMsC0lEzHqXOkB4SCwc_4zmAo/edit?pli=1&gid=982443592#gid=982443592"

try:
    # Bước 1: Đọc dữ liệu thô để tìm vị trí hàng tiêu đề
    raw_df = conn.read(spreadsheet=URL, header=None)
    header_idx = None
    for i, row in raw_df.iterrows():
        if "Userstory/Todo" in row.values:
            header_idx = i
            break

    if header_idx is not None:
        # Bước 2: Đọc dữ liệu thật từ hàng tiêu đề trở đi
        df = conn.read(spreadsheet=URL, skiprows=header_idx, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]

        # Bước 3: Dọn dẹp số liệu (Sửa lỗi 185,5 -> 185.5)
        for col in ['Estimate Dev', 'Real', 'Remain Dev']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '.')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Bước 4: Lọc dữ liệu thực (Chỉ lấy dòng có PIC hợp lệ, bỏ qua các dòng tiêu đề nhóm màu xám)
        # Theo ảnh, dòng tiêu đề nhóm thường rỗng hoặc là #N/A ở cột PIC
        df_clean = df[df['PIC'].notna() & (df['PIC'] != '#N/A') & (df['PIC'].str.strip() != '')].copy()

        st.title("📊 Sprint Backlog Analysis Dashboard")

        # --- PHẦN 1: CHỈ SỐ TỔNG HỢP ---
        total_est = df_clean['Estimate Dev'].sum()
        total_real = df_clean['Real'].sum()
        total_remain = df_clean['Remain Dev'].sum()
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tổng Estimate", f"{total_est}h")
        c2.metric("Thực tế đã làm", f"{total_real}h")
        c3.metric("Còn lại", f"{total_remain}h")
        
        done_rate = (len(df_clean[df_clean['State'] == 'Done']) / len(df_clean) * 100) if len(df_clean) > 0 else 0
        c4.metric("Tiến độ hoàn thành", f"{done_rate:.1f}%")

        # --- PHẦN 2: BURNDOWN CHART GIẢ LẬP ---
        st.subheader("📉 Burndown Chart (Khối lượng công việc)")
        fig_burn = go.Figure()
        fig_burn.add_trace(go.Scatter(x=['Bắt đầu', 'Hiện tại'], y=[total_est, total_remain], mode='lines+markers', name='Công việc còn lại'))
        fig_burn.update_layout(yaxis_title="Giờ công (h)")
        st.plotly_chart(fig_burn, use_container_width=True)

        # --- PHẦN 3: PHÂN TÍCH NHANH/CHẬM THEO PIC ---
        st.subheader("👤 Phân tích hiệu suất cá nhân")
        pic_stats = df_clean.groupby('PIC').
