import requests
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import os
import streamlit as st

# Lấy thông tin từ GitHub Secrets (đã cài ở Bước 3)
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
SHEET_URL = os.environ.get("GSHEETS_URL")

def get_data_and_send():
    try:
        # Giả lập một connection để dùng GSheetsConnection mà không cần chạy app
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        # Đọc dữ liệu từ URL
        raw_df = conn.read(spreadsheet=SHEET_URL, header=None)
        header_idx = next((i for i, row in raw_df.iterrows() if "Userstory/Todo" in row.values), None)
        
        if header_idx is not None:
            df = conn.read(spreadsheet=SHEET_URL, skiprows=header_idx)
            df.columns = [str(c).strip() for c in df.columns]
            
            # Chuẩn hóa trạng thái
            df['State_Clean'] = df['State'].fillna('None').replace('', 'None').str.strip().str.lower()
            valid_pics = ['Tài', 'Dương', 'QA', 'Quân', 'Phú', 'Thịnh', 'Đô', 'Tùng', 'Anim', 'Thắng VFX']
            df_team = df[df['PIC'].isin(valid_pics)].copy()

            # Tính toán logic (Cancel = Done)
            pic_stats = df_team.groupby('PIC').agg(
                total=('Userstory/Todo', 'count'),
                done=('State_Clean', lambda x: x.isin(['done', 'cancel']).sum()),
                ip=('State_Clean', lambda x: (x == 'in progress').sum()),
                none=('State_Clean', lambda x: (x == 'none').sum())
            ).reset_index()

            # Xây dựng nội dung tin nhắn
            msg = "⏰ **BÁO CÁO TỰ ĐỘNG ĐẦU NGÀY (8:30 AM)** ☀️\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━\n"
            
            for _, r in pic_stats.iterrows():
                progress = (r['done'] / r['total'] * 100) if r['total'] > 0 else 0
                icon = "🟢" if progress >= 80 else "🟡"
                msg += f"{icon} **{r['PIC']}**: `{progress:.1f}%` Done\n"
                msg += f"   • Xong/Cancel: `{int(r['done'])}` | In Progress: `{int(r['ip'])}` | None: `{int(r['none'])}` \n"
            
            msg += "━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "👉 Xem Dashboard: [Link App của bạn]"

            # Gửi lên Discord
            requests.post(WEBHOOK_URL, json={"content": msg})
            print("Đã gửi báo cáo thành công!")
            
    except Exception as e:
        print(f"Lỗi khi chạy báo cáo tự động: {e}")

if __name__ == "__main__":
    get_data_and_send()
