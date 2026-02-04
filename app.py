import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Sprint Dashboard Pro", layout="wide")

# 1. Kết nối an toàn
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. Đọc dữ liệu (Thay link Sheet của bạn vào đây)
URL = "https://docs.google.com/spreadsheets/d/your_id/edit"

try:
    # Đọc dữ liệu từ hàng thứ 2 (để lấy đúng header: Userstory/Todo, State, Estimate Dev, Real, PIC)
    df = conn.read(spreadsheet=URL)

    # 3. Dọn dẹp dữ liệu
    # Chuyển đổi số thập phân từ dấu phẩy sang dấu chấm
    for col in ['Estimate Dev', 'Real', 'Remain Dev']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '.')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Loại bỏ các dòng tiêu đề (Dòng có PIC là #N/A hoặc rỗng)
    # Dựa trên ảnh, các dòng tiêu đề nhóm thường không có người phụ trách (PIC)
    df_clean = df[df['PIC'].notna() & (df['PIC'] != '#N/A')].copy()

    # 4. Giao diện Dashboard
    st.title("🚀 Sprint Backlog Analysis")
    
    # Chỉ số tổng quát
    total_est = df_clean['Estimate Dev'].sum()
    total_real = df_clean['Real'].sum()
    remain = df_clean['Remain Dev'].sum()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tổng Estimate", f"{total_est}h")
    col2.metric("Thực tế (Real)", f"{total_real}h")
    col3.metric("Còn lại (Remain)", f"{remain}h")
    
    # Tỉ lệ hoàn thành
    done_count = len(df_clean[df_clean['State'] == 'Done'])
    total_count = len(df_clean)
    progress = (done_count / total_count) if total_count > 0 else 0
    col4.metric("Tiến độ Task", f"{progress*100:.1f}%")

    # 5. Biểu đồ theo người phụ trách (PIC)
    st.subheader("Phân bổ khối lượng công việc theo PIC")
    pic_chart = df_clean.groupby('PIC')[['Estimate Dev', 'Real']].sum().reset_index()
    fig = px.bar(pic_chart, x='PIC', y=['Estimate Dev', 'Real'], barmode='group')
    st.plotly_chart(fig, use_container_width=True)

    # 6. Bảng dữ liệu chi tiết (đã lọc tiêu đề)
    st.subheader("Danh sách Task chi tiết")
    st.dataframe(df_clean[['Userstory/Todo', 'State', 'Estimate Dev', 'Real', 'PIC', 'Remain Dev']])

except Exception as e:
    st.error("Chưa kết nối được dữ liệu. Vui lòng kiểm tra lại 'Secrets' và Link Sheet.")
    st.info("Lưu ý: Đảm bảo tên cột trong Sheet khớp 100% với: Userstory/Todo, State, Estimate Dev, Real, PIC")
