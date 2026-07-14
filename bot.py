import os
import logging
import anthropic
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from database import Database
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from ozon_agent import run_daily_brief

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = Database()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")

SYSTEM_PROMPT = """Ты личный помощник по имени Подручный. Ты помогаешь пользователю управлять задачами, напоминаниями и запоминаешь важную информацию о нём.

Когда пользователь просит что-то запомнить — отвечай что запомнил.
Когда пользователь просит напомнить о задаче — отвечай что установил напоминание.
Отвечай кратко, по-русски, дружелюбно."""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"Привет! Я Подручный\n\n"
        f"Твой Chat ID: {chat_id}\n\n"
        f"Команды:\n"
        f"/brief - получить аналитику Ozon прямо сейчас\n"
        f"/memory - что я о тебе знаю\n"
        f"/tasks - твои задачи\n"
        f"/clear - очистить историю"
    )


async def brief_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text("Собираю данные с Ozon, подожди минуту...")
    await run_daily_brief(chat_id)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text

    db.add_message(user_id, "user", user_message)

    history = db.get_history(user_id, limit=20)
    memory = db.get_memory(user_id)

    system = SYSTEM_PROMPT
    if memory:
        system += f"\n\nЧто ты знаешь о пользователе:\n{memory}"
    system += f"\n\nТекущая дата и время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"

    lower_msg = user_message.lower()

    if any(word in lower_msg for word in ["запомни", "запомнить", "не забудь что"]):
        db.add_memory(user_id, user_message)

    if any(word in lower_msg for word in ["напомни", "напоминание", "напомнить"]):
        db.add_task(user_id, user_message)

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            system=system,
            messages=history
        )
        reply = response.content[0].text
    except Exception as e:
        logger.error(f"Claude error: {e}")
        reply = "Что-то пошло не так, попробуй ещё раз"

    db.add_message(user_id, "assistant", reply)
    await update.message.reply_text(reply)


async def memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    memory = db.get_memory(user_id)
    if memory:
        await update.message.reply_text(f"Вот что я о тебе знаю:\n\n{memory}")
    else:
        await update.message.reply_text("Я пока ничего не запомнил о тебе!")


async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tasks = db.get_tasks(user_id)
    if tasks:
        text = "Твои задачи:\n\n"
        for i, task in enumerate(tasks, 1):
            text += f"{i}. {task}\n"
        await update.message.reply_text(text)
    else:
        await update.message.reply_text("У тебя пока нет задач!")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db.clear_history(user_id)
    await update.message.reply_text("История очищена!")


async def post_init(application):
    if OWNER_CHAT_ID:
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            run_daily_brief,
            'cron',
            hour=8,
            minute=0,
            args=[int(OWNER_CHAT_ID)]
        )
        scheduler.start()
        logger.info("Расписание установлено: бриф каждый день в 8:00")


def main():
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN не установлен!")

    app = Application.builder().token(token).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("brief", brief_command))
    app.add_handler(CommandHandler("memory", memory_command))
    app.add_handler(CommandHandler("tasks", tasks_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
