from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext,CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import logging
import asyncio

logger = logging.getLogger(__name__)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


async def send_welcome_menu(update: Update, context: CallbackContext, include_welcome=True):
    if include_welcome:
        welcome_message = "Welcome to EventEchoBot, press menu to choose options"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_message, reply_markup=main_menu_keyboard())
    else:
        keyboard = main_menu_keyboard()
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Select an option:", reply_markup=keyboard)

    await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_message, reply_markup=keyboard)

def main_menu_keyboard():
    keyboard = [[InlineKeyboardButton('Set a reminder', callback_data='m1')],
                [InlineKeyboardButton('View reminder', callback_data='m2')],
                [InlineKeyboardButton('Cancel reminder', callback_data='m3')],
                [InlineKeyboardButton('About bot', callback_data='m4')]]
    return InlineKeyboardMarkup(keyboard)

def start(update: Update, context: CallbackContext):
    context.job_queue.run_once(lambda _: asyncio.create_task(send_welcome_menu(update, context)), 0)

async def main_menu_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # очікуєм корутину

    callback_data = query.data

    if callback_data == 'm1':
        pass  # обробка встановлення
    elif callback_data == 'm2':
        pass  # обробка перегляду
    elif callback_data == 'm3':
        pass  # обробка видалення
    elif callback_data == 'm4':
        await about(update, context) 
    else:
        pass  # тут будуть помилки

    await query.edit_message_text(text="Main Menu:", reply_markup=main_menu_keyboard())  


async def about(update: Update, context: CallbackContext):
    about_message = "EventEchoBot is a reminder bot that helps you manage your tasks and events. You can set reminders, view upcoming events, and more."
    user_id = update.effective_user.id  # Get the user ID
    logger.info(f"User {user_id} requested information about the bot.")
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=about_message)
    
    # After sending the about message, display the main menu without the welcome message
    await send_welcome_menu(update, context, include_welcome=False)
    
    await send_welcome_menu(update, context, include_welcome=False)

    
if __name__ == "__main__":
    app = ApplicationBuilder().token("6327207738:AAEQdGOOk_nefapz9AHYHdkqaXUPL6JsBEE").build()
    
    start_handler = CommandHandler('start', start)
    about_handler = CommandHandler('about', about)
    main_menu_handler = CallbackQueryHandler(main_menu_callback, pattern='m[1-4]')

    app.add_handler(start_handler)
    app.add_handler(about_handler)
    app.add_handler(main_menu_handler)

    app.run_polling()