import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, time, timedelta

# --- 1. HÀM TÍNH GIỜ LÀM VIỆC ---
def calculate_working_hours(start_dt, end_dt):
    if pd.isna(start_dt) or start_dt > end_dt:
        return 0
    total_seconds = 0
    curr = start_dt
    while curr.date() <= end_dt.date():
        if curr.weekday() < 5: # Thứ 2 - Thứ 6
            morn_s = datetime.combine(curr.date(), time(8, 30))
            morn_e = datetime.combine(curr.date(), time(12, 0))
            aft_s = datetime.combine(curr.date(), time(13, 30))
            aft_e = datetime.combine(curr.date(), time(18, 0))
            
            s_m, e_m = max(curr, morn_s), min(end_dt, morn_e)
            if s_m < e_m: total_seconds += (e_m - s_m).total_seconds()
            
            s_a, e_a = max(curr, aft_s), min(end_dt, aft_e)
            if s_a < e_a: total_seconds += (e_a - s_a).total_seconds()
            
        curr = (curr + timedelta(days=1)).replace(hour=8, minute=30, second=0)
    return total_seconds / 3600

st.set_page_config(page_title="Sprint Workload Analyzer", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1llUlTDfR413oZelu-AoMsC0lEzHqXOkB4SCwc_4zmAo/edit?pli=1&gid=982443592#gid=982443592"

try:
    raw_df = conn.read(spreadsheet=URL, header=None)
    header_idx = next((i for i, row in raw_df.iterrows() if "Userstory/Todo" in row.values), None)
            
    if header_idx is not None:
        df = conn.read(spreadsheet=URL, skiprows=header_idx)
        df.columns = [str(c).strip() for c in df.columns]
        
        # Đảm bảo các cột cần thiết tồn tại
        for c in ['Estimate Dev', 'Real', 'Start_time', 'State', 'PIC']:
            if c not in df.columns: df[c] = 0 if c in ['Estimate Dev', 'Real'] else 'None'

        # Xử lý định dạng
        df['Estimate Dev'] = pd.to_numeric(df['Estimate Dev'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        df['Real'] = pd.to_numeric(df['Real'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        df['Start_time'] = pd.to_datetime(df['Start_time'], errors='coerce')
        df['State_Clean'] = df['State'].fillna('None').str.strip().str.lower()
        
        valid_pics = ['Tài', 'Dương', 'QA', 'Quân', 'Phú', 'Thịnh', 'Đô', 'Tùng', 'Anim', 'Thắng VFX']
        df_team = df[df['PIC'].isin(valid_pics)].copy()

        # LOGIC CẢNH BÁO OVER ESTIMATE
        now = datetime.now()
        over_est_list = []
        for _, row in df_team.iterrows():
            if row['State_Clean'] == 'in progress' and not pd.isna(row['Start_time']):
                actual = calculate_working_hours(row['Start_time'], now)
                est = float(row['Estimate Dev'])
                if est > 0 and actual > est:
                    over_est_list.append({"PIC": row['PIC'], "Task": row['Userstory/Todo'], "Actual": round(actual, 1), "Est": est})

        st.title("🚀 Sprint Workload & Performance")

        if over_est_list:
            st.warning(f"🚨 Có {len(over_est_list)} task đang vượt quá thời gian Estimate!")
            st.table(pd.DataFrame(over_est_list))

        # --- TÍNH TOÁN STATS (GỒM CẢ PHẦN THIẾU) ---
        pic_stats = df_team.groupby('PIC').agg(
            total_tasks=('Userstory/Todo', 'count'),
            done_tasks=('State_Clean', lambda x: x.isin(['done', 'cancel']).sum()),
            inprogress_tasks=('State_Clean', lambda x: (x == 'in progress').sum()),
            none_tasks=('State_Clean', lambda x: (x == 'none').sum()),
            active_real=('Real', 'sum'),
            total_est=('Estimate Dev', 'sum')
        ).reset_index()
        
        # Phần liệt kê số task còn lại
        pic_stats['pending_total'] = pic_stats['total_tasks'] - pic_stats['done_tasks']
        pic_stats['Progress_Task'] = (pic_stats['done_tasks'] / pic_stats['total_tasks'] * 100).fillna(0).round(1)

        # --- HIỂN THỊ METRICS ---
        st.subheader("👤 Trạng thái Task theo PIC")
        cols = st.columns(5)
        for i, row in pic_stats.iterrows():
            with cols[i % 5]:
                st.markdown(f"### **{row['PIC']}**")
                st.metric("Tiến độ", f"{row['Progress_Task']}%")
                st.write(f"✅ Hoàn thành: **{int(row['done_tasks'])}**")
                st.write(f"🚧 Đang làm: **{int(row['inprogress_tasks'])}**")
                st.write(f"⏳ Chưa làm: **{int(row['none_tasks'])}**")
                st.write(f"🚩 Còn lại: **{int(row['pending_total'])}** task") # Đã thêm lại dòng này
                st.progress(min(row['Progress_Task']/100, 1.0))
                st.divider()

        # --- GỬI DISCORD ---
        st.sidebar.subheader("📢 Báo cáo Discord")
        webhook_url = st.sidebar.text_input("Webhook URL:", type="password")
        if st.sidebar.button("📤 Gửi báo cáo chi tiết"):
            if webhook_url:
                msg = "📊 **SPRINT REPORT**\n━━━━━━━━━━━━━━━━━━━━━\n"
                for _, r in pic_stats.iterrows():
                    msg += f"👤 **{r['PIC']}** | `{r['Progress_Task']}%` Done\n"
                    msg += f"• Còn lại: `{int(r['pending_total'])}` task\n" # Đã thêm lại vào Discord
                
                if over_est_list:
                    msg += "\n🚨 **CẢNH BÁO VƯỢT ESTIMATE**\n"
                    for item in over_est_list:
                        msg += f"• {item['PIC']}: {item['Task']} (`{item['Actual']}h`/{item['Est']}h)\n" # Đã sửa lỗi thụt lề
                
                requests.post(webhook_url, json={"content": msg})
                st.sidebar.success("Đã gửi báo cáo!")

        # --- BIỂU ĐỒ & DATA ---
        st.plotly_chart(px.bar(pic_stats, x='PIC', y=['active_real', 'total_est'], barmode='group'), use_container_width=True)
        st.dataframe(df_team[['Userstory/Todo', 'State', 'PIC', 'Estimate Dev', 'Start_time']], use_container_width=True)

    else:
        st.error("Không tìm thấy hàng tiêu đề 'Userstory/Todo'.")
except Exception as e:
    st.error(f"Lỗi hệ thống: {e}")
