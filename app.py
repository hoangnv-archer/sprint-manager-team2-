import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timezone, timedelta

# --- 1. CẤU HÌNH MÚI GIỜ VIỆT NAM ---
VN_TZ = timezone(timedelta(hours=7))

def get_actual_hours(start_val):
    if pd.isna(start_val) or str(start_val).strip().lower() in ['none', '', 'nat']:
        return 0
    try:
        start_dt = pd.to_datetime(start_val)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=VN_TZ)
        now_vn = datetime.now(VN_TZ)
        diff = now_vn - start_dt
        return diff.total_seconds() / 3600 
    except:
        return 0

def send_telegram_msg(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    return requests.post(url, json=payload)

st.set_page_config(page_title="Team 2 Sprint Analyzer", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- THAY LINK GOOGLE SHEET TEAM 2 TẠI ĐÂY ---
URL_TEAM_2 = "https://docs.google.com/spreadsheets/d/1hentY_r7GNVwJWM3wLT7LsA3PrXQidWnYahkfSwR9Kw/edit?pli=1&gid=982443592#gid=982443592"

try:
    # Đọc dữ liệu tươi (không cache)
    df_raw = conn.read(spreadsheet=URL_TEAM_2, header=None, ttl=0)
    header_idx = next((i for i, row in df_raw.iterrows() if "Userstory/Todo" in row.values), None)
            
    if header_idx is not None:
        df = conn.read(spreadsheet=URL_TEAM_2, skiprows=header_idx, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]

        # Fix số liệu
        for col in ['Estimate Dev', 'Real']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '.').replace('None', '0')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Cột thời gian của bạn
        T_COL = 'Start-time'
        df['State_Clean'] = df['State'].fillna('None').str.strip().str.lower()
        
        # Danh sách PIC (Hãy sửa đúng tên thành viên Team 2)
        valid_pics = ['Chuân', 'Việt', 'QA', 'Thắng', 'Mai', 'Hải Anh', 'Hiếu', 'Thuật']
        df_team = df[df['PIC'].isin(valid_pics)].copy()

        # 2. LOGIC CẢNH BÁO LỐ GIỜ
        over_est_list = []
        for _, row in df_team.iterrows():
            if 'progress' in row['State_Clean']:
                actual_h = get_actual_hours(row.get(T_COL))
                est_h = float(row.get('Estimate Dev', 0))
                if est_h > 0 and actual_h > est_h:
                    over_est_list.append({
                        "PIC": row['PIC'], "Task": row['Userstory/Todo'], 
                        "Thực tế": f"{round(actual_h * 60)}p", "Dự kiến": f"{round(est_h * 60)}p"
                    })

        st.title("🚀 Team 2 - Sprint Performance Dashboard")

        # HIỂN THỊ CẢNH BÁO ĐỎ (Tính năng mới)
        if over_est_list:
            st.error(f"🚨 PHÁT HIỆN {len(over_est_list)} TASK VƯỢT GIỜ DỰ KIẾN!")
            st.table(pd.DataFrame(over_est_list))

        # --- 3. KHÔI PHỤC TOÀN BỘ METRICS CŨ ---
        pic_stats = df_team.groupby('PIC').agg(
            total=('Userstory/Todo', 'count'),
            done=('State_Clean', lambda x: x.isin(['done', 'cancel']).sum()),
            doing=('State_Clean', lambda x: x.str.contains('progress').sum()),
            est_sum=('Estimate Dev', 'sum'),
            real_sum=('Real', 'sum')
        ).reset_index()
        pic_stats['pending'] = pic_stats['total'] - pic_stats['done']
        pic_stats['percent'] = (pic_stats['done'] / pic_stats['total'] * 100).fillna(0).round(1)

        st.subheader("👤 Trạng thái PIC & Task Tồn Đọng")
        cols = st.columns(5)
        for i, row in pic_stats.iterrows():
            with cols[i % 5]:
                st.markdown(f"#### **{row['PIC']}**")
                st.metric("Tiến độ", f"{row['percent']}%")
                st.write(f"✅ Xong: {int(row['done'])} | 🚧 Đang làm: {int(row['doing'])}")
                st.write(f"⏳ **Tồn đọng: {int(row['pending'])} task**")
                st.progress(min(row['percent']/100, 1.0))
                st.divider()

        # BIỂU ĐỒ (Tính năng cũ)
        st.plotly_chart(px.bar(pic_stats, x='PIC', y=['est_sum', 'real_sum'], barmode='group', title="So sánh Dự kiến vs Thực tế (Giờ)"), use_container_width=True)

        # 4. CẤU HÌNH TELEGRAM TRÊN SIDEBAR
        st.sidebar.subheader("📢 Telegram Bot")
        tg_token = st.sidebar.text_input("Bot Token:", type="password")
        tg_chat_id = st.sidebar.text_input("Chat ID:")
        
        if st.sidebar.button("📤 Gửi báo cáo Telegram"):
            if tg_token and tg_chat_id:
                msg = "📊 *SPRINT REPORT TEAM 2*\n━━━━━━━━━━━━━━━\n"
                for _, r in pic_stats.iterrows():
                    msg += f"👤 *{r['PIC']}*: `{r['percent']}%` (Tồn: {int(r['pending'])})\n"
                if over_est_list:
                    msg += "\n🚨 *CẢNH BÁO LỐ GIỜ:*\n"
                    for item in over_est_list:
                        msg += f"🔥 `{item['PIC']}` lố: {item['Task']} ({item['Thực tế']}/{item['Dự kiến']})\n"
                
                send_telegram_msg(tg_token, tg_chat_id, msg)
                st.sidebar.success("Đã gửi Telegram!")

        # 5. BẢNG CHI TIẾT
        st.subheader("📋 Danh sách Task chi tiết")
        st.dataframe(df_team[['Userstory/Todo', 'State', 'PIC', 'Estimate Dev', 'Real', T_COL]], use_container_width=True)

    else:
        st.error("Không tìm thấy hàng tiêu đề 'Userstory/Todo'.")
except Exception as e:
    st.error(f"Lỗi: {e}")
