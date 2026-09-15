import asyncio
import html
import json
import os
import random
import re
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
import httpx
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# توكن بوت التلغرام الخاص بك
TELEGRAM_TOKEN = "8984966726:AAGnqqbhtvfmQtF6oqBPJPrSwDqZIhiP3RQ"

# 1. رمز القناة المرجعي
CHANNEL_INVITE_CODE = "0029VbC9XL2GJP8HPaVgWt1S"


# خادم بسيط لاستجابة Railway Health Check وتفادي الـ Crash
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running successfully!")

    def log_message(self, format, *args):
        return


def start_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()


# 2. إيموجيات حزينة متناسقة
def get_sad_emoji(quote_text: str) -> str:
    txt = quote_text.lower()
    if "موت" in txt or "فقد" in txt or "رحيل" in txt:
        return "🥀🖤"
    if "دموع" in txt or "بكاء" in txt or "مطر" in txt or "تبكي" in txt:
        return "🌧️💔"
    if "شوق" in txt or "حنين" in txt or "غياب" in txt or "اشتياق" in txt:
        return "🖤🕊️"
    if "قلب" in txt or "كسر" in txt or "جرح" in txt or "وجع" in txt:
        return "💔🍂"

    sad_emoji_sets = [
        "🖤✨",
        "🥀💔",
        "🌧️🤍",
        "🥀✨",
        "🖤🕊️",
        "🌧️🖤",
        "💔🍂",
        "🖤🥀",
        "😭💔",
        "🥀😭",
    ]
    return random.choice(sad_emoji_sets)


# 3. الاتصال بـ API الذكاء الاصطناعي مع معالجة الأخطاء
async def call_gpt_api(prompt: str) -> str:
    encoded_prompt = urllib.parse.quote(prompt)
    url = f"https://engez.a7a.online/api/v1/ai/gpt?q={encoded_prompt}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                raise Exception(f"خطأ في الاستجابة: status {response.status_code}")
            res_data = response.json()
        except Exception as e:
            raise Exception(f"فشل الاتصال بالخادم: {str(e)}")

        if res_data.get("success") and res_data.get("response", {}).get("success"):
            resp = res_data.get("response", {})
            reply = (
                resp.get("result", {}).get("message") or resp.get("raw") or ""
            )
            return reply
        else:
            raise Exception("فشل الرد من خادم الذكاء الاصطناعي")


# دالة تنظيف صارمة لحذف الأكواد والمُعرّفات والرموز الغريبة
def clean_quote_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r":::[^\s]*", "", text)
    text = re.sub(r"\{[^}]*\}", "", text)
    text = re.sub(r"\[[^\]]*\]", "", text)
    text = re.sub(
        r'id\s*=\s*["\']?[^"\'\s\}]+["\']?', "", text, flags=re.IGNORECASE
    )
    text = re.sub(r'["\'\}\{\[\]\\]', "", text)
    text = re.sub(r"^[\d\.\-\*•\)\(\s]+", "", text)
    text = re.sub(r'^["\'«»‏\s]+|["\'«»\s]+$', "", text)
    text = re.sub(r"[\.\!\?،,\s]+$", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# دالة التحقق من أن السطر نص عربي حقيقي
def is_valid_arabic_quote(line: str) -> bool:
    if not line or len(line) < 10:
        return False
    is_artifact = bool(
        re.search(
            r"id=|variant|document|script|html|http|:::|[{}]|\[|\]",
            line,
            re.IGNORECASE,
        )
    )
    arabic_letters = re.findall(r"[\u0600-\u06FF]", line)
    return not is_artifact and len(arabic_letters) >= 6


# 4. دالة التوليد الضامنة لـ 15 إقتباساً نقياً 100%
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

            parsed_lines = [
                clean_quote_text(line)
                for line in raw_reply.split("\n")
                if is_valid_arabic_quote(clean_quote_text(line))
                and clean_quote_text(line) not in accumulated_quotes
            ]

            accumulated_quotes.extend(parsed_lines)
        except Exception as e:
            print(f"محاولة AI رقم {attempts} فشلت: {e}")

    return accumulated_quotes[:15]


# 5. دالة النشر والتأكد من العدد الفعلي المنشور
async def run_publish_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    success_count = 0
    last_error = ""

    try:
        quotes_list = await generate_exactly_15_quotes()

        if not quotes_list:
            print("⚠️ لم يتم جلب إقتباسات في هذه الدورة.")
            return {"successCount": 0, "error": "تعذر جلب البيانات."}

        for quote in quotes_list:
            clean_quote = clean_quote_text(quote)

            if not is_valid_arabic_quote(clean_quote):
                continue

            matched_emoji = get_sad_emoji(clean_quote)
            # التنسيق باستخدام HTML لتفادي أخطاء Markdown
            safe_quote = html.escape(clean_quote)
            formatted_quote = f"<b>‏{safe_quote} {matched_emoji}</b>"

            try:
                await update.effective_chat.send_message(
                    text=formatted_quote, parse_mode="HTML"
                )
                success_count += 1
            except Exception as post_err:
                last_error = str(post_err)

            await asyncio.sleep(2.5)

    except Exception as err:
        last_error = str(err)

    print(f"✅ تم نشر {success_count} إقتباس بنجاح.")
    return {"successCount": success_count, "error": last_error}


# معالج الأوامر الرئيسي (quote, اقتباس, اقتباسات)
async def quote_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(
            "🤖 <b>جاري بدء توليد ونشر 15 إقتباساً...</b>", parse_mode="HTML"
        )

        result = await run_publish_job(update, context)

        if result["successCount"] == 0:
            safe_err = html.escape(str(result["error"]))
            await update.message.reply_text(
                f"❌ <b>فشل النشر:</b>\n<code>{safe_err}</code>",
                parse_mode="HTML",
            )
            return

        await update.message.reply_text(
            f"<b>✅ تم نشر [ {result['successCount']} ] إقتباساً بنجاح</b>",
            parse_mode="HTML",
        )

    except Exception as e:
        safe_exc = html.escape(str(e))
        await update.message.reply_text(
            f"❌ حدث خطأ غير متوقع: {safe_exc}", parse_mode="HTML"
        )


def main():
    # تشغيل خادم منفذ Railway في خلفية البرنامج
    threading.Thread(target=start_health_check_server, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler(["quote", "اقتباس", "اقتباسات"], quote_handler))
    app.add_handler(
        MessageHandler(
            filters.Regex(r"^(quote|اقتباس|اقتباسات)$") & ~filters.COMMAND,
            quote_handler,
        )
    )

    print("🤖 بوت التلغرام يعمل الآن...")
    app.run_polling()


if __name__ == "__main__":
    main()
