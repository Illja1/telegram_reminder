from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
import logging
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import asyncio
import uuid
from db import db, REMINDER_COLLECTION
from token_1 import Token
from pytz import timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler


SELECT_REMINDER_TIME = range(1)
ENTER_REMINDER_TEXT, ENTER_REMINDER_TIME, SELECT_REMINDER_TIME, SELECT_CUSTOM_TIME_OPTION, ENTER_CUSTOM_TIME = range(
    5)

ukraine_timezone = timezone('Europe/Kiev')
scheduler = AsyncIOScheduler(timezone=ukraine_timezone)
scheduler.start()


def calculate_actual_time(selected_time):
    now = datetime.now()

    if selected_time == "Morning":
        reminder_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
    elif selected_time == "Afternoon":
        reminder_time = now.replace(hour=14, minute=0, second=0, microsecond=0)
    elif selected_time == "Evening":
        reminder_time = now.replace(hour=18, minute=0, second=0, microsecond=0)
    else:

        return None

    if reminder_time <= now:
        reminder_time += timedelta(days=1)

    return reminder_time.strftime('%Y-%m-%d %H:%M:%S')


logger = logging.getLogger(__name__)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


async def send_welcome_menu(update: Update, context: CallbackContext, include_welcome=True):
    if include_welcome:
        welcome_message = "Welcome to EventEchoBot, press menu to choose options"
    else:
        welcome_message = "Select an option:"

    keyboard = main_menu_keyboard()

    await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_message, reply_markup=keyboard)


def main_menu_keyboard():
    keyboard = [[InlineKeyboardButton('Set a reminder', callback_data='m1')],
                [InlineKeyboardButton('View reminder', callback_data='m2')],
                [InlineKeyboardButton('About bot', callback_data='m3')]]
    return InlineKeyboardMarkup(keyboard)


def start(update: Update, context: CallbackContext):
    context.job_queue.run_once(lambda _: asyncio.create_task(
        send_welcome_menu(update, context)), 0)


async def main_menu_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    callback_data = query.data

    if callback_data == 'm1':
        set_reminder(update, context)
    elif callback_data == 'm2':
        await display_user_reminders(update, update.effective_user.id, context)
    elif callback_data == 'm3':
        await about(update, context)
    else:
        pass

    await query.edit_message_text(text="Main Menu:", reply_markup=main_menu_keyboard())


