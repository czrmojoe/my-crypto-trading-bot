import os
import telebot
from google import genai
from PIL import Image
import http.server
import socketserver
import threading

# --- ลูกเล่นพิเศษ: หลอก Render ว่าเราเป็นเว็บไซต์ จะได้รันแผน Web Service ฟรีได้ 24 ชม. ---
def run_dummy_server():
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args): return  # ปิด log เพื่อไม่ให้กวนหน้าจอเซิร์ฟเวอร์
    with socketserver.TCPServer(("", 8080), QuietHandler) as httpd:
        httpd.serve_forever()
threading.Thread(target=run_dummy_server, daemon=True).start()
# ----------------------------------------------------------------------------------

# 1. ตั้งค่าดึง API Token จาก Environment Variables ของ Render (ปลอดภัย คีย์ไม่หลุดแน่นอน)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# 2. เริ่มต้นการทำงานของบอท และ AI Client
bot = telebot.TeleBot(TELEGRAM_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# 3. คำสั่ง Prompt ฉบับสรุปกระชับ สั้น ดุดัน เน้นอ่านง่ายหน้าจอมือถือ
ANALYSIS_PROMPT = """
คุณคือผู้ช่วยเทรดคริปโตสายเทคนิคอลระดับโลก (Crypto Technical Analyst)
โปรดวิเคราะห์ภาพกราฟนี้และสรุปข้อมูล "เน้นเนื้อๆ ไม่เอาน้ำ" ให้กระชับที่สุด
โดยตอบกลับมาเป็นหัวข้อและใช้ Emoji นำหน้าตามรูปแบบนี้เท่านั้น:

📈 **Trend:** (Uptrend/Downtrend/Sideway ใน TF อะไร)
🛡️ **Support:** (ราคาแนวรับที่สำคัญ)
⚔️ **Resistance:** (ราคาแนวต้านที่สำคัญ)
🧩 **Pattern:** (รูปแบบกราฟหรือแท่งเทียนที่พบ ถ้าไม่มีให้ข้าม)
💡 **Action Plan:** (แนะนำจุดเข้า Buy/Sell พร้อมจุด Stop Loss และ Take Profit ชัดเจน)

*หมายเหตุ: สรุปสั้นๆ เป็นข้อๆ ด้วยภาษาไทยที่เข้าใจง่ายที่สุด ไม่ต้องบรรยายยาว*
"""

# ยินดีต้อนรับเมื่อพิมพ์ /start หรือ /help
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "สวัสดีครับ! บอทวิเคราะห์กราฟออนไลน์ 24 ชม. พร้อมทำงานแล้ว 🤖📈\nส่งภาพหน้าจอกราฟเทคนิคมาให้ผมได้เลยครับ!")

# ฟังก์ชันรอรับข้อความที่เป็น "รูปภาพ" (Photo)
@bot.message_handler(content_types=['photo'])
def handle_menu_photo(message):
    try:
        # ส่งข้อความแจ้งผู้ใช้ก่อนว่าระบบกำลังทำงาน
        status_msg = bot.reply_to(message, "ได้รับภาพกราฟแล้วครับ กำลังส่งให้ AI วิเคราะห์... ⏳")

        # ดึงไฟล์รูปภาพเวอร์ชันที่ชัดที่สุดมาดาวน์โหลด
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # บันทึกภาพลงเครื่องชั่วคราวบนเซิร์ฟเวอร์
        image_path = "temp_chart.jpg"
        with open(image_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        # เปิดภาพด้วย Pillow เพื่อส่งต่อให้ AI
        img = Image.open(image_path)

        # ส่งภาพและ Prompt ไปประมวลผลที่ Gemini 2.5 Flash
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[img, ANALYSIS_PROMPT]
        )

        # ลบข้อความสถานะเดิมทิ้งเพื่อความสะอาดของแชท
        bot.delete_message(message.chat.id, status_msg.message_id)
        
        # ดึงข้อความบทวิเคราะห์ และตรวจเช็คความยาวไม่ให้เกินลิมิตของ Telegram
        text_response = response.text
        max_length = 4000 
        
        if len(text_response) > max_length:
            # หากข้อความยาวเกินลิมิต ให้ตัดแบ่งครึ่งแล้วทยอยส่ง
            for i in range(0, len(text_response), max_length):
                bot.send_message(message.chat.id, text_response[i:i+max_length])
        else:
            # หากความยาวปกติ ให้ส่งกลับแบบ Reply
            bot.reply_to(message, text_response)

        # ลบไฟล์ภาพชั่วคราวออกเพื่อเคลียร์พื้นที่หน่วยความจำ
        if os.path.exists(image_path):
            os.remove(image_path)

    except Exception as e:
        bot.reply_to(message, f"❌ เกิดข้อผิดพลาดในการวิเคราะห์: {str(e)}")

# เปิดโหมด Infinity Polling รันบอทแสตนด์บายยาวๆ
print("บอทเริ่มทำงานออนไลน์แล้ว...")
bot.infinity_polling()