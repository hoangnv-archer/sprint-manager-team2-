import requests
import pandas as pd
import os
import gspread
import json

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
SHEET_URL = os.environ.get("GSHEETS_URL")
SERVICE_ACCOUNT_JSON = os.environ.get("GCP_SERVICE_ACCOUNT")

def get_report():
    try:
        # 1. Xác thực
        creds_dict = json.loads(SERVICE_ACCOUNT_JSON)
        gc = gspread.service_account_from_dict(creds_dict)
        
        # 2. Mở Sheet
        sh = gc.open_by_url(SHEET_URL)
        worksheet = sh.get_worksheet(0)
        data = worksheet.get_all_values()
        
        # 3. Chuyển thành DataFrame
        df_full = pd.DataFrame(data)
        header_idx = df_full[df_full.eq("Userstory/Todo").any(axis=1)].index[0]
        df = pd.DataFrame(data[header_idx + 1:], columns=data[header_idx])
        
        # 4. CHUẨN HÓA DỮ LIỆU (QUAN TRỌNG)
        df.columns = [str(c).strip() for c in df.columns]
        
        # Chuyển State về chữ thường, xóa khoảng trắng, nếu trống thì ghi là 'none'
        df['State_Clean'] = df['State'].str.strip().str.lower()
        df['State_Clean'] = df['State_Clean'].replace(['', None], 'none')
        
        valid_pics = ['Tài', 'Dương', 'QA', 'Quân', 'Phú', 'Thịnh', 'Đô', 'Tùng', 'Anim', 'Thắng VFX']
        df_team = df[df['PIC'].isin(valid_pics)].copy()

        # 5. TÍNH TOÁN CHI TIẾT
        pic_stats = df_team.groupby('PIC').agg(
            total=('Userstory/Todo', 'count'),
            done=('State_Clean', lambda x: x.isin(['done', 'cancel']).sum()),
            ip=('State_Clean', lambda x: (x == 'in progress').sum()),
            none=('State_Clean', lambda x: (x == 'none').sum())
        ).reset_index()

        # 6. SOẠN TIN NHẮN (Bổ sung phần 'Chưa làm')
        msg = "⏰ **BÁO CÁO TỰ ĐỘNG (8:30 AM)** ☀️\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━\n"
        
        for _, r in pic_stats.iterrows():
            total = int(r['total'])
            done = int(r['done'])
            ip = int(r['ip'])
            none = int(r['none'])
            
            progress = (done / total * 100) if total > 0 else 0
            icon = "🟢" if progress >= 80 else "🟡" if progress >= 50 else "🔴"
            
            msg += f"{icon} **{r['PIC']}**: `{progress:.1f}%` Hoàn thành\n"
            msg += f"   • Xong/Cancel: `{done}`\n"
            msg += f"   • In Progress: `{ip}`\n"
            msg += f"   • **Chưa làm (None): `{none}`**\n" # Thêm dòng này
            msg += f"   • Tổng task: `{total}`\n"
            msg += "─────────────────────\n"
        
        msg += "💡 *Dữ liệu được cập nhật tự động từ Google Sheets.*"

        # 7. Gửi Discord
        if WEBHOOK_URL:
            requests.post(WEBHOOK_URL, json={"content": msg})
            print("✅ Đã gửi báo cáo đầy đủ thông tin!")

    except Exception as e:
        print(f"❌ Lỗi: {e}")

if __name__ == "__main__":
    get_report()
