import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Sprint Velocity Analyzer", layout="wide")

# Kết nối dữ liệu
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1llUlTDfR413oZelu-AoMsC0lEzHqXOkB4SCwc_4zmAo/edit?pli=1&gid=982443592#gid=982443592"

try:
    # 1. Tìm hàng tiêu đề (Userstory/Todo) - Thường nằm ở hàng 15
    raw_df = conn.read(spreadsheet=URL, header=None)
    header_idx = None
    for i, row in raw_df.iterrows():
        if "Userstory/Todo" in row.values:
            header_idx = i
            break

    if header_idx is not None:
        # 2. Đọc dữ liệu từ hàng tiêu đề trở đi
        df = conn.read(spreadsheet=URL, skiprows=header_idx, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]

        # 3. Xử lý số liệu (Chuyển dấu phẩy 185,5 -> 185.5)
        for col in ['Estimate Dev', 'Real']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '.')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # 4. Lọc lấy các task thực tế (Chỉ lấy dòng có PIC)
        df_clean = df[df['PIC'].notna() & (df['PIC'] != '#N/A') & (df['PIC'].str.strip() != '')].copy()

        st.title("🚀 Phân Tích Tốc Độ & Hiệu Suất Team")

        # 5. Tổng hợp dữ liệu theo PIC
        velocity_df = df_clean.groupby('PIC').agg(
            total_est=('Estimate Dev', 'sum'),
            total_real=('Real', 'sum'),
            task_count=('Userstory/Todo', 'count')
        ).reset_index()

        # 6. Tính toán chỉ số Hiệu suất
        # Hiệu suất % = (Dự kiến / Thực tế) * 100
        velocity_df['Efficiency'] = (velocity_df['total_est'] / velocity_df['total_real'] * 100).round(1)
        # Tỉ lệ Tốc độ (Speed Ratio): Thực tế / Dự kiến
        velocity_df['
