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
import ccxt

# สร้างฟังก์ชันเช็คราคา Realtime 
def monitor_crypto_price():
    exchange = ccxt.binance() # ดึงข้อมูลจาก Binance
    target_price = 70000 # ตั้งราคาที่ต้องการให้เตือน
    alert_fired = False

    while True:
        try:
            ticker = exchange.fetch_ticker('BTC/USDT')
            current_price = ticker['last']
            
            # ถ้าราคาพุ่งทะลุแนวต้านที่ตั้งไว้ ให้บอทยิงเตือน
            if current_price >= target_price and not alert_fired:
                bot.send_message(MY_CHAT_ID, f"🚨 **ALERT:** ตอนนี้ราคา BTC ทะลุเป้าหมายแล้ว! ราคาปัจจุบัน: ${current_price:,}")
                alert_fired = True # สั่งล็อกไว้ไม่ให้เตือนซ้ำกวนใจ
                
            time.sleep(30) # ให้แอบไปดูราคาทุกๆ 30 วินาที
        except Exception as e:
            time.sleep(10)

# เปิดรันระบบเช็คราคาเป็นเบื้องหลัง
threading.Thread(target=monitor_crypto_price, daemon=True).start()

# --- ลูกเล่นพิเศษ: หลอก Render ให้รันแผนฟรีได้ 24 ชม. ---
def run_dummy_server():
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args): return
    with socketserver.TCPServer(("", 8080), QuietHandler) as httpd:
        httpd.serve_forever()
threading.Thread(target=run_dummy_server, daemon=True).start()
# ----------------------------------------------------------------------------------

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MY_CHAT_ID = "1705356855"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# 🧠 ดิกชันนารีสำหรับเก็บความจำแยกตามรายคน (User Chat History Sessions)
# โครงสร้างนี้จะช่วยจำว่าคุยอะไรค้างไว้กับใคร
user_sessions = {}

# ข้อกำหนดบทบาทของบอทเวลาคุยเล่น/ปรึกษา
SYSTEM_INSTRUCTION = """
คุณคือผู้ช่วยเทรดคริปโตสายเทคนิคอลและกูรูด้านการลงทุน (Crypto Trading Expert) 
ให้ตอบคำถามอย่างเป็นกันเอง สรุปประเด็นชัดเจน ได้ใจความ 
หากผู้ใช้ถามเรื่องกลยุทธ์ อารมณ์ตลาด หรือปรึกษาพอร์ต ให้ใช้ความรู้ด้าน Technical Analysis ช่วยตอบเสมอ
"""

ANALYSIS_PROMPT = """
คุณคือผู้ช่วยเทรดคริปโตสายเทคนิคอลระดับโลก (Crypto Technical Analyst)
โปรดวิเคราะห์ภาพกราฟนี้และสรุปข้อมูล "เน้นเนื้อๆ ไม่เอาน้ำ" ให้กระชับที่สุด
📈 **Trend:** (Uptrend/Downtrend/Sideway ใน TF อะไร)
🛡️ **Support:** (ราคาแนวรับที่สำคัญ)
⚔️ **Resistance:** (ราคาแนวต้านที่สำคัญ)
🧩 **Pattern:** (รูปแบบกราฟหรือแท่งเทียนที่พบ ถ้าไม่มีให้ข้าม)
💡 **Action Plan:** (แนะนำจุดเข้า Buy/Sell พร้อมจุด Stop Loss และ Take Profit ชัดเจน)
"""

# ฟังก์ชัน Cron Job 07:00 น.
def auto_analyze_btc():
    try:
        chart_url = "https://charts.taapi.io/charts/btc-usdt-1d.png" 
        response_img = requests.get(chart_url)
        image_path = "auto_btc_1d.jpg"
        if response_img.status_code == 200:
            with open(image_path, 'wb') as f: f.write(response_img.content)
            img = Image.open(image_path)
            ai_response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=[img, ANALYSIS_PROMPT])
            bot.send_message(MY_CHAT_ID, ai_response.text)
            if os.path.exists(image_path): os.remove(image_path)
    except Exception as e:
        bot.send_message(MY_CHAT_ID, f"❌ ระบบตั้งเวลาเกิดข้อผิดพลาด: {str(e)}")

