import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timezone, timedelta

# --- 1. CỐ ĐỊNH MÚI GIỜ VIỆT NAM ---
VN_TZ = timezone(timedelta(hours=7))

def get_actual_hours(start_val):
    if pd.isna(start_val) or str(start_val).strip().lower() in ['none', '']:
        return 0
    try:
        # Ép kiểu datetime cho định dạng 2026-09-02 16:14:09
        start_dt = pd.to_datetime(start_val)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=VN_TZ)
        now_vn = datetime.now(VN_TZ)
        diff = now_vn - start_dt
        return max(0, diff.total_seconds() / 3600)
    except:
        return 0

TG_TOKEN = "8535993887:AAFDNSLk9KRny99kQrAoQRbgpKJx_uHbkpw" 
TG_CHAT_ID = "-1002102856307"  # Đảm bảo có dấu trừ nếu là Group
TG_TOPIC_ID = 18251

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID, 
        "message_thread_id": TG_TOPIC_ID, # Gửi đúng vào topic này
        "text": message, 
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        return {"ok": False, "description": str(e)}

st.set_page_config(page_title="Team 2 Sprint Dashboard", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- THAY LINK GOOGLE SHEET TEAM 2 TẠI ĐÂY ---
URL_TEAM_2 = "https://docs.google.com/spreadsheets/d/1hentY_r7GNVwJWM3wLT7LsA3PrXQidWnYahkfSwR9Kw/edit?pli=1&gid=982443592#gid=982443592"

try:
    df_raw = conn.read(spreadsheet=URL_TEAM_2, header=None, ttl=0)
    header_idx = next((i for i, row in df_raw.iterrows() if "Userstory/Todo" in row.values), None)
            
    if header_idx is not None:
        df = conn.read(spreadsheet=URL_TEAM_2, skiprows=header_idx, ttl=0)
        df.columns = [str(c).strip() for c in df.columns]

        # Tự động tìm cột Start dựa trên từ khóa để tránh lỗi 'not in index'
        t_col = next((c for c in df.columns if "start" in c.lower()), None)
        
        # Chuẩn hóa dữ liệu số
        for col in ['Estimate Dev', 'Real']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '.').replace('None', '0')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        df['State_Clean'] = df['State'].fillna('None').str.strip().str.lower()
        
        # --- CẬP NHẬT DANH SÁCH PIC CHO TEAM 2 ---
        valid_pics = ['Chuân', 'Việt', 'Thắng', 'QA', 'Mai', 'Hải Anh', 'Thuật', 'Hiếu'] # Thay bằng tên PIC thực tế của Team 2
        df_team = df[df['PIC'].isin(valid_pics)].copy()

        # 2. LOGIC CẢNH BÁO LỐ GIỜ
        over_est_list = []
        if t_col:
            for _, row in df_team.iterrows():
                if 'progress' in row['State_Clean']:
                    actual_h = get_actual_hours(row[t_col])
                    est_h = float(row['Estimate Dev'])
                    if est_h > 0 and actual_h > est_h:
                        over_est_list.append({
                            "PIC": row['PIC'], "Task": row['Userstory/Todo'], 
                            "Thực tế": f"{round(actual_h * 60)}p", "Dự kiến": f"{round(est_h * 60)}p"
                        })

        st.title("📊 Team 2 Sprint Performance")

        # Hiển thị Cảnh báo Đỏ (UI quan trọng)
        if over_est_list:
            st.error(f"🚨 PHÁT HIỆN {len(over_est_list)} TASK LÀM QUÁ DỰ KIẾN!")
            st.table(pd.DataFrame(over_est_list))

        # --- 3. KHÔI PHỤC TOÀN BỘ GIAO DIỆN METRICS ---
        pic_stats = df_team.groupby('PIC').agg(
            total=('Userstory/Todo', 'count'),
            done=('State_Clean', lambda x: x.isin(['done', 'cancel']).sum()),
            doing=('State_Clean', lambda x: x.str.contains('progress').sum()),
            est_sum=('Estimate Dev', 'sum'),
            real_sum=('Real', 'sum')
        ).reset_index()
        pic_stats['pending'] = pic_stats['total'] - pic_stats['done']
        pic_stats['percent'] = (pic_stats['done'] / pic_stats['total'] * 100).fillna(0).round(1)

        st.subheader("👤 Trạng thái chi tiết PIC")
        cols = st.columns(min(len(pic_stats), 5))
        for i, row in pic_stats.iterrows():
            with cols[i % 5]:
                st.markdown(f"### **{row['PIC']}**")
                st.metric("Hoàn thành", f"{row['percent']}%")
                st.write(f"✅ Xong: {int(row['done'])} | 🚧 Đang làm: {int(row['doing'])}")
                st.write(f"⏳ **Tồn đọng: {int(row['pending'])} task**")
                st.progress(min(row['percent']/100, 1.0))
                st.divider()

        # BIỂU ĐỒ (UI cũ)
        st.plotly_chart(px.bar(pic_stats, x='PIC', y=['est_sum', 'real_sum'], barmode='group', title="Estimate vs Real (h)"), use_container_width=True)

        # 4. GỬI TELEGRAM TRÊN SIDEBAR
       if st.sidebar.button("📤 Gửi báo cáo vào Topic"):
    # 1. Khởi tạo tiêu đề tin nhắn
            msg = "📊 *TEAM 2 REPORT* \n" + "━" * 15 + "\n"
            
            # 2. Thống kê tiến độ từng PIC
            if not pic_stats.empty:
                for _, r in pic_stats.iterrows():
                    msg += f"👤 *{r['PIC']}*: `{r['percent']}%` (Tồn: {int(r['pending'])})\n"
            else:
                msg += "⚠️ Không có dữ liệu PIC.\n"
        
            # 3. Thống kê lố giờ (Bắt lỗi 16:14 so với 16:45)
            if over_est_list:
                msg += "\n🚨 *CẢNH BÁO LỐ GIỜ:*\n"
                for item in over_est_list:
                    msg += f"🔥 `{item['PIC']}`: {item['Task']} ({item['Thực tế']}/{item['Dự kiến']})\n"
            
            # 4. Thực hiện gửi
            res = send_telegram_msg(msg)
            
            if res.get("ok"):
                st.sidebar.success(f"Đã gửi vào Topic ID: {TG_TOPIC_ID}")
            else:
                st.sidebar.error(f"Lỗi Telegram: {res.get('description')}")
        # 5. BẢNG CHI TIẾT (UI cũ)
        st.subheader("📋 Danh sách Task chi tiết")
        display_cols = ['Userstory/Todo', 'State', 'PIC', 'Estimate Dev', 'Real']
        if t_col: display_cols.append(t_col)
        st.dataframe(df_team[display_cols], use_container_width=True)

    else:
        st.error("Không tìm thấy hàng chứa 'Userstory/Todo'.")
except Exception as e:
    st.error(f"Lỗi: {e}")
