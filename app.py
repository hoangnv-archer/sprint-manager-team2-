import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timezone, timedelta

# --- 1. CỐ ĐỊNH MÚI GIỜ VIỆT NAM ---
VN_TZ = timezone(timedelta(hours=7))

def get_actual_hours(start_val):
    if pd.isna(start_val) or str(start_val).strip().lower() in ['none', '', 'nat']:
        return 0
    try:
        # Chuyển đổi datetime chuẩn
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
URL = "https://docs.google.com/spreadsheets/d/1hentY_r7GNVwJWM3wLT7LsA3PrXQidWnYahkfSwR9Kw/edit?pli=1&gid=982443592#gid=982443592"

# --- LẤY DỮ LIỆU TƯƠI (TTL=0 ĐỂ KHÔNG DÙNG CACHE) ---
try:
    # Đọc thô để tìm Header
    df_raw = conn.read(spreadsheet=URL, header=None, ttl=0)
    
    # Tìm hàng chứa chữ "Userstory/Todo"
    header_idx = next((i for i, row in df_raw.iterrows() if "Userstory/Todo" in row.values), None)
            
    if header_idx is not None:
        # Đọc lại từ hàng tiêu đề
        df = conn.read(spreadsheet=URL, skiprows=header_idx, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]

        # --- PHẦN DEBUG (BẠN XEM DÒNG NÀY TRÊN APP ĐỂ BIẾT TÊN CỘT ĐÚNG) ---
        # st.write("Các cột hệ thống tìm thấy:", list(df.columns)) 

        # Chuẩn hóa số
        for col in ['Estimate Dev', 'Real']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '.').replace('None', '0')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # CỘT THỜI GIAN: Tìm cột "Start-time" hoặc bất kỳ cột nào có chữ "Start"
        t_col = next((c for c in df.columns if "start" in c.lower()), None)
        
        df['State_Clean'] = df['State'].fillna('None').str.strip().str.lower()
        valid_pics = ['Chuân', 'Việt', 'QA', 'Thắng', 'Mai', 'Hải Anh', 'Hiếu', 'Thuật']
        df_team = df[df['PIC'].isin(valid_pics)].copy()

        # --- 2. LOGIC CẢNH BÁO LỐ GIỜ ---
        over_est_list = []
        if t_col:
            for _, row in df_team.iterrows():
                if 'progress' in row['State_Clean']:
                    actual_h = get_actual_hours(row[t_col])
                    est_h = float(row['Estimate Dev'])
                    # Kiểm tra lố giờ (Ví dụ: 31p > 6p)
                    if est_h > 0 and actual_h > est_h:
                        over_est_list.append({
                            "PIC": row['PIC'], 
                            "Task": row['Userstory/Todo'], 
                            "Thực tế": f"{round(actual_h * 60)} phút", 
                            "Dự kiến": f"{round(est_h * 60)} phút"
                        })

        st.title("🚀 Sprint Dashboard & Performance Alert")

        # HIỂN THỊ CẢNH BÁO ĐỎ
        if over_est_list:
            st.error(f"🚨 PHÁT HIỆN {len(over_est_list)} TASK LÀM QUÁ GIỜ DỰ KIẾN!")
            st.table(pd.DataFrame(over_est_list))
        else:
            st.info("💡 Mẹo: Nếu task 'In Progress' lố giờ mà không hiện bảng đỏ, hãy đảm bảo cột 'Start-time' đã điền giờ bắt đầu.")

        # --- 3. THỐNG KÊ PIC & TASK TỒN ĐỌNG ---
        pic_stats = df_team.groupby('PIC').agg(
            total=('Userstory/Todo', 'count'),
            done=('State_Clean', lambda x: x.isin(['done', 'cancel']).sum()),
            doing=('State_Clean', lambda x: x.str.contains('progress').sum()),
            est_total=('Estimate Dev', 'sum'),
            real_total=('Real', 'sum')
        ).reset_index()
        
        # Tồn đọng = Tổng - Done - Cancel
        pic_stats['pending'] = pic_stats['total'] - pic_stats['done']
        pic_stats['percent'] = (pic_stats['done'] / pic_stats['total'] * 100).fillna(0).round(1)

        st.subheader("👤 Trạng thái chi tiết từng PIC")
        cols = st.columns(5)
        for i, row in pic_stats.iterrows():
            with cols[i % 5]:
                st.markdown(f"#### **{row['PIC']}**")
                st.metric("Tiến độ", f"{row['percent']}%")
                st.write(f"✅ Xong: {int(row['done'])} | 🚧 Đang làm: {int(row['doing'])}")
                st.write(f"⏳ **Tồn đọng: {int(row['pending'])} task**")
                st.progress(min(row['percent']/100, 1.0))
                st.divider()

        # Biểu đồ Bar Chart
        st.plotly_chart(px.bar(pic_stats, x='PIC', y=['est_total', 'real_total'], barmode='group', title="Estimate vs Real (Giờ)"), use_container_width=True)

        # 4. GỬI DISCORD
        st.sidebar.subheader("📢 Discord Webhook")
        webhook_url = st.sidebar.text_input("Webhook URL:", type="password")
        if st.sidebar.button("📤 Gửi báo cáo"):
            if webhook_url:
                msg = "📊 **SPRINT PROGRESS REPORT**\n"
                for _, r in pic_stats.iterrows():
                    msg += f"👤 **{r['PIC']}**: `{r['percent']}%` (Tồn: {int(r['pending'])})\n"
                if over_est_list:
                    msg += "\n🚨 **CẢNH BÁO LỐ GIỜ:**\n"
                    for item in over_est_list:
                        msg += f"🔥 `{item['PIC']}` lố: {item['Task']} ({item['Thực tế']}/{item['Dự kiến']})\n"
                requests.post(webhook_url, json={"content": msg})
                st.sidebar.success("Đã gửi!")

        st.subheader("📋 Bảng chi tiết Task")
        show_cols = ['Userstory/Todo', 'State', 'PIC', 'Estimate Dev', 'Real']
        if t_col: show_cols.append(t_col)
        st.dataframe(df_team[show_cols], use_container_width=True)

    else:
        st.error("Lỗi: Không tìm thấy hàng chứa 'Userstory/Todo' trên Sheet.")
except Exception as e:
    st.error(f"Lỗi hệ thống: {e}")
