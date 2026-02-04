import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Sprint Dashboard Pro", layout="wide")

# Kết nối an toàn qua Secrets
conn = st.connection("gsheets", type=GSheetsConnection)

# Link Sheet của bạn
URL = "https://docs.google.com/spreadsheets/d/1llUlTDfR413oZelu-AoMsC0lEzHqXOkB4SCwc_4zmAo/edit?pli=1&gid=982443592#gid=982443592"

try:
    # 1. Đọc dữ liệu thô để tìm hàng tiêu đề thực sự
    raw_df = conn.read(spreadsheet=URL, header=None)
    
    # Tìm hàng chứa chữ "Userstory/Todo" (Thường là hàng 15 trong ảnh của bạn)
    header_idx = None
    for i, row in raw_df.iterrows():
        if "Userstory/Todo" in row.values:
            header_idx = i
            break
            
    if header_idx is not None:
        # Đọc lại dữ liệu chuẩn từ hàng tiêu đề đó
        df = conn.read(spreadsheet=URL, skiprows=header_idx, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]
        
        # 2. Xử lý số thập phân (185,5 -> 185.5)
        for col in ['Estimate Dev', 'Real', 'Remain Dev']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '.')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # 3. Lọc lấy các task thực tế (Bỏ dòng tiêu đề nhóm màu xám - PIC rỗng)
        # Lấy các PIC có tên thực tế như: Tài, Dương, QA, Quân...
        df_clean = df[df['PIC'].notna() & (df['PIC'] != '#N/A') & (df['PIC'].str.strip() != '')].copy()

        st.title("📊 Sprint Analysis & Burndown")

        # --- BIỂU ĐỒ BURNDOWN ---
        st.subheader("📉 Sprint Burndown Chart")
        total_est = df_clean['Estimate Dev'].sum()
        current_remain = df_clean['Remain Dev'].sum()
        
        fig_burn = go.Figure()
        # Đường mục tiêu (Dự kiến xong hết)
        fig_burn.add_trace(go.Scatter(x=['Bắt đầu', 'Kết thúc'], y=[total_est, 0], name='Mục tiêu (Lý tưởng)', line=dict(dash='dash')))
        # Đường thực tế hiện tại
        fig_burn.add_trace(go.Scatter(x=['Bắt đầu', 'Hiện tại'], y=[total_est, current_remain], name='Thực tế còn lại', mode='lines+markers'))
        st.plotly_chart(fig_burn, use_container_width=True)

        # --- PHÂN TÍCH TỪNG NGƯỜI (NHANH/CHẬM) ---
        st.subheader("👤 Hiệu suất cá nhân")
        
        # Tính toán group theo PIC (Đã sửa lỗi Syntax của bạn)
        pic_stats = df_clean.groupby('PIC').agg({'Estimate Dev': 'sum', 'Real': 'sum'}).reset_index()
        
        # Chỉ số Speed = Real / Estimate ( < 1 là nhanh, > 1 là chậm)
        pic_stats['Efficiency'] = pic_stats['Real'] / pic_stats['Estimate Dev']

        cols = st.columns(len(pic_stats))
        for i, row in pic_stats.iterrows():
            with cols[i]:
                # Logic đánh giá Nhanh/Chậm
                if row['Efficiency'] < 1:
                    status = f"🚀 Nhanh (vượt {(1-row['Efficiency'])*100:.0f}%)"
                    color = "normal"
                elif row['Efficiency'] > 1:
                    status = f"⚠️ Chậm (lố {(row['Efficiency']-1)*100:.0f}%)"
                    color = "inverse"
                else:
                    status = "✅ Đúng hạn"
                    color = "off"
                
                st.metric(label=f"PIC: {row['PIC']}", 
                          value=f"{row['Real']}h / {row['Estimate Dev']}h", 
                          delta=status, delta_color=color)

        # Biểu đồ so sánh Real vs Est theo PIC
        fig_pic = px.bar(pic_stats, x='PIC', y=['Estimate Dev', 'Real'], barmode='group', title="So sánh Estimate vs Real")
        st.plotly_chart(fig_pic, use_container_width=True)

    else:
        st.error("Không tìm thấy hàng tiêu đề 'Userstory/Todo'. Kiểm tra lại Sheet!")

except Exception as e:
    st.error(f"Lỗi: {e}")
