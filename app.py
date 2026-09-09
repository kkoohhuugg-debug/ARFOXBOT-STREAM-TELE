import asyncio
import random
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

# ----------------------------------------------------
# 1. كلاس المحاكاة (مطابق لمنطق JavaScript تماماً)
# ----------------------------------------------------
class FakeLikesSimulator:
    def __init__(self, target=1000000):
        self.likes = 0
        self.running = False
        self.speed = 100
        self.target = target
        self.started_at = None
        self.status = "⏸️ Stopped"
        self.task = None

    def random_likes(self):
        # min = 500, max = 5000
        return random.randint(500, 5000)

    def get_progress_bar(self, total_blocks=10):
        percent = min((self.likes / self.target), 1.0)
        filled = int(total_blocks * percent)
        bar = "🟩" * filled + "⬛" * (total_blocks - filled)
        return f"{bar} {percent * 100:.1f}%"

    def render_message(self):
        # تنسيق واجهة المستخدم لتناسب تلغرام
        return (
            "❤️ <b>Fake WhatsApp Likes</b>\n\n"
            f"<b>Likes:</b> <code>{self.likes:,}</code>\n\n"
            f"<b>Progress:</b>\n{self.get_progress_bar()}\n\n"
            f"<b>Status:</b> {self.status}\n"
            f"<b>⚡ Speed:</b> {self.speed:,} likes/sec"
        )

    def get_keyboard(self):
        # أزرار START / STOP / RESET
        keyboard = [
            [
                InlineKeyboardButton("▶️ START", callback_data="start"),
                InlineKeyboardButton("⏸️ STOP", callback_data="stop"),
                InlineKeyboardButton("🔄 RESET", callback_data="reset"),
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    def reset(self):
        self.running = False
        if self.task:
            self.task.cancel()
            self.task = None
        self.likes = 0
        self.speed = 0
        self.started_at = None
        self.status = "🔄 Reset"

    def set_target(self, number):
        if isinstance(number, (int, float)) and number > 0:
            self.target = number

    def set_speed(self, number):
        if isinstance(number, (int, float)) and number > 0:
            self.speed = number


# تخزين جلسات المستخدمين (Per User Session)
user_simulators = {}

def get_user_sim(user_id):
    if user_id not in user_simulators:
        user_simulators[user_id] = FakeLikesSimulator()
    return user_simulators[user_id]


# ----------------------------------------------------
# 2. أوامر ومعالجات تلغرام (Telegram Handlers)
# ----------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    sim = get_user_sim(user_id)

    await update.message.reply_text(
        text=sim.render_message(),
        parse_mode="HTML",
        reply_markup=sim.get_keyboard()
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    sim = get_user_sim(user_id)
    data = query.data

    if data == "start":
        if sim.running:
            return

        sim.running = True
        sim.started_at = time.time()
        sim.status = "🟢 Running..."

        # تشغيل دالة التكرار (Tick Loop) في الخلفية
        sim.task = asyncio.create_task(run_ticks(query, sim))

    elif data == "stop":
        sim.running = False
        if sim.task:
            sim.task.cancel()
            sim.task = None
        sim.status = "⏸️ Stopped"

        await query.edit_message_text(
            text=sim.render_message(),
            parse_mode="HTML",
            reply_markup=sim.get_keyboard()
        )

    elif data == "reset":
        sim.reset()
        await query.edit_message_text(
            text=sim.render_message(),
            parse_mode="HTML",
            reply_markup=sim.get_keyboard()
        )


async def run_ticks(query, sim: FakeLikesSimulator):
    """
    دالة الـ Tick المطابقة لـ setInterval:
    تقوم بالحساب بزيادات سريعة، وتحديث رسالة تلغرام كل 1 ثانية
    لتجنب حظر البوت بسبب Rate Limit الخاص بتلغرام.
    """
    try:
        last_ui_update = time.time()

        while sim.running:
            # تنفيذ العمليات الحسابية بنفس منطق randomLikes
            amount = sim.random_likes()
            sim.likes += amount
            sim.speed = amount * 10

            # التحقق من وصول الهدف
            if sim.likes >= sim.target:
                sim.likes = sim.target
                sim.running = False
                sim.status = "✅ Target reached"

                await query.edit_message_text(
                    text=sim.render_message(),
                    parse_mode="HTML",
                    reply_markup=sim.get_keyboard()
                )
                break

            # تحديث الواجهة على تلغرام كل 1 ثانية لتجنب 429 Too Many Requests
            if time.time() - last_ui_update >= 1.0:
                await query.edit_message_text(
                    text=sim.render_message(),
                    parse_mode="HTML",
                    reply_markup=sim.get_keyboard()
                )
                last_ui_update = time.time()

            # التأخير بين كل زيادة وزيادة (تطابق منطق الـ 10ms)
            await asyncio.sleep(0.01)

    except asyncio.CancelledError:
        pass


# ----------------------------------------------------
# 3. تشغيل البوت
# ----------------------------------------------------
if __name__ == "__main__":
    TOKEN = "8772396167:AAHoZFrU-QUCbUFzEwuCDl6Y3kBBtT2Iv8g"

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("❤️ Fake Likes Telegram Bot Started...")
    app.run_polling()

