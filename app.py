import streamlit as st
from streamlit_gsheets import GSheetsConnection

# Tiêu đề app
st.title("Sprint Backlog Analyzer") [cite: 1]

# Kết nối (Sẽ tự động tìm thông tin trong [connections.gsheets])
conn = st.connection("gsheets", type=GSheetsConnection) [cite: 5, 14]

# Đọc dữ liệu
df = conn.read(spreadsheet="https://docs.google.com/spreadsheets/d/1llUlTDfR413oZelu-AoMsC0lEzHqXOkB4SCwc_4zmAo/edit?pli=1&gid=982443592#gid=982443592")
st.write(df)
try:
    df = conn.read(spreadsheet=url)
    
    # Hiển thị bảng dữ liệu để kiểm tra
    st.write("Dữ liệu hiện tại:")
    st.dataframe(df)
    
    # Tại đây bạn có thể thêm các code vẽ biểu đồ như tôi đã hướng dẫn ở trên
except Exception as e:
    st.error(f"Đang chờ kết nối dữ liệu... Lỗi: {e}")
    for col in ['Estimate', 'Actual']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '.').astype(float)

    # Hiển thị các chỉ số tổng quát
    col1, col2, col3 = st.columns(3)
    with col1:
        total_tasks = len(df)
        done_tasks = len(df[df['Docs'] == 'Done'])
        st.metric("Tiến độ", f"{(done_tasks/total_tasks)*100:.1f}%")
    with col2:
        st.metric("Tổng Estimate", f"{df['Estimate'].sum()}h")
    with col3:
        diff = df['Actual'].sum() - df['Estimate'].sum()
        st.metric("Chênh lệch thực tế", f"{df['Actual'].sum()}h", delta=f"{diff:.1f}h", delta_color="inverse")

    # Biểu đồ
    st.subheader("Biểu đồ khối lượng công việc")
    fig = px.bar(df, x=df.columns[0], y=['Estimate', 'Actual'], barmode='group')
    st.plotly_chart(fig, use_container_width=True)

    # Bảng dữ liệu
    st.subheader("Danh sách chi tiết")
    st.dataframe(df)

except Exception as e:
    st.error(f"Lỗi: Không thể đọc dữ liệu. Hãy kiểm tra link CSV. Chi tiết: {e}")
