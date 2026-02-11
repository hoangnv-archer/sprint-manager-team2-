import pandas as pd
import requests
from datetime import datetime, timezone, timedelta

# --- CẤU HÌNH ---
VN_TZ = timezone(timedelta(hours=7))
TG_TOKEN = "8535993887:AAFDNSLk9KRny99kQrAoQRbgpKJx_uHbkpw"
TG_CHAT_ID = "-1002102856307"
TG_TOPIC_ID = 18251
SHEET_URL = "https://docs.google.com/spreadsheets/d/1hentY_r7GNVwJWM3wLT7LsA3PrXQidWnYahkfSwR9Kw/gviz/tq?tqx=out:csv&gid=982443592"

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID, 
        "message_thread_id": TG_TOPIC_ID, 
        "text": message, 
        "parse_mode": "HTML", # Chuyển sang HTML để tránh lỗi Markdown ký tự đặc biệt
        "disable_web_page_preview": True
    }
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        print(f"❌ LỖI TELEGRAM: {response.text}")
    else:
        print("✅ TIN NHẮN ĐÃ GỬI THÀNH CÔNG!")

def run_job():
    try:
        df_raw = pd.read_csv(SHEET_URL, header=None)
        
        # Tìm hàng chứa tiêu đề "Userstory/Todo"
        header_row_idx = None
        for i, row in df_raw.iterrows():
            if "Userstory/Todo" in row.values:
                header_row_idx = i
                break
        
        if header_row_idx is None:
            print("❌ LỖI: Không tìm thấy cột 'Userstory/Todo' trong Sheet")
            return
        df = pd.read_csv(SHEET_URL, skiprows=header_row_idx)
        df.columns = [str(c).strip() for c in df.columns]
        state_col = next((c for c in df.columns if "state" in c.lower()), None)
        pic_col = next((c for c in df.columns if "pic" in c.lower()), None)
        task_col = "Userstory/Todo"

        if not state_col or not pic_col:
            print(f"❌ LỖI: Không tìm thấy cột State hoặc PIC. Các cột hiện có: {list(df.columns)}")
            return
        for col in ['Estimate Dev', 'Real']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        
        df['State_Clean'] = df['State'].fillna('None').str.strip().str.lower()
        valid_pics = ['Chuân', 'Việt', 'Thắng', 'QA', 'Mai', 'Hải Anh', 'Thuật', 'Hiếu']
        df_team = df[df['PIC'].isin(valid_pics)].copy()

        pic_stats = df_team.groupby('PIC').agg(
            total=('Userstory/Todo', 'count'),
            done=('State_Clean', lambda x: x.isin(['done', 'cancel', 'dev done']).sum()),
            doing=('State_Clean', lambda x: x.str.contains('progress').sum()),
            est_sum=('Estimate Dev', 'sum'),
            real_sum=('Real', 'sum')
        ).reset_index()
        pic_stats['pending'] = pic_stats['total'] - pic_stats['done']
        pic_stats['percent'] = (pic_stats['done'] / pic_stats['total'] * 100).fillna(0).round(1)

        now_str = datetime.now(VN_TZ).strftime('%d/%m %H:%M')
        # Dùng thẻ HTML để thay thế Markdown
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
            msg += "──────────────────\n"
        
        send_telegram_msg(msg)
    except Exception as e:
        print(f"❌ LỖI HỆ THỐNG: {e}")

if __name__ == "__main__":
    run_job()
