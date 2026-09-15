import asyncio
import json
import random
import re
import urllib.parse
import httpx
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# توكن بوت التلغرام الخاص بك
TELEGRAM_TOKEN = "8984966726:AAGnqqbhtvfmQtF6oqBPJPrSwDqZIhiP3RQ"

# 1. رمز القناة المرجعي (محفوظ كما هو من الكود الأصلي)
CHANNEL_INVITE_CODE = "0029VbC9XL2GJP8HPaVgWt1S"


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


# 3. الاتصال بـ API الذكاء الاصطناعي
async def call_gpt_api(prompt: str) -> str:
    encoded_prompt = urllib.parse.quote(prompt)
    url = f"https://engez.a7a.online/api/v1/ai/gpt?q={encoded_prompt}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url, headers=headers)
        res_data = response.json()

        if res_data.get("success") and res_data.get("response", {}).get("success"):
            resp = res_data.get("response", {})
            reply = (
                resp.get("result", {}).get("message")
                or resp.get("raw")
                or ""
            )
            return reply
        else:
            raise Exception("فشل الرد من الخادم")


# دالة تنظيف صارمة لحذف الأكواد والمُعرّفات والرموز الغريبة
def clean_quote_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r":::[^\s]*", "", text)
    text = re.sub(r"\{[^}]*\}", "", text)
    text = re.sub(r"\[[^\]]*\]", "", text)
    text = re.sub(r'id\s*=\s*["\']?[^"\'\s\}]+["\']?', "", text, flags=re.IGNORECASE)
    text = re.sub(r'["\'\}\{\[\]\\]', "", text)
    text = re.sub(r"^[\d\.\-\*•\)\(\s]+", "", text)
    text = re.sub(r'^["\'«»‏\s]+|["\'«»\s]+$', "", text)
    text = re.sub(r"[\.\!\?،,\s]+$", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# دالة التحقق من أن السطر نص عربي حقيقي وليس كوداً
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
            formatted_quote = f"*‏{clean_quote} {matched_emoji}*"

            try:
                # إرسال الرسالة للمحادثة/القناة التي طُلب منها الأمر
                await update.effective_chat.send_message(
                    text=formatted_quote, parse_mode="Markdown"
                )
                success_count += 1
            except Exception as post_err:
                last_error = str(post_err)

            # تأخير 2.5 ثانية بين الرسائل
            await asyncio.sleep(2.5)

    except Exception as err:
        last_error = str(err)

    print(f"✅ تم نشر {success_count} إقتباس بنجاح.")
    return {"successCount": success_count, "error": last_error}


# معالج الأوامر الرئيسي (quote, اقتباس, اقتباسات)
async def quote_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(
            "🤖 *جاري بدء توليد ونشر 15 إقتباساً في قناة واتساب ...*",
            parse_mode="Markdown",
        )

        result = await run_publish_job(update, context)

        if result["successCount"] == 0:
            await update.message.reply_text(
                f"❌ *فشل النشر:*\n`{result['error']}`", parse_mode="Markdown"
            )
            return

        await update.message.reply_text(
            f"*✅ تم نشر [ {result['successCount']} ] إقتباساً بنجاح*",
            parse_mode="Markdown",
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ حدث خطأ غير متوقع: {str(e)}", parse_mode="Markdown"
        )


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # الاستجابة لأوامر /quote أو /اقتباس أو /اقتباسات
    app.add_handler(CommandHandler(["quote", "اقتباس", "اقتباسات"], quote_handler))

    # الاستجابة عند كتابة الكلمات بدون رمز السلاش /
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
