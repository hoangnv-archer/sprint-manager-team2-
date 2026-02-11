import pandas as pd
import requests
from datetime import datetime, timezone, timedelta

# --- CẤU HÌNH ---
VN_TZ = timezone(timedelta(hours=7))
TG_TOKEN = "8535993887:AAFDNSLk9KRny99kQrAoQRbgpKJx_uHbkpw"
TG_CHAT_ID = "-1002102856307"
TG_TOPIC_ID = 18251
# Link export CSV chuẩn của Google Sheets
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
        # 1. Đọc dữ liệu thô và tìm hàng tiêu đề
        df_raw = pd.read_csv(SHEET_URL, header=None)
        header_idx = None
        for i, row in df_raw.iterrows():
            if "Userstory/Todo" in [str(x).strip() for x in row.values]:
                header_idx = i
                break
        
        if header_idx is None:
            print("❌ LỖI: Không tìm thấy cột 'Userstory/Todo'")
            return

        # 2. Đọc lại dữ liệu chuẩn
        df = pd.read_csv(SHEET_URL, skiprows=header_idx)
        df.columns = [str(c).strip() for c in df.columns]

        # 3. Tìm cột linh hoạt
        col_pic = next((c for c in df.columns if "pic" in c.lower()), None)
        col_state = next((c for c in df.columns if "state" in c.lower()), None)
        col_est = next((c for c in df.columns if "estimate" in c.lower()), None)
        col_real = next((c for c in df.columns if "real" in c.lower()), None)
        
        if not col_pic or not col_state:
            print(f"❌ LỖI: Thiếu cột PIC hoặc State. Cột hiện tại: {list(df.columns)}")
            return

        # 4. Xử lý số liệu
        for c in [col_est, col_real]:
            if c:
                df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

        # 5. Lọc và Thống kê
        valid_pics = ['Chuân', 'Việt', 'Thắng', 'QA', 'Mai', 'Hải Anh', 'Thuật', 'Hiếu']
        df_team = df[df[col_pic].isin(valid_pics)].copy()
        df_team['State_Clean'] = df_team[col_state].fillna('None').str.strip().str.lower()

        pic_stats = df_team.groupby(col_pic).agg(
            total=('Userstory/Todo', 'count'),
            done=('State_Clean', lambda x: x.isin(['done', 'cancel', 'dev done']).sum()),
            doing=('State_Clean', lambda x: x.str.contains('progress').sum()),
            est_sum=(col_est, 'sum') if col_est else ('Userstory/Todo', lambda x: 0),
            real_sum=(col_real, 'sum') if col_real else ('Userstory/Todo', lambda x: 0)
        ).reset_index()

        pic_stats.columns = ['PIC', 'total', 'done', 'doing', 'est_sum', 'real_sum']
        pic_stats['percent'] = (pic_stats['done'] / pic_stats['total'] * 100).fillna(0).round(1)

        # 6. Xây dựng tin nhắn
        now_str = datetime.now(VN_TZ).strftime('%d/%m %H:%M')
        msg = f"<b>🤖 AUTO REPORT ({now_str})</b>\n"
        msg = msg + "━━━━━━━━━━━━━━━━━━\n\n"
        
        PIC_EMOJIS = {
            "Chuân": "🔧", "Việt": "💊", "Thắng": "✏️", "QA": "🔍",
            "Mai": "🌟", "Hải Anh": "✨", "Thuật": "👾", "Hiếu": "👽"
        }

        for _, r in pic_stats.iterrows():
            emoji = PIC_EMOJIS.get(r['PIC'], "👤")
            msg = msg + f"{emoji} <b>{r['PIC']}</b>\n"
            msg = msg + f"┣ Tiến độ: <b>{r['percent']}%</b>\n"
            msg = msg + f"┣ ✅ Xong: {int(r['done'])} | 🚧 Đang: {int(r['doing'])}\n"
            msg = msg + f"┗ ⏱ Giờ: {round(r['real_sum'], 1)}h / {round(r['est_sum'], 1)}h\n"
            msg = msg + "──────────────────\n"
        
        send_telegram_msg(msg)
    except Exception as e:
        print(f"❌ LỖI HỆ THỐNG: {str(e)}")

if __name__ == "__main__":
    run_job()
