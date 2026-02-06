import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import requests

st.set_page_config(page_title="Sprint Workload Analyzer", layout="wide")

conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1llUlTDfR413oZelu-AoMsC0lEzHqXOkB4SCwc_4zmAo/edit?pli=1&gid=982443592#gid=982443592"

try:
    raw_df = conn.read(spreadsheet=URL, header=None)
    header_idx = next((i for i, row in raw_df.iterrows() if "Userstory/Todo" in row.values), None)
            
    if header_idx is not None:
        df = conn.read(spreadsheet=URL, skiprows=header_idx)
        df.columns = [str(c).strip() for c in df.columns]
        for col in ['Estimate Dev', 'Real']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        
        df['State'] = df['State'].fillna('None').replace('', 'None')
        valid_pics = ['Tài', 'Dương', 'QA', 'Quân', 'Phú', 'Thịnh', 'Đô', 'Tùng', 'Anim', 'Thắng VFX']
        df_team = df[df['PIC'].isin(valid_pics)].copy()

        st.title("🚀 Sprint Workload & Performance")

        # --- TÍNH TOÁN ---
        task_counts = df_team.groupby('PIC').agg(
            total_tasks=('Userstory/Todo', 'count'),
            done_tasks=('State', lambda x: (x.str.strip().str.lower() == 'done').sum())
        ).reset_index()
        task_counts['Progress_Task'] = (task_counts['done_tasks'] / task_counts['total_tasks'] * 100).fillna(0).round(1)

        pending_work = df_team[df_team['State'] == 'None'].groupby('PIC')['Estimate Dev'].sum().reset_index().rename(columns={'Estimate Dev': 'Pending_Est'})
        active_work = df_team[df_team['State'] != 'None'].groupby('PIC').agg({'Estimate Dev': 'sum', 'Real': 'sum'}).reset_index().rename(columns={'Estimate Dev': 'Active_Est', 'Real': 'Active_Real'})

        pic_stats = pd.DataFrame({'PIC': valid_pics}).merge(active_work, on='PIC', how='left').merge(pending_work, on='PIC', how='left').merge(task_counts, on='PIC', how='left').fillna(0)
        pic_stats['Total_Estimate'] = pic_stats['Active_Est'] + pic_stats['Pending_Est']

        # --- GIAO DIỆN ---
        st.subheader("👤 Tiến độ thành viên")
        cols = st.columns(5)
        for i, row in pic_stats.iterrows():
            with cols[i % 5]:
                st.metric(row['PIC'], f"{row['Progress_Task']}%", f"{int(row['done_tasks'])}/{int(row['total_tasks'])} Task")
                st.caption(f"Real: {row['Active_Real']}h | Chờ: {row['Pending_Est']}h")
                st.progress(min(row['Progress_Task']/100, 1.0))

        # --- BIỂU ĐỒ ---
        st.subheader("📊 Biểu đồ Real-time vs Tồn đọng")
        fig_df = pic_stats[['PIC', 'Active_Real', 'Total_Estimate', 'Pending_Est']].copy()
        fig_df.columns = ['PIC', 'Thực tế (Real)', 'Tổng dự tính', 'Đang chờ (None)']
        fig = px.bar(fig_df.melt(id_vars='PIC'), x='PIC', y='value', color='variable', barmode='group', text_auto='.1f',
                     color_discrete_map={'Thực tế (Real)': '#00C853', 'Tổng dự tính': '#636EFA', 'Đang chờ (None)': '#FFD600'})
        st.plotly_chart(fig, use_container_width=True)

        # --- DISCORD WEBHOOK ---
        st.sidebar.subheader("📢 Discord Report")
        webhook_url = st.sidebar.text_input("Webhook URL:", type="password")
        if st.sidebar.button("📤 Gửi báo cáo Text"):
            if webhook_url:
                msg = "🚀 **SPRINT REPORT**\n" + "━" * 15 + "\n"
                for _, r in pic_stats.iterrows():
                    icon = "🟢" if r['Progress_Task'] >= 80 else "🟡"
                    msg += f"{icon} **{r['PIC']}**: `{r['Progress_Task']}%` | Real: `{r['Active_Real']}h` | Chờ: `{r['Pending_Est']}h`\n"
                requests.post(webhook_url, json={"content": msg})
                st.sidebar.success("Đã gửi!")

        st.subheader("📋 Chi tiết Task")
        st.dataframe(df_team[['Userstory/Todo', 'State', 'Estimate Dev', 'Real', 'PIC']], use_container_width=True)
              
    else: st.error("Không tìm thấy tiêu đề 'Userstory/Todo'.")
except Exception as e: st.error(f"Lỗi: {e}")
