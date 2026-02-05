import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Sprint Analyzer Pro", layout="wide")

# Kết nối an toàn qua Secrets
conn = st.connection("gsheets", type=GSheetsConnection)

# Dán link trình duyệt file Sheet của bạn vào đây
URL = "https://docs.google.com/spreadsheets/d/1llUlTDfR413oZelu-AoMsC0lEzHqXOkB4SCwc_4zmAo/edit?pli=1&gid=982443592#gid=982443592"

try:
    # 1. Đọc dữ liệu thô (không lấy header) để dò tìm hàng tiêu đề thực sự
    raw_df = conn.read(spreadsheet=URL, header=None)
    
    # Tìm hàng chứa chữ "Userstory/Todo" để xác định header
    header_idx = None
    for i, row in raw_df.iterrows():
        if "Userstory/Todo" in row.values:
            header_idx = i
            break
            
    if header_idx is not None:
        # Đọc lại dữ liệu bắt đầu từ hàng tiêu đề đã tìm thấy
        df = conn.read(spreadsheet=URL, skiprows=header_idx)
        
        # Làm sạch tên cột (xóa khoảng trắng thừa)
        df.columns = [str(c).strip() for c in df.columns]
        
        # 2. Xử lý số liệu: Chuyển '185,5' thành 185.5
        for col in ['Estimate Dev', 'Real', 'Remain Dev']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '.')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # 3. Lọc dữ liệu: Chỉ lấy dòng có PIC và bỏ qua dòng 'Summary' (hàng ngay dưới header)
        # Chúng ta lọc bỏ dòng có chứa tổng số 185.5 bằng cách kiểm tra PIC hợp lệ
        valid_pics = ['Tài', 'Dương', 'QA', 'Quân', 'Phú'] # Bạn có thể thêm tên team vào đây
        df_clean = df[df['PIC'].isin(valid_pics)].copy()

        # 4. Giao diện Dashboard
        st.title("🚀 Sprint Backlog Analysis")
        
        # Tính toán các chỉ số
        total_est = df_clean['Estimate Dev'].sum()
        total_real = df_clean['Real'].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Tổng Giờ Dự Tính (Est)", f"{total_est:.1f}h")
        c2.metric("Thực Tế Đã Làm (Real)", f"{total_real:.1f}h")
        
        # Tính % hoàn thành
        done_tasks = len(df_clean[df_clean['State'] == 'Done'])
        total_tasks = len(df_clean)
        if total_tasks > 0:
            progress = (done_tasks / total_tasks) * 100
            c3.metric("Tiến độ Sprint", f"{progress:.1f}%")

        # 5. Biểu đồ theo PIC
        st.subheader("Phân bổ khối lượng theo thành viên")
        pic_chart = df_clean.groupby('PIC')[['Estimate Dev', 'Real']].sum().reset_index()
        fig = px.bar(pic_chart, x='PIC', y=['Estimate Dev', 'Real'], barmode='group')
        st.plotly_chart(fig, use_container_width=True)

        # 6. Bảng danh sách task (đã lọc sạch)
        st.subheader("Danh sách Task chi tiết")
        st.dataframe(df_clean[['Userstory/Todo', 'State', 'Estimate Dev', 'Real', 'PIC']])
        
    else:
        st.error("Không tìm thấy hàng tiêu đề 'Userstory/Todo'. Vui lòng kiểm tra lại cấu trúc Sheet.")

except Exception as e:
    st.error(f"Lỗi hệ thống: {e}")
