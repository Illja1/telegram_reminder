from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext,CallbackQueryHandler,MessageHandler,filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup,ReplyKeyboardMarkup, KeyboardButton
import logging
from datetime import datetime, timedelta
import asyncio
from db import db, REMINDER_COLLECTION
from token_1 import Token

SELECT_REMINDER_TIME = range(1)
ENTER_REMINDER_TEXT, ENTER_REMINDER_TIME, SELECT_REMINDER_TIME, SELECT_CUSTOM_TIME_OPTION, ENTER_CUSTOM_TIME = range(5)



def calculate_actual_time(selected_time):
    now = datetime.now()  # Corrected line
    
    if selected_time == "Morning":
        reminder_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
    elif selected_time == "Afternoon":
        reminder_time = now.replace(hour=14, minute=0, second=0, microsecond=0)
    elif selected_time == "Evening":
        reminder_time = now.replace(hour=18, minute=0, second=0, microsecond=0)
    else:
        # For "Custom Time", you can prompt the user to enter a specific time
        return None
    
    # If the calculated time is in the past, set it for the same time on the next day
    if reminder_time <= now:
        reminder_time += timedelta(days=1)  # Corrected line
    
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
       set_reminder(update, context)
    elif callback_data == 'm2':
       await display_user_reminders(update, update.effective_user.id, context)
    elif callback_data == 'm3':
        pass  # обробка видалення
    elif callback_data == 'm4':
        await about(update, context) 
    else:
        pass  # тут будуть помилки

    await query.edit_message_text(text="Main Menu:", reply_markup=main_menu_keyboard())  



# Define the function to set a reminder
async def set_reminder(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    await context.bot.send_message(chat_id=user_id, text="Please enter your reminder message:")

    # Update the conversation state
    context.user_data['conversation_state'] = ENTER_REMINDER_TEXT

# Handle user messages during the conversation
async def handle_user_message(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if 'conversation_state' not in context.user_data:
        return

    if context.user_data['conversation_state'] == ENTER_REMINDER_TEXT:
        context.user_data['reminder_message'] = update.message.text
        
        # Provide predefined time selection options
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
                [KeyboardButton("Set by Hour"), KeyboardButton("Set by Minutes")]
            ], resize_keyboard=True, one_time_keyboard=True)
            await context.bot.send_message(chat_id=user_id, text="Please select how to set the custom time:", reply_markup=keyboard)
            context.user_data['conversation_state'] = SELECT_CUSTOM_TIME_OPTION
        else:
            reminder_time = calculate_actual_time(selected_time)  # Implement this function to calculate the reminder time
            
            # Store the reminder in the database
            reminder_message = context.user_data['reminder_message']
            reminder_data = {
                "user_id": user_id,
                "reminder_message": reminder_message,
                "reminder_time": reminder_time
            }
            
            # Insert the reminder data into the MongoDB collection
            db[REMINDER_COLLECTION].insert_one(reminder_data)
            
            selected_time_message = f"Selected time: {selected_time}" if reminder_time else ""
            message = f"Setting a reminder for user {user_id}:\nReminder: {context.user_data['reminder_message']}\n{selected_time_message}"
            await context.bot.send_message(chat_id=user_id, text=message)
            await send_welcome_menu(update, context, include_welcome=False)

            # Reset conversation state
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
        # Handle custom time entry based on the selected option (hour or minute)
        custom_time_input = update.message.text
        try:
            custom_time = int(custom_time_input)
            if context.user_data['custom_time_option'] == "hour":
                reminder_time = datetime.now() + timedelta(hours=custom_time)
            elif context.user_data['custom_time_option'] == "minute":
                reminder_time = datetime.now() + timedelta(minutes=custom_time)
            
            formatted_reminder_time = reminder_time.strftime('%Y-%m-%d %H:%M:%S')

            selected_time = formatted_reminder_time
            message = f"Setting a reminder for user {user_id}:\nReminder: {context.user_data['reminder_message']}\nTime: {selected_time}"
            await context.bot.send_message(chat_id=user_id, text=message)
            await send_welcome_menu(update, context, include_welcome=False)

            # Store the reminder in the database
            reminder_message = context.user_data['reminder_message']
            reminder_data = {
                "user_id": user_id,
                "reminder_message": reminder_message,
                "reminder_time": formatted_reminder_time
            }

            # Insert the reminder data into the MongoDB collection
            db[REMINDER_COLLECTION].insert_one(reminder_data)

            # Reset conversation state
            del context.user_data['conversation_state']
            del context.user_data['reminder_message']
            del context.user_data['custom_time_option']

            # Print the reminder_data for verification
            print(reminder_data)
        except ValueError:
            await context.bot.send_message(chat_id=user_id, text="Invalid input. Please enter a valid number.")


            
async def about(update: Update, context: CallbackContext):
    about_message = "EventEchoBot is a reminder bot that helps you manage your tasks and events. You can set reminders, view upcoming events, and more."
    user_id = update.effective_user.id  # Get the user ID
    logger.info(f"User {user_id} requested information about the bot.")
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=about_message)
    
    # After sending the about message, display the main menu without 
            

    
    # After sending the about message, display the main menu without the welcome message
    await send_welcome_menu(update, context, include_welcome=False)

async def about(update: Update, context: CallbackContext):
    about_message = "EventEchoBot is a reminder bot that helps you manage your tasks and events. You can set reminders, view upcoming events, and more."
    user_id = update.effective_user.id  # Get the user ID
    logger.info(f"User {user_id} requested information about the bot.")
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=about_message)
    
    # After sending the about message, display the main menu without the welcome message
    await send_welcome_menu(update, context, include_welcome=False)
    
def get_reminders_for_user(user_id):
    reminders = db[REMINDER_COLLECTION].find({"user_id": user_id})
    return list(reminders)

async def display_user_reminders(update: Update,user_id, context):
    reminders = get_reminders_for_user(user_id)

    if not reminders:
        await context.bot.send_message(chat_id=user_id, text="You don't have any reminders.")
        return

    reminder_message = "Your reminders:\n"
    for reminder in reminders:
        reminder_time = reminder['reminder_time']
        reminder_msg = reminder['reminder_message']
        reminder_message += f"- Reminder: {reminder_msg}\n  Time: {reminder_time}\n"

    await context.bot.send_message(chat_id=user_id, text=reminder_message)
    await send_welcome_menu(update, context, include_welcome=False)

if __name__ == "__main__":
    app = ApplicationBuilder().token(Token).build()
    
    start_handler = CommandHandler('start', start)
    about_handler = CommandHandler('about', about)
    set_reminder_handler = CallbackQueryHandler(set_reminder, pattern='m1')
    view_reminder_handler = CallbackQueryHandler(display_user_reminders,pattern='m2')
    main_menu_handler = CallbackQueryHandler(main_menu_callback, pattern='m[1-4]')
    message_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message)

    app.add_handler(start_handler)
    app.add_handler(about_handler)
    app.add_handler(set_reminder_handler)
    app.add_handler(main_menu_handler)
    app.add_handler(message_handler)

    app.run_polling()