schedule.every().day.at("00:00").do(auto_analyze_btc)
def run_cron():
    while True:
        schedule.run_pending()
        time.sleep(1)
threading.Thread(target=run_cron, daemon=True).start()

# --- เริ่มส่วนปุ่มคำสั่งหลัก ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.chat.id
    # รีเซ็ตหรือสร้างเซสชันการคุยใหม่เมื่อกด /start
    user_sessions[user_id] = ai_client.chats.create(
        model="gemini-2.5-flash",
        config={"system_instruction": SYSTEM_INSTRUCTION}
    )
    bot.reply_to(message, "สวัสดีครับ! ผมเป็นผู้ช่วยเทรดคริปโตส่วนตัวของคุณแล้ว 🤖📈\n\n"
                          "⚙️ **ฟีเจอร์ตอนนี้:**\n"
                          "1. 💬 พิมพ์คุย/ปรึกษาเรื่องเทรดกับผมต่อเนื่องได้เลย ผมจะจำบริบทไว้\n"
                          "2. 🖼️ ส่งรูปภาพกราฟมาให้ผมช่วยวิเคราะห์แผนเทรดได้ทุกเมื่อ\n"
                          "3. ⏰ บอทจะสรุปแท่งเทียนวัน BTC 1D ส่งให้คุณทุกเช้าตอน 7 โมง")

# ฟังก์ชันรับภาพ (ส่งภาพจะวิเคราะห์สดแบบคำสั่งเดี่ยว ไม่รวมในแชทปกติเพื่อความประหยัดโควต้าคีย์)
@bot.message_handler(content_types=['photo'])
def handle_menu_photo(message):
    try:
        status_msg = bot.reply_to(message, "ได้รับภาพกราฟแล้วครับ กำลังส่งให้ AI วิเคราะห์... ⏳")
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        image_path = "temp_chart.jpg"
        with open(image_path, 'wb') as new_file: new_file.write(downloaded_file)
        img = Image.open(image_path)
        
        response = ai_client.models.generate_content(model='gemini-3.5-flash', contents=[img, ANALYSIS_PROMPT])
        bot.delete_message(message.chat.id, status_msg.message_id)
        
        text_response = response.text
        max_length = 4000 
        if len(text_response) > max_length:
            for i in range(0, len(text_response), max_length): bot.send_message(message.chat.id, text_response[i:i+max_length])
        else:
            bot.reply_to(message, text_response)
        if os.path.exists(image_path): os.remove(image_path)
    except Exception as e:
        bot.reply_to(message, f"❌ เกิดข้อผิดพลาดในการวิเคราะห์ภาพ: {str(e)}")

# ฟังก์ชันพิมพ์ข้อความคุยโต้ตอบ (Chat Mode) 💬
@bot.message_handler(content_types=['text'])
def handle_text_chat(message):
    user_id = message.chat.id
    
    # ถ้าผู้ใช้คนนี้ยังไม่มีห้องแชทในความทรงจำ ให้สร้างห้องแชทให้เขาก่อน
    if user_id not in user_sessions:
        user_sessions[user_id] = ai_client.chats.create(
            model="gemini-2.5-flash",
            config={"system_instruction": SYSTEM_INSTRUCTION}
        )
        
    try:
        # ส่งสถานะว่าบอทกำลังพิมพ์ข้อความตอบกลับ
        bot.send_chat_action(user_id, 'typing')
        
        # ดึงห้องแชทของคนนี้ออกมา แล้วส่งข้อความคุยต่อเนื่องไปหา Gemini
        chat_session = user_sessions[user_id]
        response = chat_session.send_message(message.text)
        
        # ส่งคำตอบกลับไปหาผู้ใช้ใน Telegram
        bot.reply_to(message, response.text)
        
    except Exception as e:
        bot.reply_to(message, f"❌ เกิดข้อผิดพลาดในระบบแชท: {str(e)}")

print("บอทเริ่มทำงานออนไลน์พร้อมระบบโต้ตอบต่อเนื่อง (Chat Mode) แล้ว...")
bot.infinity_polling()
