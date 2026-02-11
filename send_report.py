import pandas as pd
import requests
from datetime import datetime, timezone, timedelta

# --- CẤU HÌNH ---
VN_TZ = timezone(timedelta(hours=7))
TG_TOKEN = "8535993887:AAFDNSLk9KRny99kQrAoQRbgpKJx_uHbkpw"
TG_CHAT_ID = "-1002102856307"
TG_TOPIC_ID = 18251
# Sử dụng link export CSV chuẩn
SHEET_URL = "https://docs.google.com/spreadsheets/d/1hentY_r7GNVwJWM3wLT7LsA3PrXQidWnYahkfSwR9Kw/export?format=csv&gid=982443592"

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID, 
        "message_thread_id": TG_TOPIC_ID, 
        "text": message, 
        "parse_mode": "HTML", 
        "disable_web_page_preview": True
    }
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        print(f"❌ LỖI TELEGRAM: {response.text}")
    else:
        print("✅ TIN NHẮN ĐÃ GỬI THÀNH CÔNG!")

def run_job():
    try:
        # 1. Đọc dữ liệu thô để xác định vị trí header
        df_raw = pd.read_csv(SHEET_URL, header=None)
        
        header_row_idx = None
        for i, row in df_raw.iterrows():
            # Tìm hàng có chứa từ khóa quan trọng nhất
            row_values = [str(val).strip() for val in row.values]
            if "Userstory/Todo" in row_values:
                header_row_idx = i
                break
        
        if header_row_idx is None:
            print("❌ LỖI: Không tìm thấy hàng chứa tiêu đề 'Userstory/Todo'")
            return

        # 2. Đọc lại dữ liệu từ hàng header đã tìm thấy
        df = pd.read_csv(SHEET_URL, skiprows=header_row_idx)
        df.columns = [str(c).strip() for c in df.columns]

        # 3. Xác định các cột linh hoạt
        col_state = next((c for c in df.columns if "state" in c.lower()), None)
        col_pic = next((c for c in df.columns if "pic" in c.lower()), None)
        col_est = next((c for c in df.columns if "estimate" in c.lower()), None)
        col_real = next((c for c in df.columns if "real" in c.lower()), None)
        col_task = "Userstory/Todo"

        if not col_state or not col_pic:
            print(f"❌ LỖI: Thiếu cột State hoặc PIC. Cột hiện có: {list(df.columns)}")
            return

        # 4. Xử lý định dạng số cho Estimate và Real
        for col in [col_est, col_real]:
            if col:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        
        # 5. Lọc dữ liệu Team
        df['State_Clean'] = df[col_state].fillna('None').str.strip().str.lower()
        valid_pics = ['Chuân', 'Việt', 'Thắng', 'QA', 'Mai', 'Hải Anh', 'Thuật', 'Hiếu']
        df_team = df[df[col_pic].isin(valid_pics)].copy()

        if df_team.empty:
            print("❌ LỖI: Không có dữ liệu của thành viên nào trong danh sách PIC.")
            return

        # 6. Thống kê
        pic_stats = df_team.groupby(col_pic).agg(
            total=(col_task, 'count'),
            done=('State_Clean', lambda x: x.isin(['done', 'cancel', 'dev done']).sum()),
            doing=('State_Clean', lambda x: x.str.contains('progress').sum()),
            est_sum=(col_est, 'sum') if col_est else (col_task, lambda x: 0),
            real_sum=(col_real, 'sum') if col_real else (col_task, lambda x: 0)
        ).reset_index()
        
        pic_stats.columns = ['PIC', 'total', 'done', 'doing', 'est_sum', 'real_sum']
        pic_stats['pending'] = pic_stats['total'] - pic_stats['done']
        pic_stats['percent'] = (pic_stats['done'] / pic_stats['total'] * 100).fillna(0).round(1)

        # 7. Tạo nội dung tin nhắn HTML
        now_str = datetime.now(VN_TZ).strftime('%d/%m %H:%M')
        msg = f"<b>🤖 AUTO REPORT ({now_str})</b>\n"
        msg += "━━━━━━━━━━━━━━━━━━\n\n"
        
        PIC_EMOJIS = {
            "Chuân": "🔧", "Việt": "💊", "Thắng": "✏️", "QA": "🔍",
            "Mai": "🌟", "Hải Anh": "✨", "Thuật": "👾", "Hiếu": "👽"
        }

        for _, r in pic_stats.iterrows():
            emoji = PIC_EMOJIS.get(r['PIC'], "👤")
            msg += f"{emoji} <b>{r['PIC']}</b>\n"
            msg += f"┣ Tiến độ: <b>{r['percent']}%</b> \n"
            msg += f"┣ ✅ Xong: {int(r['done'])} | 🚧 Đang: {int(r['doing'])}\n"
            msg += f"┣ ⏳ <b>Tồn: {int(r['pending'])} task</b>\n"
            msg += f"┗ ⏱ Giờ: {round(r['real_sum'], 1)}h / {round(r['est_sum'], 1)}h\n"
            msg += "────────────────
