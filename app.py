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
    # Đọc dữ liệu
    df = conn.read(spreadsheet=URL)

    # 1. Dọn dẹp dữ liệu: Chuyển dấu phẩy thành dấu chấm để tính toán
    for col in ['Estimate Dev', 'Real', 'Remain Dev']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '.')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 2. Loại bỏ các dòng tiêu đề màu xám 
    # (Các dòng tiêu đề thường có PIC là rỗng hoặc #N/A)
    df_clean = df[df['PIC'].notna() & (df['PIC'] != '#N/A') & (df['PIC'] != '')].copy()

    # 3. Giao diện Dashboard
    st.title("🚀 Phân Tích Sprint Backlog")
    
    # Tính toán chỉ số dựa trên dòng dữ liệu thực tế
    total_est = df_clean['Estimate Dev'].sum()
    total_real = df_clean['Real'].sum()
    remain = df_clean['Remain Dev'].sum()
    done_tasks = len(df_clean[df_clean['State'] == 'Done'])
    total_tasks = len(df_clean)
    
    # Hiển thị các con số tổng quát
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tổng dự tính", f"{total_est}h")
    c2.metric("Thực tế đạt được", f"{total_real}h")
    c3.metric("Khối lượng còn lại", f"{remain}h")
    progress = (done_tasks / total_tasks * 100) if total_tasks > 0 else 0
    c4.metric("Tiến độ hoàn thành", f"{progress:.1f}%")

    # 4. Biểu đồ trực quan theo PIC (Người thực hiện)
    st.subheader("Khối lượng công việc theo từng thành viên")
    pic_data = df_clean.groupby('PIC')[['Estimate Dev', 'Real']].sum().reset_index()
    fig = px.bar(pic_data, x='PIC', y=['Estimate Dev', 'Real'], barmode='group',
                 labels={'value': 'Số giờ', 'variable': 'Loại thời gian'})
    st.plotly_chart(fig, use_container_width=True)

    # 5. Hiển thị bảng dữ liệu đã lọc (giống ảnh của bạn)
    st.subheader("Chi tiết danh sách Task")
    st.dataframe(df_clean[['Userstory/Todo', 'State', 'Estimate Dev', 'Real', 'PIC', 'Remain Dev']])

except Exception as e:
    st.error(f"Lỗi kết nối: {e}")
    st.info("Kiểm tra: 1. Đã Share Sheet cho Service Account chưa? 2. Tên cột có đúng 'Estimate Dev', 'Real', 'PIC' không?")
