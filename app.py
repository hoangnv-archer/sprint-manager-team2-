import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timezone, timedelta

# --- 1. CỐ ĐỊNH MÚI GIỜ VIỆT NAM ---
VN_TZ = timezone(timedelta(hours=7))

def get_actual_hours(start_val):
    if pd.isna(start_val) or str(start_val).lower() in ['none', '']:
        return 0
    try:
        # Ép kiểu datetime từ cột Start-time
        start_dt = pd.to_datetime(start_val)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=VN_TZ)
        
        now_vn = datetime.now(VN_TZ)
        diff = now_vn - start_dt
        return diff.total_seconds() / 3600 
    except:
        return 0

st.set_page_config(page_title="Sprint Dashboard Final", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1llUlTDfR413oZelu-AoMsC0lEzHqXOkB4SCwc_4zmAo/edit?pli=1&gid=982443592#gid=982443592"

try:
    df_raw = conn.read(spreadsheet=URL, header=None, ttl=0)
    header_idx = next((i for i, row in df_raw.iterrows() if "Userstory/Todo" in row.values), None)
            
    if header_idx is not None:
        df = conn.read(spreadsheet=URL, skiprows=header_idx, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]

        # Fix số liệu: Xử lý dấu phẩy cho Estimate và Real
        for col in ['Estimate Dev', 'Real']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '.').replace('None', '0')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # --- ĐỊNH DANH CHÍNH XÁC CỘT CỦA BẠN ---
        T_COL = 'Start-time' 
        
        if T_COL not in df.columns:
            st.error(f"⚠️ Không tìm thấy cột '{T_COL}'. Vui lòng kiểm tra lại tên cột trên Google Sheets.")
            st.stop()

        df['State_Clean'] = df['State'].fillna('None').str.strip().str.lower()
        valid_pics = ['Tài', 'Dương', 'QA', 'Quân', 'Phú', 'Thịnh', 'Đô', 'Tùng', 'Anim', 'Thắng VFX']
        df_team = df[df['PIC'].isin(valid_pics)].copy()

        # --- 2. LOGIC CẢNH BÁO LỐ GIỜ (31 PHÚT > 6 PHÚT) ---
        over_est_list = []
        for _, row in df_team.iterrows():
            if 'progress' in row['State_Clean']:
                actual_h = get_actual_hours(row[T_COL])
                est_h = float(row['Estimate Dev'])
                
                if est_h > 0 and actual_h > est_h:
                    over_est_list.append({
                        "PIC": row['PIC'], 
                        "Task": row['Userstory/Todo'], 
                        "Thực tế": f"{round(actual_h * 60)} phút", 
                        "Dự kiến": f"{round(est_h * 60)} phút"
                    })

        st.title("🚀 Sprint Dashboard - Hệ thống cảnh báo lố giờ")

        # HIỂN THỊ CẢNH BÁO ĐỎ
        if over_est_list:
            st.error(f"🚨 PHÁT HIỆN {len(over_est_list)} TASK LÀM QUÁ GIỜ DỰ KIẾN!")
            st.table(pd.DataFrame(over_est_list))
        else:
            st.success("✅ Mọi task In Progress hiện tại đều đang ổn.")

        # --- 3. THỐNG KÊ PIC & TASK TỒN ĐỌNG (PULL TÍNH NĂNG CŨ) ---
        pic_stats = df_team.groupby('PIC').agg(
            total=('Userstory/Todo', 'count'),
            done=('State_Clean', lambda x: x.isin(['done', 'cancel']).sum()),
            doing=('State_Clean', lambda x: x.str.contains('progress').sum()),
            est_total=('Estimate Dev', 'sum'),
            real_total=('Real', 'sum')
        ).reset_index()
        
        # Task tồn đọng = Tất cả task chưa Done hoặc Cancel
        pic_stats['pending'] = pic_stats['total'] - pic_stats['done']
        pic_stats['percent'] = (pic_stats['done'] / pic_stats['total'] * 100).fillna(0).round(1)

        st.subheader("👤 Trạng thái chi tiết theo PIC")
        cols = st.columns(5)
        for i, row in pic_stats.iterrows():
            with cols[i % 5]:
                st.markdown(f"#### **{row['PIC']}**")
                st.metric("Tiến độ", f"{row['percent']}%")
                st.write(f"✅ Xong: {int(row['done'])} | 🚧 Đang làm: {int(row['doing'])}")
                st.write(f"⏳ **Tồn đọng: {int(row['pending'])}**")
                st.progress(min(row['percent']/100, 1.0))
                st.divider()

        # Biểu đồ so sánh thời gian
        st.plotly_chart(px.bar(pic_stats, x='PIC', y=['est_total', 'real_total'], barmode='group', title="Estimate vs Real (Giờ)"), use_container_width=True)

        # 4. GỬI DISCORD
        st.sidebar.subheader("📢 Discord Settings")
        webhook_url = st.sidebar.text_input("Webhook URL:", type="password")
        if st.sidebar.button("📤 Gửi báo cáo chi tiết"):
            if webhook_url:
                msg = "📊 **SPRINT STATUS REPORT**\n"
                for _, r in pic_stats.iterrows():
                    msg += f"👤 **{r['PIC']}**: `{r['percent']}%` (Tồn: {int(r['pending'])})\n"
                if over_est_list:
                    msg += "\n🚨 **CẢNH BÁO LỐ GIỜ:**\n"
                    for item in over_est_list:
                        msg += f"🔥 `{item['PIC']}` lố: {item['Task']} ({item['Thực tế']}/{item['Dự kiến']})\n"
                requests.post(webhook_url, json={"content": msg})
                st.sidebar.success("Đã gửi báo cáo thành công!")

        # 5. BẢNG CHI TIẾT
        st.subheader("📋 Chi tiết danh sách Task")
        st.dataframe(df_team[['Userstory/Todo', 'State', 'PIC', 'Estimate Dev', 'Real', T_COL]], use_container_width=True)

    else:
        st.error("Không tìm thấy hàng tiêu đề 'Userstory/Todo'.")
except Exception as e:
    st.error(f"Lỗi hệ thống: {e}")
