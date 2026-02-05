import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Sprint Real-time Tracker", layout="wide")

conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1llUlTDfR413oZelu-AoMsC0lEzHqXOkB4SCwc_4zmAo/edit?pli=1&gid=982443592#gid=982443592"

try:
    # 1. Đọc dữ liệu
    raw_df = conn.read(spreadsheet=URL, header=None)
    header_idx = next((i for i, row in raw_df.iterrows() if "Userstory/Todo" in row.values), None)
            
    if header_idx is not None:
        df = conn.read(spreadsheet=URL, skiprows=header_idx)
        df.columns = [str(c).strip() for c in df.columns]
        
        # 2. Xử lý số liệu
        for col in ['Estimate Dev', 'Real']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        
        # Gán nhãn "None" cho State trống
        df['State'] = df['State'].fillna('None').replace('', 'None')

        # 3. Lọc Team
        valid_pics = ['Tài', 'Dương', 'QA', 'Quân', 'Phú']
        df_team = df[df['PIC'].isin(valid_pics)].copy()

        st.title("📊 Real-time Sprint Performance & Workload")

        # --- TÍNH TOÁN TỔNG HỢP ---
        # Tính tổng tất cả Est và Real (Real-time)
        summary = df_team.groupby('PIC').agg({
            'Estimate Dev': 'sum',
            'Real': 'sum'
        }).reset_index()

        # Tính riêng phần Est của những task chưa làm (State == None)
        pending_work = df_team[df_team['State'] == 'None'].groupby('PIC')['Estimate Dev'].sum().reset_index()
        pending_work.columns = ['PIC', 'Pending Hours (None)']

        # Gộp dữ liệu
        final_df = pd.merge(summary, pending_work, on='PIC', how='left').fillna(0)

        # Hiệu suất % = (Dự tính / Thực tế) * 100
        final_df['Efficiency (%)'] = (final_df['Estimate Dev'] / final_df['Real'] * 100).fillna(0).round(1)
        final_df.loc[final_df['Real'] == 0, 'Efficiency (%)'] = 0

        # --- GIAO DIỆN METRICS ---
        cols = st.columns(len(valid_pics))
        for i, row in final_df.iterrows():
            with cols[i]:
                st.write(f"### **{row['PIC']}**")
                st.metric("Thực tế (Real)", f"{row['Real']:.1f}h", delta=f"Tổng Est: {row['Estimate Dev']:.1f}h", delta_color="off")
                st.write(f"⏳ Đang chờ (None): **{row['Pending Hours (None)']:.1f}h**")
                st.caption(f"Hiệu suất: {row['Efficiency (%)']}%")

        st.divider()

        # --- BIỂU ĐỒ SO SÁNH REAL-TIME ---
        st.subheader("📈 Biểu đồ so sánh Real-time: Dự kiến vs Thực tế")
        
        # Chuyển dữ liệu sang dạng dọc để vẽ biểu đồ cột nhóm
        plot_df = final_df.melt(id_vars='PIC', value_vars=['Estimate Dev', 'Real', 'Pending Hours (None)'], 
                                var_name='Metric', value_name='Hours')
        
        fig = px.bar(plot_df, x='PIC', y='Hours', color='Metric', 
                     barmode='group', text_auto='.1f',
                     color_discrete_map={
                         'Estimate Dev': '#636EFA',   # Xanh dương (Tổng dự kiến)
                         'Real': '#00C853',           # Xanh lá (Thực tế đã làm - Real time)
                         'Pending Hours (None)': '#FFD600' # Vàng (Phần việc chưa động vào)
                     },
                     title="Phân tích chi tiết giờ công theo từng PIC")
        
        st.plotly_chart(fig, use_container_width=True)

        # 4. Bảng chi tiết
        st.subheader("📋 Danh sách Task")
        st.dataframe(df_team[['Userstory/Todo', 'State', 'Estimate Dev', 'Real', 'PIC']], use_container_width=True)
              
    else:
        st.error("Không tìm thấy hàng tiêu đề 'Userstory/Todo'.")

except Exception as e:
    st.error(f"Lỗi hệ thống: {e}")
