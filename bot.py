import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import re
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC, TIT2, TPE1
from mutagen.mp3 import MP3
import requests
from io import BytesIO

# إعداد السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ضع التوكن الخاص بك هنا
BOT_TOKEN = "8309221696:AAFanKtye5Ewo0qKUqfsOSz6EBuLOBdNICo"

# دالة البداية
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = """
مرحباً! 👋

أنا بوت تحميل الصوتيات من يوتيوب 🎵

أرسل لي رابط فيديو من YouTube وسأحوله إلى ملف صوتي MP3 

استخدم /help لمزيد من المعلومات
    """
    await update.message.reply_text(welcome_message)

# دالة المساعدة
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📖 كيفية الاستخدام:

1️⃣ انسخ رابط الفيديو من YouTube
2️⃣ أرسله لي مباشرة
3️⃣ انتظر قليلاً حتى يتم التحميل والتحويل
4️⃣ استلم الملف الصوتي! 🎉

⚠️ ملاحظات:
- سيتم تحويل الفيديو إلى MP3 بجودة عالية
- الفيديوهات الطويلة جداً قد تأخذ وقتاً

الأوامر المتاحة:
/start - البداية
/help - المساعدة
    """
    await update.message.reply_text(help_text)

# دالة التحقق من رابط يوتيوب
def is_youtube_url(url):
    youtube_patterns = [
        r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/',
        r'(https?://)?(www\.)?youtu\.be/',
    ]
    for pattern in youtube_patterns:
        if re.search(pattern, url):
            return True
    return False

# دالة إضافة الميتاداتا للملف الصوتي
def add_metadata(audio_file, title, artist, thumbnail_url):
    try:
        # تحميل الصورة المصغرة
        response = requests.get(thumbnail_url)
        image_data = response.content
        
        # إضافة الميتاداتا
        audio = MP3(audio_file, ID3=ID3)
        
        # حذف أي tags قديمة
        try:
            audio.delete()
        except:
            pass
        
        # إضافة tags جديدة
        audio = MP3(audio_file, ID3=ID3)
        audio.tags.add(TIT2(encoding=3, text=title))
        audio.tags.add(TPE1(encoding=3, text=artist))
        
        # إضافة صورة الغلاف
        audio.tags.add(
            APIC(
                encoding=3,
                mime='image/jpeg',
                type=3,
                desc='Cover',
                data=image_data
            )
        )
        
        audio.save()
        logger.info(f"Metadata added successfully to {audio_file}")
        
    except Exception as e:
        logger.error(f"Error adding metadata: {e}")

# دالة تحميل الصوت من يوتيوب
async def download_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if not is_youtube_url(url):
        await update.message.reply_text("❌ الرجاء إرسال رابط يوتيوب صحيح!")
        return
    
    # إرسال رسالة الانتظار
    status_message = await update.message.reply_text("⏳ جاري التحميل والتحويل... الرجاء الانتظار")
    
    try:
        # إنشاء مجلد التحميلات إذا لم يكن موجوداً
        os.makedirs('downloads', exist_ok=True)
        
        # إعدادات التحميل
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'quiet': True,
            'no_warnings': True,
        }
        
        # التحميل واستخراج المعلومات
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await status_message.edit_text("📥 جاري تحميل الفيديو...")
            info = ydl.extract_info(url, download=True)
            
            title = info.get('title', 'Unknown Title')
            channel = info.get('uploader', 'Unknown Artist')
            thumbnail = info.get('thumbnail', '')
            
            # اسم الملف النهائي
            base_filename = ydl.prepare_filename(info)
            mp3_filename = base_filename.rsplit('.', 1)[0] + '.mp3'
        
        # إضافة الميتاداتا
        await status_message.edit_text("🎨 جاري إضافة التفاصيل...")
        add_metadata(mp3_filename, title, channel, thumbnail)
        
        # تحديث الحالة
        await status_message.edit_text("📤 جاري رفع الملف الصوتي...")
        
        # تحميل صورة الثمنيل لإرسالها مع الصوت
        thumb_data = None
        if thumbnail:
            try:
                thumb_response = requests.get(thumbnail)
                thumb_data = BytesIO(thumb_response.content)
            except:
                pass
        
        # إرسال الملف الصوتي
        with open(mp3_filename, 'rb') as audio:
            await update.message.reply_audio(
                audio=audio,
                title=title,
                performer=channel,
                thumbnail=thumb_data,
                caption=f"🎵 {title}\n👤 {channel}"
            )
        
        # حذف رسالة الحالة
        await status_message.delete()
        
        # حذف الملف بعد الإرسال
        if os.path.exists(mp3_filename):
            os.remove(mp3_filename)
        
        # حذف الصورة المؤقتة إن وجدت
        thumbnail_files = [f for f in os.listdir('downloads') if f.endswith(('.jpg', '.png', '.webp'))]
        for thumb_file in thumbnail_files:
            try:
                os.remove(os.path.join('downloads', thumb_file))
            except:
                pass
            
    except Exception as e:
        logger.error(f"Error downloading audio: {e}")
        await status_message.edit_text(
            "❌ حدث خطأ في التحميل!\n\n"
            "الأسباب المحتملة:\n"
            "• الرابط غير صالح\n"
            "• الفيديو محمي أو محذوف\n"
            "• مشكلة في الاتصال\n\n"
            "حاول مرة أخرى أو جرب رابط آخر"
        )

# دالة معالجة الأخطاء
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception while handling an update: {context.error}")

# الدالة الرئيسية
def main():
    # إنشاء التطبيق
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_audio))
    
    # معالج الأخطاء
    application.add_error_handler(error_handler)
    
    # بدء البوت
    print("🤖 البوت يعمل الآن...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    import asyncio
    
    # Create new event loop for Python 3.14+
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        main()
    finally:
        loop.close()