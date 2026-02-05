import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Sprint Workload Analyzer", layout="wide")

conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1llUlTDfR413oZelu-AoMsC0lEzHqXOkB4SCwc_4zmAo/edit?pli=1&gid=982443592#gid=982443592"

try:
    # 1. Đọc dữ liệu
    raw_df = conn.read(spreadsheet=URL, header=None)
    header_idx = None
    for i, row in raw_df.iterrows():
        if "Userstory/Todo" in row.values:
            header_idx = i
            break
            
    if header_idx is not None:
        df = conn.read(spreadsheet=URL, skiprows=header_idx)
        df.columns = [str(c).strip() for c in df.columns]
        
        # 2. Xử lý số liệu và chuẩn hóa State
        for col in ['Estimate Dev', 'Real']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        
        # Gán nhãn "None" cho các ô State trống
        df['State'] = df['State'].fillna('None').replace('', 'None')

        # 3. Lọc Team (Chỉ lấy những dòng đã giao PIC)
        valid_pics = ['Tài', 'Dương', 'QA', 'Quân', 'Phú']
        df_team = df[df['PIC'].isin(valid_pics)].copy()

        st.title("🚀 Phân Tích Khối Lượng & Hiệu Suất Team")

        # --- TÍNH TOÁN THEO LOGIC MỚI ---
        # Tính tổng giờ Est của các task State == "None" (Chưa làm)
        pending_work = df_team[df['State'] == 'None'].groupby('PIC')['Estimate Dev'].sum().reset_index()
        pending_work.columns = ['PIC', 'Pending_Est']

        # Tính tổng giờ Est và Real của các task đã/đang làm (State != "None")
        active_work = df_team[df['State'] != 'None'].groupby('PIC').agg({
            'Estimate Dev': 'sum',
            'Real': 'sum'
        }).reset_index()
        active_work.columns = ['PIC', 'Active_Est', 'Active_Real']

        # Gộp tất cả dữ liệu theo PIC
        pic_stats = pd.DataFrame({'PIC': valid_pics})
        pic_stats = pic_stats.merge(active_work, on='PIC', how='left')
        pic_stats = pic_stats.merge(pending_work, on='PIC', how='left').fillna(0)

        # Tổng Estimate của một người = Giờ đang làm + Giờ đang chờ (None)
        pic_stats['Total_Estimate'] = pic_stats['Active_Est'] + pic_stats['Pending_Est']

        # Hiệu suất làm việc (Chỉ tính trên những task đã bắt đầu làm để công bằng)
        pic_stats['Efficiency (%)'] = (pic_stats['Active_Est'] / pic_stats['Active_Real'] * 100).fillna(0).round(1)
        pic_stats.loc[pic_stats['Active_Real'] == 0, 'Efficiency (%)'] = 0

        # --- GIAO DIỆN ---
        st.subheader("👤 Chi tiết khối lượng từng thành viên")
        cols = st.columns(len(valid_pics))
        
        for i, row in pic_stats.iterrows():
            with cols[i]:
                st.write(f"### **{row['PIC']}**")
                st.metric("Tổng Est", f"{row['Total_Estimate']}h")
                st.write(f"✅ Đã làm: **{row['Active_Real']}h**")
                st.write(f"⏳ Đang chờ (None): **{row['Pending_Est']}h**")
                
                # Thanh tiến độ công việc của người đó
                progress_val = (row['Active_Real'] / row['Total_Estimate']) if row['Total_Estimate'] > 0 else 0
                st.progress(min(progress_val, 1.0))
                st.caption(f"Tiến độ: {row['Efficiency (%)']}%")

        st.divider()

        # --- BIỂU ĐỒ PHÂN TÍCH ---
        # --- PHẦN XỬ LÝ DỮ LIỆU BIỂU ĐỒ ---
        st.subheader("📊 Biểu đồ so sánh: Real-time vs Tồn đọng (None)")

        # Tạo DataFrame tạm để vẽ biểu đồ, đảm bảo các cột tồn tại
        chart_data = pic_stats[['PIC', 'Active_Real', 'Total_Estimate', 'Pending_Est']].copy()
        
        # Đổi tên cột để hiển thị trên biểu đồ cho đẹp
        chart_data.columns = ['PIC', 'Thực tế (Real-time)', 'Tổng dự tính (Kế hoạch)', 'Dự kiến đang chờ (None)']

        # Chuyển đổi dữ liệu sang dạng dọc (Melt)
        fig_df = chart_data.melt(
            id_vars='PIC', 
            var_name='Trạng thái', 
            value_name='Số giờ'
        )

        # Kiểm tra nếu có dữ liệu thì mới vẽ
        if not fig_df.empty:
            fig = px.bar(
                fig_df, 
                x='PIC', 
                y='Số giờ', 
                color='Trạng thái', 
                barmode='group', # Hiển thị các cột nằm cạnh nhau
                text_auto='.1f', # Hiện số giờ trên đầu cột
                color_discrete_map={
                    'Thực tế (Real-time)': '#00C853',      # Xanh lá
                    'Tổng dự tính (Kế hoạch)': '#636EFA', # Xanh dương
                    'Dự kiến đang chờ (None)': '#FFD600'  # Vàng
                }
            )

            fig.update_layout(
                xaxis_title="Thành viên Team",
                yaxis_title="Số giờ (h)",
                legend_title="Chỉ số",
                margin=dict(l=20, r=20, t=50, b=20),
                height=500
            )

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("⚠️ Không có dữ liệu để hiển thị biểu đồ.")

        # 4. Bảng chi tiết (Highlight các task None)
        st.subheader("📋 Danh sách Task chi tiết")
        def style_rows(row):
            return ['background-color: #f5f5f5; color: #9e9e9e' if row.State == 'None' else '' for _ in row]

        st.dataframe(df_team[['Userstory/Todo', 'State', 'Estimate Dev', 'Real', 'PIC']].style.apply(style_rows, axis=1), 
                     use_container_width=True)
              
    else:
        st.error("Không tìm thấy tiêu đề 'Userstory/Todo'.")

except Exception as e:
    st.error(f"Lỗi hệ thống: {e}")
