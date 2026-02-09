import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime

st.set_page_config(page_title="Sprint Dashboard", layout="wide")

# --- HÀM TÍNH THỜI GIAN THỰC TẾ (Đơn giản để bắt lỗi lố phút) ---
def get_actual_hours(start_dt):
    if pd.isna(start_dt):
        return 0
    now = datetime.now()
    duration = now - start_dt
    return max(0, duration.total_seconds() / 3600) # Quy đổi ra giờ thập phân

conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1llUlTDfR413oZelu-AoMsC0lEzHqXOkB4SCwc_4zmAo/edit?pli=1&gid=982443592#gid=982443592"

try:
    raw_df = conn.read(spreadsheet=URL, header=None, ttl=0)
    header_idx = next((i for i, row in raw_df.iterrows() if "Userstory/Todo" in row.values), None)
            
    if header_idx is not None:
        df = conn.read(spreadsheet=URL, skiprows=header_idx, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]

        # 1. Xử lý dấu phẩy và chuyển đổi số
        for col in ['Estimate Dev', 'Real']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '.').replace('None', '0')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # 2. Xử lý Start_time (Lấy từ cột I)
        start_col = next((c for c in df.columns if "start" in c.lower()), None)
        df['Start_DT'] = pd.to_datetime(df[start_col], errors='coerce') if start_col else pd.NaT
        
        df['State_Clean'] = df['State'].fillna('None').str.strip().str.lower()
        valid_pics = ['Tài', 'Dương', 'QA', 'Quân', 'Phú', 'Thịnh', 'Đô', 'Tùng', 'Anim', 'Thắng VFX']
        df_team = df[df['PIC'].isin(valid_pics)].copy()

        # 3. LOGIC CẢNH BÁO (So sánh trực tiếp thời gian trôi qua)
        over_est_list = []
        for _, row in df_team.iterrows():
            if 'progress' in row['State_Clean'] and not pd.isna(row['Start_DT']):
                actual_h = get_actual_hours(row['Start_DT'])
                est_h = float(row['Estimate Dev'])
                
                # Nếu thời gian trôi qua (ví dụ 16p = 0.26h) > Estimate (6p = 0.1h)
                if est_h > 0 and actual_h > est_h:
                    over_est_list.append({
                        "PIC": row['PIC'], 
                        "Task": row['Userstory/Todo'], 
                        "Thực tế (h)": round(actual_h, 2), 
                        "Dự kiến (h)": est_h
                    })

        st.title("🚀 Sprint Workload Analyzer")

        # Hiển thị bảng cảnh báo
        if over_est_list:
            st.error(f"🚨 PHÁT HIỆN {len(over_est_list)} TASK VƯỢT GIỜ DỰ KIẾN!")
            st.table(pd.DataFrame(over_est_list))
        else:
            st.success("✅ Mọi task đều đang trong tiến độ (hoặc chưa đủ dữ liệu Start_time).")

        # --- PHỤC HỒI CÁC TÍNH NĂNG CŨ ---
        pic_stats = df_team.groupby('PIC').agg(
            total=('Userstory/Todo', 'count'),
            done=('State_Clean', lambda x: x.isin(['done', 'cancel']).sum()),
            doing=('State_Clean', lambda x: x.str.contains('progress').sum())
        ).reset_index()
        pic_stats['percent'] = (pic_stats['done'] / pic_stats['total'] * 100).fillna(0).round(1)

        # Hiển thị Metrics PIC
        cols = st.columns(5)
        for i, row in pic_stats.iterrows():
            with cols[i % 5]:
                st.metric(row['PIC'], f"{row['percent']}%", f"Làm: {int(row['doing'])}")
                st.progress(min(row['percent']/100, 1.0))

        # --- GỬI DISCORD ---
        st.sidebar.subheader("📢 Discord Report")
        webhook_url = st.sidebar.text_input("Webhook URL:", type="password")
        if st.sidebar.button("📤 Gửi báo cáo"):
            if webhook_url:
                msg = "📊 **SPRINT REPORT**\n"
                for _, r in pic_stats.iterrows():
                    msg += f"👤 **{r['PIC']}**: `{r['percent']}%` xong\n"
                
                if over_est_list:
                    msg += "\n🚨 **CẢNH BÁO VƯỢT ESTIMATE:**\n"
                    for item in over_est_list:
                        msg += f"🔥 `{item['PIC']}` lố: **{item['Task']}** (`{item['Thực tế (h)']}h`/{item['Dự kiến (h)']}h)\n"
                
                requests.post(webhook_url, json={"content": msg})
                st.sidebar.success("Đã gửi!")

        st.subheader("📋 Chi tiết danh sách")
        st.dataframe(df_team[['Userstory/Todo', 'State', 'PIC', 'Estimate Dev', 'Start_DT']], use_container_width=True)

    else:
        st.error("Không tìm thấy hàng 'Userstory/Todo'.")
except Exception as e:
    st.error(f"Lỗi: {e}")
