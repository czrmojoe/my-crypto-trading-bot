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
import ccxt  # ไลบรารีสำหรับดึงราคา Realtime จากกระดานเทรด

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

# ⚠️ สำคัญมาก: เปลี่ยนเลขตรงนี้ให้เป็น Chat ID ส่วนตัวของน้า เพื่อให้ระบบตั้งเวลาส่งรายงานถูกห้องแชท
MY_CHAT_ID = "1705356855"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)
user_sessions = {}

# ข้อกำหนดบทบาทของบอทเวลาคุยเล่น/ปรึกษา
SYSTEM_INSTRUCTION = """
คุณคือผู้ช่วยเทรดคริปโตสายเทคนิคอลและกูรูด้านการลงทุน (Crypto Trading Expert) 
ให้ตอบคำถามอย่างเป็นกันเอง สรุปประเด็นชัดเจน ได้ใจความ 
หากผู้ใช้ถามเรื่องกลยุทธ์ อารมณ์ตลาด หรือปรึกษาพอร์ต ให้ใช้ความรู้ด้าน Technical Analysis ช่วยตอบเสมอ
"""

# Prompt สำหรับวิเคราะห์ภาพกราฟเทคนิคอล
ANALYSIS_PROMPT = """
คุณคือผู้ช่วยเทรดคริปโตสายเทคนิคอลระดับโลก (Crypto Technical Analyst)
โปรดวิเคราะห์ภาพกราฟนี้และสรุปข้อมูล "เน้นเนื้อๆ ไม่เอาน้ำ" ให้กระชับที่สุด
📊 **BTC Daily Report (07:00 AM)** (ถ้าเป็นระบบตั้งเวลาตอนเช้า)
📈 **Trend:** (Uptrend/Downtrend/Sideway ใน TF อะไร)
🛡️ **Support:** (ราคาแนวรับที่สำคัญ)
⚔️ **Resistance:** (ราคาแนวต้านที่สำคัญ)
🧩 **Pattern:** (รูปแบบกราฟหรือแท่งเทียนที่พบ ถ้าไม่มีให้ข้าม)
💡 **Action Plan:** (แนะนำจุดเข้า Buy/Sell พร้อมจุด Stop Loss และ Take Profit ชัดเจน)
*หมายเหตุ: สรุปสั้นๆ เป็นข้อๆ ด้วยภาษาไทยที่เข้าใจง่ายที่สุด*
"""

# --- ⚡ 1. ระบบเฝ้าราคาและแจ้งเตือนราคาชนเส้นอัตโนมัติ (ทำงานอยู่เบื้องหลัง) ---
def monitor_crypto_price():
    exchange = ccxt.binance({'enableRateLimit': True})
    
    # 📌 น้าสามารถตั้งราคาแจ้งเตือนตรงนี้ได้เลย (ตัวอย่าง: ตั้งเตือนเมื่อราคาพุ่งทะลุแนวรับ/แนวต้าน)
    target_high = 75000  
    target_low = 60000
    
    alert_high_fired = False
    alert_low_fired = False

    while True:
        try:
            ticker = exchange.fetch_ticker('BTC/USDT')
            current_price = ticker['last']
            
            # เงื่อนไขแจ้งเตือนราคาบน
            if current_price >= target_high and not alert_high_fired:
                bot.send_message(MY_CHAT_ID, f"🚀 **🚨 ALERT:** ราคา BTC พุ่งทะลุเป้าบนแล้ว! ราคาปัจจุบัน: `${current_price:,}`")
                alert_high_fired = True
                
            # เงื่อนไขแจ้งเตือนราคาล่าง
            if current_price <= target_low and not alert_low_fired:
                bot.send_message(MY_CHAT_ID, f"📉 **🚨 ALERT:** ราคา BTC ร่วงทะลุแนวรับล่างแล้ว! ราคาปัจจุบัน: `${current_price:,}`")
                alert_low_fired = True
                
            time.sleep(20) # ให้แอบไปส่องราคาทุกๆ 20 วินาที
        except Exception as e:
            print(f"Error fetching price: {e}")
            time.sleep(10)

threading.Thread(target=monitor_crypto_price, daemon=True).start()
# ----------------------------------------------------------------------------------

