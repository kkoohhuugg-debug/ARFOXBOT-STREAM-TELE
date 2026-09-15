import asyncio
import json
import random
import re
import urllib.parse
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import httpx

# توكن البوت والمعلومات الأساسية
TELEGRAM_TOKEN = "8984966726:AAGnqqbhtvfmQtF6oqBPJPrSwDqZIhiP3RQ"
CHANNEL_INVITE_CODE = "0029VbC9XL2GJP8HPaVgWt1S"

# 1. إيموجيات حزينة متناسقة
def get_sad_emoji(quote_text: str) -> str:
    txt = quote_text.lower()
    if any(w in txt for w in ['موت', 'فقد', 'رحيل']):
        return '🥀🖤'
    if any(w in txt for w in ['دموع', 'بكاء', 'مطر', 'تبكي']):
        return '🌧️💔'
    if any(w in txt for w in ['شوق', 'حنين', 'غياب', 'اشتياق']):
        return '🖤🕊️'
    if any(w in txt for w in ['قلب', 'كسر', 'جرح', 'وجع']):
        return '💔🍂'
    
    sad_emoji_sets = ['🖤✨', '🥀💔', '🌧️🤍', '🥀✨', '🖤🕊️', '🌧️🖤', '💔🍂', '🖤🥀', '😭💔', '🥀😭']
    return random.choice(sad_emoji_sets)

# 2. الاتصال بـ API الذكاء الاصطناعي
async def call_gpt_api(prompt: str) -> str:
    encoded_prompt = urllib.parse.quote(prompt)
    url = f"https://engez.a7a.online/api/v1/ai/gpt?q={encoded_prompt}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers)
        res_data = response.json()
        
        if res_data.get('success') and res_data.get('response', {}).get('success'):
            result_obj = res_data['response'].get('result', {})
            reply = result_obj.get('message') or res_data['response'].get('raw') or ""
            return reply
        else:
            raise Exception("فشل الرد من الخادم")

# 3. دالة تنظيف صارمة لحذف الأكواد والمُعرّفات والرموز الغريبة
def clean_quote_text(text: str) -> str:
    if not text:
        return ''
    
    text = re.sub(r':::[^\s]*', '', text)
    text = re.sub(r'\{[^}]*\}', '', text)
    text = re.sub(r'\[[^\]]*\]', '', text)
    text = re.sub(r'id\s*=\s*["\']?[^"\'\s\}]+["\']?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'["\'\}\{\[\]\\]', '', text)
    text = re.sub(r'^[\d\.\-\*•\)\(\s]+', '', text)
    text = re.sub(r'^["\'«»\u200f\s]+|["\'«»\s]+$', '', text)
    text = re.sub(r'[\.\!\?،,\s]+$', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# 4. دالة التحقق من أن السطر نص عربي حقيقي وليس كوداً
def is_valid_arabic_quote(line: str) -> bool:
    if not line or len(line) < 10:
        return False
    
    is_artifact = bool(re.search(r'id=|variant|document|script|html|http|:::|[{}]|\[|\]', line, re.IGNORECASE))
    arabic_letters_count = len(re.findall(r'[\u0600-\u06FF]', line))
    return not is_artifact and arabic_letters_count >= 6

# 5. دالة التوليد الضامنة لـ 15 إقتباساً نقياً 100%
async def generate_exactly_15_quotes() -> list:
    accumulated_quotes = []
    attempts = 0

    while len(accumulated_quotes) < 15 and attempts < 5:
        attempts += 1
        needed = 15 - len(accumulated_quotes)
        prompt = f"""اكتب لي {needed + 10} إقتباسات حزينة ومؤثرة جداً عن الشوق، الفراق، ألم الغياب والخذلان.
الشروط الصارمة:
1. اكتب النصوص مباشرة بدون أي وسوم أو أكواد أو رموز برمجية نهائياً.
2. كل إقتباس في سطر مستقل بدون ترقيم.
3. لا تضع نقطة (.) في نهاية السطر نهائياً.
4. بدون أي مقدمات أو خاتمات."""

        try:
            raw_reply = await call_gpt_api(prompt)
            lines = raw_reply.split('\n')
            
            for line in lines:
                cleaned = clean_quote_text(line)
                if is_valid_arabic_quote(cleaned) and cleaned not in accumulated_quotes:
                    accumulated_quotes.append(cleaned)
                    
        except Exception as e:
            print(f"محاولة AI رقم {attempts} فشلت: {e}")

    return accumulated_quotes[:15]

# 6. معالج الأمر لتلجرام
async def quote_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(
            "🤖 *جاري بدء توليد ونشر 15 إقتباساً في قناة واتساب ...*",
            parse_mode="Markdown"
        )

        chat_id = update.effective_chat.id

        async def run_publish_job():
            success_count = 0
            last_error = ''

            try:
                quotes_list = await generate_exactly_15_quotes()

                if not quotes_list or len(quotes_list) == 0:
                    print('⚠️ لم يتم جلب إقتباسات في هذه الدورة.')
                    return {"success_count": 0, "error": "تعذر جلب البيانات."}

                for quote in quotes_list:
                    clean_quote = clean_quote_text(quote)

                    if not is_valid_arabic_quote(clean_quote):
                        continue

                    matched_emoji = get_sad_emoji(clean_quote)
                    formatted_quote = f"*‏{clean_quote} {matched_emoji}*"

                    try:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=formatted_quote,
                            parse_mode="Markdown"
                        )
                        success_count += 1
                    except Exception as post_err:
                        last_error = str(post_err)

                    # تأخير 2.5 ثانية بين الرسائل
                    await asyncio.sleep(2.5)

            except Exception as err:
                last_error = str(err)

            print(f"✅ تم نشر {success_count} إقتباس بنجاح.")
            return {"success_count": success_count, "error": last_error}

        result = await run_publish_job()

        if result["success_count"] == 0:
            await update.message.reply_text(
                f"❌ *فشل النشر:*\n`{result['error']}`",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"*✅ تم نشر [ {result['success_count']} ] إقتباساً بنجاح*",
                parse_mode="Markdown"
            )

    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ غير متوقع: {e}")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # الأوامر المفعلة: /quote أو /اقتباس أو /اقتباسات
    app.add_handler(CommandHandler(["quote", "اقتباس", "اقتباسات"], quote_command_handler))

    print("🚀 البوت يعمل الآن ويستمع للأوامر...")
    app.run_polling()

if __name__ == "__main__":
    main()

