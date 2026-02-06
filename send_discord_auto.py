import requests
import pandas as pd
import os
import gspread
import json

# Cấu hình ID Discord (Thay thế số ID thực tế của bạn vào đây)
DISCORD_TAGS = {
    'TEAM_ROLE': '<@&1387617307190366329>' # ID của nhóm/role
}

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
SHEET_URL = os.environ.get("GSHEETS_URL")
SERVICE_ACCOUNT_JSON = os.environ.get("GCP_SERVICE_ACCOUNT")

def get_report():
    try:
        # 1. Xác thực và lấy dữ liệu
        creds_dict = json.loads(SERVICE_ACCOUNT_JSON)
        gc = gspread.service_account_from_dict(creds_dict)
        sh = gc.open_by_url(SHEET_URL)
        worksheet = sh.get_worksheet(0)
        data = worksheet.get_all_values()
        
        # 2. Xử lý DataFrame
        df_full = pd.DataFrame(data)
        header_idx = df_full[df_full.eq("Userstory/Todo").any(axis=1)].index[0]
        df = pd.DataFrame(data[header_idx + 1:], columns=data[header_idx])
        
        df.columns = [str(c).strip() for c in df.columns]
        df['State_Clean'] = df['State'].str.strip().str.lower().replace(['', None], 'none')
        
        valid_pics = ['Tài', 'Dương', 'QA', 'Quân', 'Phú', 'Thịnh', 'Đô', 'Tùng', 'Anim', 'Thắng VFX']
        df_team = df[df['PIC'].isin(valid_pics)].copy()

        # 3. Tính toán
        pic_stats = df_team.groupby('PIC').agg(
            total=('Userstory/Todo', 'count'),
            done=('State_Clean', lambda x: x.isin(['done', 'cancel']).sum()),
            ip=('State_Clean', lambda x: (x == 'in progress').sum()),
            none=('State_Clean', lambda x: (x == 'none').sum())
        ).reset_index()

        # 4. Soạn tin nhắn có TAG
        # Tag cả nhóm ở đầu tin nhắn
        msg = f"🔔 **SÁNG NAY CÓ GÌ?** {DISCORD_TAGS.get('TEAM_ROLE')}\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━\n"
        
        for _, r in pic_stats.iterrows():
            total = int(r['total'])
            done = int(r['done'])
            none = int(r['none'])
            progress = (done / total * 100) if total > 0 else 0
            
            # Lấy tag cá nhân nếu có trong danh sách
            mention = DISCORD_TAGS.get(r['PIC'], f"**{r['PIC']}**")
            
            icon = "🟢" if progress >= 80 else "🟡" if progress >= 50 else "🔴"
            msg += f"{icon} {mention}: `{progress:.1f}%` Done | IP: `{int(r['ip'])}` | **None: `{none}`**\n"
        
        msg += "━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "💡 *Dữ liệu tự động cập nhật từ Google Sheets.*"

        # 5. Gửi Discord
        if WEBHOOK_URL:
            requests.post(WEBHOOK_URL, json={"content": msg})
            print("✅ Báo cáo kèm thẻ tên đã được gửi!")

    except Exception as e:
        print(f"❌ Lỗi: {e}")

if __name__ == "__main__":
    get_report()