async def set_reminder(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    await context.bot.send_message(chat_id=user_id, text="Please enter your reminder message:")

    context.user_data['conversation_state'] = ENTER_REMINDER_TEXT

    context.user_data['reminder_scheduled'] = True


async def send_notification(user_id, reminder_message, context, reminder_id):
    await context.bot.send_message(chat_id=user_id, text=f"Reminder: {reminder_message}")

    reminder_collection = db[REMINDER_COLLECTION]
    result = reminder_collection.delete_one({"_id": ObjectId(reminder_id)})
    if result.deleted_count > 0:
        print(f"Reminder with ID {reminder_id} deleted from the database")
    else:
        print(
            f"Failed to delete reminder with ID {reminder_id} from the database")


async def handle_user_message(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if 'conversation_state' not in context.user_data:
        return

    if context.user_data['conversation_state'] == ENTER_REMINDER_TEXT:
        if context.user_data['conversation_state'] == ENTER_REMINDER_TEXT:
            if update.message.text.lower() == "quit":
                await context.bot.send_message(chat_id=user_id, text="Reminder creation cancelled.")
                await send_welcome_menu(update, context, include_welcome=False)
                del context.user_data['conversation_state']
                return
        context.user_data['reminder_message'] = update.message.text

        keyboard = ReplyKeyboardMarkup([
            [KeyboardButton("Morning"), KeyboardButton("Afternoon")],
            [KeyboardButton("Evening"), KeyboardButton("Custom Time")]
        ], resize_keyboard=True, one_time_keyboard=True)
        await context.bot.send_message(chat_id=user_id, text="Please select the reminder time:", reply_markup=keyboard)

        context.user_data['conversation_state'] = SELECT_REMINDER_TIME
    elif context.user_data['conversation_state'] == SELECT_REMINDER_TIME:
        selected_time = update.message.text
        if selected_time == "Custom Time":
            keyboard = ReplyKeyboardMarkup([
                [KeyboardButton("Set by Hour"),
                 KeyboardButton("Set by Minutes")]
            ], resize_keyboard=True, one_time_keyboard=True)
            await context.bot.send_message(chat_id=user_id, text="Please select how to set the custom time:", reply_markup=keyboard)
            context.user_data['conversation_state'] = SELECT_CUSTOM_TIME_OPTION
        else:
            reminder_time = calculate_actual_time(selected_time)

            reminder_message = context.user_data['reminder_message']
            reminder_data = {
                "user_id": user_id,
                "reminder_message": reminder_message,
                "reminder_time": reminder_time
            }

            db[REMINDER_COLLECTION].insert_one(reminder_data)

            selected_time_message = f"Selected time: {selected_time}" if reminder_time else ""
            message = f"Setting a reminder for user {user_id}:\nReminder: {context.user_data['reminder_message']}\n{selected_time_message}"
            await context.bot.send_message(chat_id=user_id, text=message)
            await send_welcome_menu(update, context, include_welcome=False)

            del context.user_data['conversation_state']
            del context.user_data['reminder_message']
    elif context.user_data['conversation_state'] == SELECT_CUSTOM_TIME_OPTION:
        custom_time_option = update.message.text
        if custom_time_option == "Set by Hour":
            await context.bot.send_message(chat_id=user_id, text="Please enter the number of hours for the reminder:")
            context.user_data['custom_time_option'] = "hour"
            context.user_data['conversation_state'] = ENTER_CUSTOM_TIME
        elif custom_time_option == "Set by Minutes":
            await context.bot.send_message(chat_id=user_id, text="Please enter the number of minutes for the reminder:")
            context.user_data['custom_time_option'] = "minute"
            context.user_data['conversation_state'] = ENTER_CUSTOM_TIME
    elif context.user_data['conversation_state'] == ENTER_CUSTOM_TIME:

        custom_time_input = update.message.text
        try:
            custom_time = int(custom_time_input)
            if context.user_data['custom_time_option'] == "hour":
                reminder_time = datetime.now() + timedelta(hours=custom_time)
            elif context.user_data['custom_time_option'] == "minute":
                reminder_time = datetime.now() + timedelta(minutes=custom_time)

            formatted_reminder_time = reminder_time.strftime(
                '%Y-%m-%d %H:%M:%S')

            selected_time = formatted_reminder_time
            message = f"Setting a reminder for user {user_id}:\nReminder: {context.user_data['reminder_message']}\nTime: {selected_time}"
            await context.bot.send_message(chat_id=user_id, text=message)
            await send_welcome_menu(update, context, include_welcome=False)

            reminder_message = context.user_data['reminder_message']
            reminder_data = {
                "user_id": user_id,
                "reminder_message": reminder_message,
                "reminder_time": formatted_reminder_time
            }

            db[REMINDER_COLLECTION].insert_one(reminder_data)

            del context.user_data['conversation_state']
            del context.user_data['reminder_message']
            del context.user_data['custom_time_option']
        except ValueError:
            await context.bot.send_message(chat_id=user_id, text="Invalid input. Please enter a valid number.")


async def about(update: Update, context: CallbackContext):
    about_message = "EventEchoBot is a reminder bot that helps you manage your tasks and events. You can set reminders, view upcoming events, and more."
    user_id = update.effective_user.id
    logger.info(f"User {user_id} requested information about the bot.")

    await context.bot.send_message(chat_id=update.effective_chat.id, text=about_message)

    await send_welcome_menu(update, context, include_welcome=False)


async def get_reminders_for_user(user_id):
    reminders_cursor = db[REMINDER_COLLECTION].find({"user_id": user_id})
    reminders = [reminder for reminder in reminders_cursor]
    return reminders


async def display_user_reminders(update: Update, user_id, context):
    reminders = await get_reminders_for_user(user_id)

    if not reminders:
        await context.bot.send_message(chat_id=user_id, text="You don't have any reminders.")
        await send_welcome_menu(update, context, include_welcome=False)
        return

    for reminder in reminders:
        reminder_time = reminder['reminder_time']
        reminder_msg = reminder['reminder_message']

        reminder_timestamp = datetime.strptime(
            reminder_time, '%Y-%m-%d %H:%M:%S')

        if not scheduler.get_job(str(reminder['_id'])):
            job_id = str(uuid.uuid4())

            scheduler.add_job(
                send_notification,
                'date',
                run_date=reminder_timestamp,
                args=[user_id, reminder_msg, context, str(reminder['_id'])],
                id=job_id
            )

        cancel_button = InlineKeyboardButton(
            "Cancel", callback_data=f"cancel_{reminder['_id']}")
        keyboard = InlineKeyboardMarkup([[cancel_button]])

        reminder_message = f"Reminder: {reminder_msg}\nTime: {reminder_time}"
        await context.bot.send_message(chat_id=user_id, text=reminder_message, reply_markup=keyboard)


async def cancel_reminder(update: Update, context: CallbackContext):
    query = update.callback_query
    reminder_id = query.data.split("_")[1]

    reminder_collection = db[REMINDER_COLLECTION]

    result = reminder_collection.delete_one({"_id": ObjectId(reminder_id)})

    if result.deleted_count > 0:
        await query.answer(text="Reminder cancelled")
    else:
        await query.answer(text="Reminder not found")

    await display_user_reminders(update, update.effective_user.id, context)

if __name__ == "__main__":
    app = ApplicationBuilder().token(Token).build()

    start_handler = CommandHandler('start', start)
    about_handler = CommandHandler('about', about)
    set_reminder_handler = CallbackQueryHandler(set_reminder, pattern='m1')
    view_reminder_handler = CallbackQueryHandler(
        display_user_reminders, pattern='m2')
    main_menu_handler = CallbackQueryHandler(
        main_menu_callback, pattern='m[1-3]')
    message_handler = MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_user_message)
    cancel_reminder_handler = CallbackQueryHandler(
        cancel_reminder, pattern=r'^cancel_')

    app.add_handler(start_handler)
    app.add_handler(about_handler)
    app.add_handler(set_reminder_handler)
    app.add_handler(main_menu_handler)
    app.add_handler(message_handler)
    app.add_handler(cancel_reminder_handler)

    app.run_polling()
