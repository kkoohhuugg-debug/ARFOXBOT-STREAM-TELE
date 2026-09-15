import asyncio
import html
import json
import os
import random
import re
import urllib.parse
import httpx
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TELEGRAM_TOKEN = "8984966726:AAGnqqbhtvfmQtF6oqBPJPrSwDqZIhiP3RQ"


def get_sad_emoji(quote_text: str) -> str:
    txt = quote_text.lower()
    if any(w in txt for w in ["موت", "فقد", "رحيل"]):
        return "🥀🖤"
    if any(w in txt for w in ["دموع", "بكاء", "مطر", "تبكي"]):
        return "🌧️💔"
    if any(w in txt for w in ["شوق", "حنين", "غياب", "اشتياق"]):
        return "🖤🕊️"
    if any(w in txt for w in ["قلب", "كسر", "جرح", "وجع"]):
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


async def call_gpt_api(prompt: str) -> str:
    encoded_prompt = urllib.parse.quote(prompt)
    url = f"https://engez.a7a.online/api/v1/ai/gpt?q={encoded_prompt}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.get(url, headers=headers)
            res_data = response.json()
        except Exception as e:
            raise Exception(f"خطأ اتصال بالمزود: {str(e)}")

        if res_data.get("success") and res_data.get("response", {}).get("success"):
            resp = res_data.get("response", {})
            return resp.get("result", {}).get("message") or resp.get("raw") or ""
        else:
            raise Exception("لم يتوفر رد صالح من AI")


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


async def run_publish_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    success_count = 0
    last_error = ""

    try:
        quotes_list = await generate_exactly_15_quotes()

        if not quotes_list:
            return {"successCount": 0, "error": "تعذر جلب البيانات من الذكاء الاصطناعي."}

        for quote in quotes_list:
            clean_quote = clean_quote_text(quote)
            if not is_valid_arabic_quote(clean_quote):
                continue

            matched_emoji = get_sad_emoji(clean_quote)
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

    return {"successCount": success_count, "error": last_error}


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
    print("🤖 البوت يعمل بنجاح...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler(["quote", "اقتباس", "اقتباسات"], quote_handler))
    app.add_handler(
        MessageHandler(
            filters.Regex(r"^(quote|اقتباس|اقتباسات)$") & ~filters.COMMAND,
            quote_handler,
        )
    )
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
