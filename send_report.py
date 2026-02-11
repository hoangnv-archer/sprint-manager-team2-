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
        "parse_mode": "Markdown", 
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload)

def run_job():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = [str(c).strip() for c in df.columns]
        
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
        msg = f"🤖 *AUTO REPORT* ({now_str})\n"
        msg += "━━━━━━━━━━━━━━━━━━\n\n"
        
        PIC_EMOJIS = {
            "Chuân": "🔧", "Việt": "💊", "Thắng": "✏️", "QA": "🔍",
            "Mai": "🌟", "Hải Anh": "✨", "Thuật": "👾", "Hiếu": "👽"
        }

        for _, r in pic_stats.iterrows():
            emoji = PIC_EMOJIS.get(r['PIC'], "👤")
            msg += f"{emoji} *{r['PIC']}*\n"
            msg += f"┣ Tiến độ: **{r['percent']}%** \n"
            msg += f"┣ ✅ Xong: `{int(r['done'])}` | 🚧 Đang: `{int(r['doing'])}`\n"
            msg += f"┣ ⏳ *Tồn: {int(r['pending'])} task*\n"
            msg += f"┗ ⏱ Giờ: `{round(r['real_sum'], 1)}h / {round(r['est_sum'], 1)}h`\n"
            msg += "──────────────────\n"
        
        send_telegram_msg(msg)
        print("Success")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_job()