# --- ⏰ 2. ระบบตั้งเวลาวิเคราะห์ BTC 1D ทุก 07:00 น. ไทย (00:00 น. เวลาคลาวด์ UTC) ---
def auto_analyze_btc():
    try:
        chart_url = "https://charts.taapi.io/charts/btc-usdt-1d.png" 
        response_img = requests.get(chart_url)
        image_path = "auto_btc_1d.jpg"
        if response_img.status_code == 200:
            with open(image_path, 'wb') as f: f.write(response_img.content)
            img = Image.open(image_path)
            ai_response = ai_client.models.generate_content(model='gemini-3.5-flash', contents=[img, ANALYSIS_PROMPT])
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
# ----------------------------------------------------------------------------------

# --- 🎮 3. ส่วนควบคุมคำสั่งหลักบน Telegram ---

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.chat.id
    user_sessions[user_id] = ai_client.chats.create(
        model="gemini-3.5-flash",
        config={"system_instruction": SYSTEM_INSTRUCTION}
    )
    bot.reply_to(message, "สวัสดีครับน้า! บอทเวอร์ชันอัปเกรดฉลาดสุดๆ พร้อมทำงานแล้วครับ 🤖📈\n\n"
                          "💵 **พิมพ์เช็คราคาได้อิสระ:** พิมพ์คำว่า 'ราคา', 'p', 'btc' หรือพิมพ์ประโยคยาวๆ เช่น 'ขอราคาบิตคอยน์ปัจจุบันหน่อย' ระบบจะดึงราคาจาก Binance ให้ทันทีครับ\n"
                          "💬 พิมพ์คุย/ปรึกษาเรื่องเทรดทั่วไปต่อเนื่องจำบริบทได้ยาวๆ\n"
                          "🖼️ ส่งภาพกราฟเทคนิคอลมาให้ช่วยสรุปกลยุทธ์การเล่นได้ตลอด 24 ชม.")

@bot.message_handler(content_types=['photo'])
def handle_menu_photo(message):
    try:
        status_msg = bot.reply_to(message, "ได้รับภาพกราฟแล้วครับ กำลังส่งให้ Gemini 3.5 Flash วิเคราะห์... ⏳")
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

# ฟังก์ชันรับข้อความ พิมพ์คุยโต้ตอบ + ดักจับระบบเช็คราคาอัจฉริยะ 💬
@bot.message_handler(content_types=['text'])
def handle_text_chat(message):
    user_id = message.chat.id
    msg_text = message.text.strip().lower()
    
    # 🕵️‍♂️ สกิลเช็คราคาอัจฉริยะ: ค้นหาคำสำคัญในประโยค พิมพ์คำไหนปนมาก็ดึงราคา Realtime จาก Binance ให้ทันที ไม่ผ่าน AI
    price_keywords = ['ราคา', 'price', 'p', 'btc', 'บิตคอยน์', 'บิทคอยน์', 'ปัจจุบัน']
    if any(keyword in msg_text for keyword in price_keywords):
        try:
            bot.send_chat_action(user_id, 'typing')
            exchange = ccxt.binance()
            ticker = exchange.fetch_ticker('BTC/USDT')
            live_price = ticker['last']
            high_24h = ticker['high']
            low_24h = ticker['low']
            bot.reply_to(message, f"💰 **Binance Live Price**\n"
                                  f"🔸 **BTC/USDT:** `${live_price:,}`\n"
                                  f"📈 สูงสุด 24ชม: `${high_24h:,}`\n"
                                  f"📉 ต่ำสุด 24ชม: `${low_24h:,}`")
            return
        except Exception as e:
            bot.reply_to(message, f"❌ ดึงราคาไม่สำเร็จชั่วคราว: {e}")
            return

    # 🧠 ระบบแชทโต้ตอบทั่วไปแบบจำความจำเก่าด้วย Gemini 3.5 Flash
    if user_id not in user_sessions:
        user_sessions[user_id] = ai_client.chats.create(
            model="gemini-3.5-flash",
            config={"system_instruction": SYSTEM_INSTRUCTION}
        )
        
    try:
        bot.send_chat_action(user_id, 'typing')
        chat_session = user_sessions[user_id]
        response = chat_session.send_message(message.text)
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, f"❌ เกิดข้อผิดพลาดในระบบแชท: {str(e)}")

print("บอทเริ่มทำงานออนไลน์ระบบสมบูรณ์แบบเรียบร้อย...")
bot.infinity_polling()