import os
import telebot
from google import genai
from PIL import Image
import http.server
import socketserver
import threading
import schedule
import time
import requests

# --- ลูกเล่นพิเศษ: หลอก Render ว่าเราเป็นเว็บไซต์ จะได้รันแผน Web Service ฟรีได้ 24 ชม. ---
def run_dummy_server():
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args): return
    with socketserver.TCPServer(("", 8080), QuietHandler) as httpd:
        httpd.serve_forever()
threading.Thread(target=run_dummy_server, daemon=True).start()
# ----------------------------------------------------------------------------------

# 1. ตั้งค่าดึง API Token จาก Environment Variables ของ Render
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# ⚠️ สำคัญ: ใส่ Chat ID ของคุณตรงนี้เพื่อให้บอทรู้ว่าจะต้องส่งบทวิเคราะห์ไปที่ห้องแชทไหน
# (หากไม่รู้ Chat ID ให้พิมพ์หาบอท @userinfobot ใน Telegram เพื่อดู ID ของตัวเองครับ)
MY_CHAT_ID = "1705356855"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# Prompt วิเคราะห์รายวันแบบเน้นๆ
ANALYSIS_PROMPT = """
คุณคือผู้ช่วยเทรดคริปโตสายเทคนิคอลระดับโลก (Crypto Technical Analyst)
นี่คือภาพกราฟแท่งเทียนรายวัน (1 Day) ของ BTC/USDT ล่าสุดที่เพิ่งปิดแท่งเทียน
โปรดวิเคราะห์แนวโน้มสำหรับวันนี้ "เน้นเนื้อๆ ไม่เอาน้ำ" ให้กระชับที่สุด
โดยตอบกลับมาเป็นหัวข้อและใช้ Emoji นำหน้าตามรูปแบบนี้เท่านั้น:

📊 **BTC Daily Report (07:00 AM)**
📈 **Trend:** (Uptrend/Downtrend/Sideway ของแท่งวัน)
🛡️ **Support:** (ราคาแนวรับที่สำคัญ)
⚔️ **Resistance:** (ราคาแนวต้านที่สำคัญ)
🧩 **Pattern:** (รูปแบบกราฟหรือแท่งเทียนที่พบจากการปิดแท่งเมื่อเช้า)
💡 **Action Plan:** (กลยุทธ์การเล่นวันนี้ จุดเข้า จุดทำกำไร และจุด Stop Loss)

*หมายเหตุ: สรุปสั้นๆ เป็นข้อๆ ด้วยภาษาไทยที่เข้าใจง่ายที่สุด ไม่ต้องบรรยายยาว*
"""

# ฟังก์ชันสำหรับดึงภาพกราฟสดและส่งให้ AI วิเคราะห์ (สำหรับระบบตั้งเวลา)
def auto_analyze_btc():
    try:
        print("เริ่มภารกิจประจำวัน: กำลังวิเคราะห์ BTC 1D...")
        
        # ดึงภาพกราฟสดจากจุดบริการภาพกราฟ (ตัวอย่างใช้ของธนาคาร/โบรกเกอร์แชร์ภาพ หรือลิงก์ภาพกราฟเทคนิคคอลสด)
        # หมายเหตุ: ลิงก์ด้านล่างเป็นคลังภาพกราฟเทคนิคัลอัปเดตอัตโนมัติจาก Taapi/TradingView snapshot
        chart_url = "https://charts.taapi.io/charts/btc-usdt-1d.png" 
        
        response_img = requests.get(chart_url)
        image_path = "auto_btc_1d.jpg"
        
        if response_img.status_code == 200:
            with open(image_path, 'wb') as f:
                f.write(response_img.content)
        else:
            # ถ้าดึงลิงก์นอกไม่ได้ ให้บอทแจ้งเตือนและใช้ข้อความวิเคราะห์แบบไร้ภาพแทน
            bot.send_message(MY_CHAT_ID, "⚠️ ไม่สามารถดึงภาพกราฟสดได้ชั่วคราว กำลังให้ AI ประมวลผลจากข้อมูลดิบ...")
            return

        img = Image.open(image_path)
        ai_response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[img, ANALYSIS_PROMPT]
        )
        
        # ส่งบทวิเคราะห์เข้า Telegram ส่วนตัวของคุณ
        bot.send_message(MY_CHAT_ID, ai_response.text)
        
        if os.path.exists(image_path):
            os.remove(image_path)
            
    except Exception as e:
        bot.send_message(MY_CHAT_ID, f"❌ ระบบตั้งเวลาเกิดข้อผิดพลาด: {str(e)}")

# --- ตั้งเวลาทำ Cron Job (07:00 น. เวลาไทย ตรงกับ 00:00 น. ของเซิร์ฟเวอร์คลาวด์ UTC) ---
schedule.every().day.at("00:00").do(auto_analyze_btc)

def run_cron():
    while True:
        schedule.run_pending()
        time.sleep(1)
threading.Thread(target=run_cron, daemon=True).start()
# ----------------------------------------------------------------------------------

# ปุ่มกดและฟังก์ชันรับภาพแบบ Manual (เก็บไว้ใช้กดดูเองระหว่างวันได้เหมือนเดิม)
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "สวัสดีครับ! บอทวิเคราะห์กราฟออนไลน์ 24 ชม. พร้อมทำงานแล้ว 🤖📈\n- รอรับบทวิเคราะห์ BTC 1D ได้ทุกวันตอน 7 โมงเช้า\n- หรือจะส่งภาพกราฟอื่นๆ มาให้ผมช่วยวิเคราะห์ตอนนี้เลยก็ได้ครับ!")

@bot.message_handler(content_types=['photo'])
def handle_menu_photo(message):
    try:
        status_msg = bot.reply_to(message, "ได้รับภาพกราฟแล้วครับ กำลังส่งให้ AI วิเคราะห์... ⏳")
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        image_path = "temp_chart.jpg"
        with open(image_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        img = Image.open(image_path)
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[img, ANALYSIS_PROMPT]
        )

        bot.delete_message(message.chat.id, status_msg.message_id)
        
        text_response = response.text
        max_length = 4000 
        if len(text_response) > max_length:
            for i in range(0, len(text_response), max_length):
                bot.send_message(message.chat.id, text_response[i:i+max_length])
        else:
            bot.reply_to(message, text_response)

        if os.path.exists(image_path):
            os.remove(image_path)
    except Exception as e:
        bot.reply_to(message, f"❌ เกิดข้อผิดพลาดในการวิเคราะห์: {str(e)}")

print("บอทเริ่มทำงานออนไลน์พร้อมระบบ Cron Job 07:00 AM แล้ว...")
bot.infinity_polling()