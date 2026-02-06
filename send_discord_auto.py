import requests
import pandas as pd
import os
import gspread
import json

# Lấy Secrets từ GitHub
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
SHEET_URL = os.environ.get("GSHEETS_URL")
SERVICE_ACCOUNT_JSON = os.environ.get("GCP_SERVICE_ACCOUNT")

def get_report():
    try:
        # 1. Xác thực với Google Sheets bằng Service Account
        creds_dict = json.loads(SERVICE_ACCOUNT_JSON)
        gc = gspread.service_account_from_dict(creds_dict)
        
        # 2. Mở Spreadsheet qua URL
        sh = gc.open_by_url(SHEET_URL)
        worksheet = sh.get_worksheet(0) # Mở sheet đầu tiên (hoặc điền tên sheet)
        
        # 3. Lấy toàn bộ dữ liệu và chuyển thành DataFrame
        data = worksheet.get_all_values()
        df_all = pd.DataFrame(data)
        
        # 4. Tìm hàng tiêu đề 'Userstory/Todo' (giống logic cũ)
        header_idx = df_all[df_all.eq("Userstory/Todo").any(axis=1)].index[0]
        df = pd.DataFrame(data[header_idx + 1:], columns=data[header_idx])
        
        # 5. Xử lý dữ liệu
        df.columns = [str(c).strip() for c in df.columns]
        df['State_Clean'] = df['State'].fillna('None').replace('', 'None').str.strip().str.lower()
        
        valid_pics = ['Tài', 'Dương', 'QA', 'Quân', 'Phú', 'Thịnh', 'Đô', 'Tùng', 'Anim', 'Thắng VFX']
        df_team = df[df['PIC'].isin(valid_pics)].copy()

        # Tính toán
        pic_stats = df_team.groupby('PIC').agg(
            total=('Userstory/Todo', 'count'),
            done=('State_Clean', lambda x: x.isin(['done', 'cancel']).sum()),
            ip=('State_Clean', lambda x: (x == 'in progress').sum()),
            none=('State_Clean', lambda x: (x == 'none').sum())
        ).reset_index()

        # Soạn tin nhắn
        msg = "⏰ **BÁO CÁO TỰ ĐỘNG (8:30 AM)** ☀️\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━\n"
        for _, r in pic_stats.iterrows():
            p = (r['done'] / int(r['total']) * 100) if int(r['total']) > 0 else 0
            icon = "🟢" if p >= 80 else "🟡"
            msg += f"{icon} **{r['PIC']}**: `{p:.1f}%` | Xong: `{int(r['done'])}` | IP: `{int(r['ip'])}` \n"
        
        # 6. Gửi Discord
        if WEBHOOK_URL:
            res = requests.post(WEBHOOK_URL, json={"content": msg})
            print(f"✅ Đã gửi báo cáo! Status: {res.status_code}")
        else:
            print("❌ Lỗi: Thiếu DISCORD_WEBHOOK")

    except Exception as e:
        print(f"❌ Lỗi xử lý: {e}")

if __name__ == "__main__":
    get_report()
