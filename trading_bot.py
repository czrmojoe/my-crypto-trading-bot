import os
import telebot
from google import genai
from PIL import Image
import http.server
import socketserver
import threading

# --- ลูกเล่นพิเศษ: หลอก Render ว่าเราเป็นเว็บไซต์ จะได้รันฟรีได้ 24 ชม. ---
def run_dummy_server():
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args): return  # ปิด log กวนใจ
    with socketserver.TCPServer(("", 8080), QuietHandler) as httpd:
        httpd.serve_forever()
threading.Thread(target=run_dummy_server, daemon=True).start()
# ------------------------------------------------------------------

# 1. ตั้งค่า API Token ต่างๆ (ใช้คีย์ใหม่ที่คุณเปลี่ยนแล้ว)
TELEGRAM_TOKEN = "ใส่_TELEGRAM_BOT_TOKEN_ใหม่ของคุณ"
GEMINI_API_KEY = "ใส่_GEMINI_API_KEY_ใหม่ของคุณ"

# 2. เริ่มต้นการทำงานของบอท และ AI Client
bot = telebot.TeleBot(TELEGRAM_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# คำสั่ง Prompt แบบเน้นย้อย ย่อสั้น อ่านง่าย
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

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "สวัสดีครับ! บอทวิเคราะห์กราฟออนไลน์ 24 ชม. พร้อมทำงานแล้ว 🤖📈\nส่งภาพกราฟมาได้เลยครับ!")

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
        
        # ป้องกันปัญหากล่องข้อความเต็ม และลบ parse_mode ออกเพื่อกันเออร์เรอร์ Markdown
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

print("บอทเริ่มทำงานออนไลน์แล้ว...")
bot.infinity_polling()