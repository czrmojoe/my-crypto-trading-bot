import os
import telebot
from google import genai
from PIL import Image

# 1. ตั้งค่า API Token ต่างๆ (ใส่เครื่องหมายคำพูดแบบนี้ถูกต้องแล้วครับ)
TELEGRAM_TOKEN = "8864754384:AAG8k2KB4jj8NNb7NIodqojSaXUwhiPFk_c"
GEMINI_API_KEY = "AIzaSyBh7VA6fFzMdubTq3JePdPdJ9UCzn_-Mas"

# 2. เริ่มต้นการทำงานของบอท และ AI Client
# เรียกใช้ชื่อตัวแปรแทนการพิมพ์คีย์ยาวๆ ซ้ำครับ
bot = telebot.TeleBot(TELEGRAM_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# คำสั่ง (Prompt) ฉบับสรุปกระชับ สั้น ดุดัน เน้นใช้งานจริง
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
    bot.reply_to(message, "สวัสดีครับ! ผมคือผู้ช่วยเทรดคริปโต 🤖📈\nส่งภาพถ่ายหน้าจอกราฟเทคนิค (เช่น จาก TradingView หรือ Binance) มาให้ผมได้เลย ผมจะส่งให้ AI ช่วยวิเคราะห์แนวโน้มให้ครับ!")

# ฟังก์ชันรอรับข้อความที่เป็น "รูปภาพ" (Photo)
@bot.message_handler(content_types=['photo'])
def handle_menu_photo(message):
    try:
        # แจ้งเตือนผู้ใช้ก่อนว่ากำลังประมวลผล (ป้องกันผู้ใช้นึกว่าบอทค้าง)
        status_msg = bot.reply_to(message, "ได้รับภาพกราฟแล้วครับ กำลังส่งให้ AI วิเคราะห์... อาจใช้เวลา 5-10 วินาที ⏳")

        # ดึงไฟล์รูปภาพที่ชัดที่สุด (รูปสุดท้ายในอาร์เรย์จะมีขนาดใหญ่สุด)
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # บันทึกภาพลงเครื่องชั่วคราว
        image_path = "temp_chart.jpg"
        with open(image_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        # เปิดภาพด้วย Pillow เพื่อเตรียมส่งให้ AI
        img = Image.open(image_path)

        # ส่งภาพและ Prompt ไปที่ Gemini API (ใช้รุ่น gemini-2.5-flash ที่ประมวลผลเร็วและเก่งเรื่องภาพ)
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[img, ANALYSIS_PROMPT]
        )

        # ลบข้อความสถานะเดิม และส่งผลลัพธ์ที่ AI วิเคราะห์ตอบกลับไป
        bot.delete_message(message.chat.id, status_msg.message_id)
        
        text_response = response.text
        # Telegram จำกัดความยาวไว้ที่ 4000 ตัวอักษรต่อ 1 ข้อความ
        max_length = 4000 
        
        if len(text_response) > max_length:
            # ถ้าข้อความยาวเกินไป ให้แบ่งส่งทีละ 4000 ตัวอักษร
            for i in range(0, len(text_response), max_length):
                bot.send_message(message.chat.id, text_response[i:i+max_length])
        else:
            # ถ้าความยาวปกติ ให้ส่งแบบ reply ตามเดิม
            bot.reply_to(message, text_response)

        # ลบไฟล์ภาพชั่วคราวออกเพื่อประหยัดพื้นที่เซิร์ฟเวอร์
        if os.path.exists(image_path):
            os.remove(image_path)

    except Exception as e:
        bot.reply_to(message, f"❌ เกิดข้อผิดพลาดในการวิเคราะห์: {str(e)}")

# สั่งให้บอทรันตลอดเวลา (เปิดเฝ้ารอข้อความ)
print("บอทเริ่มทำงานแล้ว... รอรับรูปภาพกราฟของคุณใน Telegram")
bot.infinity_polling()