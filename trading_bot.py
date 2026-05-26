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
import ccxt  # ไลบรารีสำหรับดึงราคา Realtime

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

# ⚠️ สำคัญมาก: อย่าลืมใส่ Chat ID ของน้าตรงนี้ด้วยนะครับ
MY_CHAT_ID = "1705356855"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)
user_sessions = {}

# ข้อกำหนดบทบาทของบอทเวลาคุยเล่น/ปรึกษา
SYSTEM_INSTRUCTION = """
คุณคือผู้ช่วยเทรดคริปโตสายเทคนิคอลระดับโลก (Crypto Trading Expert) 
ให้ตอบคำถามอย่างเป็นกันเอง สรุปประเด็นชัดเจน ได้ใจความ 
เน้นการวิเคราะห์ด้วยเกณฑ์ Technical Analysis เช่น แนวรับแนวต้าน รูปแบบแท่งเทียน และสัญญาณอินดิเคเตอร์
"""

# Prompt สำหรับวิเคราะห์ภาพกราฟเทคนิคอล
ANALYSIS_PROMPT = """
คุณคือผู้ช่วยเทรดคริปโตสายเทคนิคอลระดับโลก (Crypto Technical Analyst)
โปรดวิเคราะห์ภาพกราฟนี้และสรุปข้อมูล "เน้นเนื้อๆ ไม่เอาน้ำ" ให้กระชับที่สุด
📈 **Trend:** (Uptrend/Downtrend/Sideway ใน TF อะไร)
🛡️ **Support:** (ราคาแนวรับที่สำคัญ)
⚔️ **Resistance:** (ราคาแนวต้านที่สำคัญ)
🧩 **Pattern:** (รูปแบบกราฟหรือแท่งเทียนที่พบ ถ้าไม่มีให้ข้าม)
💡 **Action Plan:** (แนะนำจุดเข้า Buy/Sell พร้อมจุด Stop Loss และ Take Profit ชัดเจน)
*หมายเหตุ: สรุปสั้นๆ เป็นข้อๆ ด้วยภาษาไทยที่เข้าใจง่ายที่สุด*
"""

# --- ⚡ 1. ระบบเฝ้าราคาฝั่ง Futures Perpetual (ทำงานอยู่เบื้องหลัง) ---
def monitor_crypto_price():
    # 🔗 ปรับแต่งให้เจาะจงตลาด Futures Perpetual (Swap) 100%
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'swap'} # 👈 เปลี่ยนจาก future เป็น swap เพื่อแก้ BadSymbol
    })
    
    target_high = 85000  
    target_low = 65000
    alert_high_fired = False
    alert_low_fired = False

    while True:
        try:
            # ดึงราคาคู่สัญญาไร้กำหนดอายุฝั่ง Futures
            ticker = exchange.fetch_ticker('BTC/USDT:USDT')
            current_price = ticker['last'] 
            
            if current_price >= target_high and not alert_high_fired:
                bot.send_message(MY_CHAT_ID, f"🚀 **🚨 FUTURES ALERT:** ราคา BTC Perpetual ทะลุเป้าบนแล้ว! ราคาปัจจุบัน: `${current_price:,}`")
                alert_high_fired = True
                
            if current_price <= target_low and not alert_low_fired:
                bot.send_message(MY_CHAT_ID, f"📉 **🚨 FUTURES ALERT:** ราคา BTC Perpetual หลุดแนวรับล่างแล้ว! ราคาปัจจุบัน: `${current_price:,}`")
                alert_low_fired = True
                
            time.sleep(20)
        except Exception as e:
            print(f"Error fetching futures price: {e}")
            time.sleep(10)

threading.Thread(target=monitor_crypto_price, daemon=True).start()
# ----------------------------------------------------------------------------------

# --- ⏰ 2. ระบบตั้งเวลาวิเคราะห์ BTC 1D ทุก 07:00 น. ไทย ---
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
    bot.reply_to(message, "สวัสดีครับน้า! บอทเวอร์ชันแก้ไขราคาฟิวเจอร์สอัปเดตตรงกระดาน 🤖⚡\n\n"
                          "💵 พิมพ์คำว่า 'ราคา', 'p', หรือพิมพ์ประโยคยาวๆ ระบบจะดึงราคาฟิวเจอร์สปัจจุบันมาให้ทันที\n"
                          "💬 พิมพ์คุย/ปรึกษาเทคนิคอลจำบริบทต่อเนื่องได้ยาวๆ\n"
                          "🖼️ ส่งภาพกราฟมาให้ช่วยตรวจหาจุดเปิดสัญญา (Action Plan) ได้ตลอด 24 ชม.")

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

# ฟังก์ชันพิมพ์ข้อความคุยโต้ตอบ + ดึงราคาตลาดล่วงหน้า
@bot.message_handler(content_types=['text'])
def handle_text_chat(message):
    user_id = message.chat.id
    msg_text = message.text.strip().lower()
    
    # ระบบค้นหาคำสำคัญเพื่อดึงราคาด่วนจากกระดาน Binance Futures
    price_keywords = ['ราคา', 'price', 'p', 'btc', 'บิตคอยน์', 'บิทคอยน์', 'ปัจจุบัน', 'ฟิวเจอร์']
    if any(keyword in msg_text for keyword in price_keywords):
        try:
            bot.send_chat_action(user_id, 'typing')
            
            # ล็อกระบบดึงข้อมูลจากตลาดสัญญาสด (Swap)
            exchange = ccxt.binance({'options': {'defaultType': 'swap'}})
            
            # ดึงราคาแท้จริงล่าสุดจากกระดาน Futures (ใช้รหัสมาตรฐานสากล)
            ticker = exchange.fetch_ticker('BTC/USDT:USDT')
            live_price = ticker['last']
            high_24h = ticker['high']
            low_24h = ticker['low']
            
            bot.reply_to(message, f"📊 **Binance Futures Perpetual**\n"
                                  f"🔹 **BTC/USDT (Perp):** `${live_price:,}`\n"
                                  f"📈 สูงสุด 24ชม: `${high_24h:,}`\n"
                                  f"📉 ต่ำสุด 24ชม: `${low_24h:,}`")
            return
        except Exception as e:
            bot.reply_to(message, f"❌ ดึงราคาฟิวเจอร์สไม่สำเร็จชั่วคราว: {e}")
            return

    # ระบบแชททั่วไปกับ Gemini 3.5 Flash
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

print("บอทระบบ Realtime Futures Perpetual ออนไลน์พร้อมทำงาน...")
bot.infinity_polling()