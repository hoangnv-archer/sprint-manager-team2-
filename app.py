import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Sprint Dashboard Pro", layout="wide")

# Kết nối an toàn qua Secrets
conn = st.connection("gsheets", type=GSheetsConnection)

# Dán link trình duyệt file Sheet của bạn vào đây
URL = "https://docs.google.com/spreadsheets/d/1llUlTDfR413oZelu-AoMsC0lEzHqXOkB4SCwc_4zmAo/edit?pli=1&gid=982443592#gid=982443592"

try:
    # Đọc toàn bộ sheet để tìm hàng tiêu đề
    raw_df = conn.read(spreadsheet=URL, header=None)
    
    # Tìm hàng chứa chữ "Userstory/Todo"
    header_row = 0
    for i, row in raw_df.iterrows():
        if "Userstory/Todo" in row.values:
            header_row = i
            break
            
    # Đọc lại dữ liệu chuẩn từ hàng tiêu đề đó
    df = conn.read(spreadsheet=URL, ttl=0) # ttl=0 để luôn lấy dữ liệu mới nhất
    
    # Chuẩn hóa tên cột (Xóa khoảng trắng thừa)
    df.columns = [str(c).strip() for c in df.columns]

    # Kiểm tra lại các cột quan trọng
    required_cols = ['Userstory/Todo', 'State', 'Estimate Dev', 'Real', 'PIC']
    if all(col in df.columns for col in required_cols):
        
        # 1. Dọn dẹp số liệu (Sửa lỗi dấu phẩy 185,5 -> 185.5)
        for col in ['Estimate Dev', 'Real', 'Remain Dev']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '.')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # 2. Loại bỏ các dòng tiêu đề màu xám (Dòng không có PIC thực sự)
        df_clean = df[df['PIC'].notna() & (df['PIC'] != '#N/A') & (df['PIC'].str.strip() != '')].copy()

        # 3. Giao diện Dashboard
        st.title("🚀 Phân Tích Sprint Backlog")
        
        total_est = df_clean['Estimate Dev'].sum()
        total_real = df_clean['Real'].sum()
        remain = df_clean['Remain Dev'].sum()
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tổng dự tính (Est)", f"{total_est}h")
        c2.metric("Thực tế (Real)", f"{total_real}h")
        c3.metric("Còn lại (Remain)", f"{remain}h")
        
        done_progress = (len(df_clean[df_clean['State'] == 'Done']) / len(df_clean) * 100) if len(df_clean) > 0 else 0
        c4.metric("Tiến độ", f"{done_progress:.1f}%")

        # 4. Biểu đồ theo PIC
        st.subheader("Khối lượng công việc theo PIC")
        pic_summary = df_clean.groupby('PIC')[['Estimate Dev', 'Real']].sum().reset_index()
        fig = px.bar(pic_summary, x='PIC', y=['Estimate Dev', 'Real'], barmode='group')
        st.plotly_chart(fig, use_container_width=True)

        # 5. Bảng chi tiết
        st.subheader("Danh sách chi tiết (Đã lọc tiêu đề nhóm)")
        st.dataframe(df_clean[required_cols + ['Remain Dev']])
        
    else:
        st.error(f"Không tìm thấy đủ các cột cần thiết. Cột hiện có: {list(df.columns)}")
        st.info("Hãy đảm bảo tiêu đề cột trong Sheet giống hệt: Userstory/Todo, State, Estimate Dev, Real, PIC")

except Exception as e:
    st.error(f"Lỗi hệ thống: {e}")
