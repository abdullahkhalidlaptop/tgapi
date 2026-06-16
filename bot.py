import os
import json
import asyncio
import datetime
from telethon import TelegramClient
from telethon.sessions import StringSession
from telegram import Update
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters, ContextTypes

# ========== CONFIGURATION ==========
# Get these from https://my.telegram.org/apps (your own developer account)
API_ID = 2040                    # Replace with your actual API ID
API_HASH = "b18441a1ff607e10a989891a5462e627"  # Replace with your actual API Hash
BOT_TOKEN = "8976825922:AAH1PxbJPgDmfkZRo7uwRK3oy9Wm39izrdE"  # Get from @BotFather on Telegram
# ===================================

# Conversation states
PHONE, CODE, PASSWORD = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the conversation and ask for phone number."""
    await update.message.reply_text(
        "🔐 **Telegram Session Generator**\n\n"
        "I will help you create a session string for your Telegram account.\n"
        "You only need to provide your phone number and the verification code.\n\n"
        "⚠️ **Security Notice:** The generated session string gives full access to your account. "
        "Keep it secret. I do not store any data after sending the file.\n\n"
        "Send your phone number in international format (e.g., `+1234567890`).",
        parse_mode="Markdown"
    )
    return PHONE

async def phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive phone number and send code request."""
    phone_number = update.message.text.strip()
    context.user_data['phone'] = phone_number

    # Create a temporary Telethon client
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    context.user_data['client'] = client

    await client.connect()
    try:
        await client.send_code_request(phone_number)
        await update.message.reply_text(
            "📨 A verification code has been sent to your Telegram app.\n"
            "Please enter the code (only numbers):"
        )
        return CODE
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}\nPlease try again with /start")
        await client.disconnect()
        return ConversationHandler.END

async def code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive verification code and try to sign in."""
    code = update.message.text.strip()
    client = context.user_data.get('client')
    phone = context.user_data['phone']

    try:
        await client.sign_in(phone, code)
    except Exception as e:
        error_msg = str(e)
        if "password" in error_msg.lower():
            await update.message.reply_text("🔐 Your account has 2FA enabled. Please enter your password:")
            return PASSWORD
        else:
            await update.message.reply_text(f"❌ Error: {error_msg}\nTry again with /start")
            await client.disconnect()
            return ConversationHandler.END

    # Authentication successful – generate session string
    session_string = client.session.save()
    me = await client.get_me()
    await client.disconnect()

    # Create credentials dictionary
    credentials = {
        "session_string": session_string,
        "phone_number": phone,
        "user_id": me.id,
        "username": me.username,
        "first_name": me.first_name,
        "created_date": datetime.datetime.now().isoformat()
    }

    # Save to JSON file
    filename = f"credentials_{me.id}.json"
    with open(filename, "w") as f:
        json.dump(credentials, f, indent=2)

    # Send file to user
    with open(filename, "rb") as f:
        await update.message.reply_document(
            document=f,
            filename="credentials.json",
            caption="✅ Here is your `credentials.json` file. Keep it safe!\n\nYou can now use this session string to authenticate with Telethon or other MTProto libraries."
        )

    # Clean up
    os.remove(filename)
    await update.message.reply_text("🎉 Done! The session file has been sent. Use /start to generate another.")
    return ConversationHandler.END

async def password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive 2FA password and complete sign in."""
    password = update.message.text.strip()
    client = context.user_data['client']
    phone = context.user_data['phone']

    try:
        await client.sign_in(password=password)
    except Exception as e:
        await update.message.reply_text(f"❌ Incorrect password or error: {str(e)}\nTry again with /start")
        await client.disconnect()
        return ConversationHandler.END

    # Same as successful code flow
    session_string = client.session.save()
    me = await client.get_me()
    await client.disconnect()

    credentials = {
        "session_string": session_string,
        "phone_number": phone,
        "user_id": me.id,
        "username": me.username,
        "first_name": me.first_name,
        "created_date": datetime.datetime.now().isoformat()
    }

    filename = f"credentials_{me.id}.json"
    with open(filename, "w") as f:
        json.dump(credentials, f, indent=2)

    with open(filename, "rb") as f:
        await update.message.reply_document(
            document=f,
            filename="credentials.json",
            caption="✅ Here is your `credentials.json` file. Keep it safe!"
        )

    os.remove(filename)
    await update.message.reply_text("🎉 Done! Use /start to generate another session.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the conversation."""
    if 'client' in context.user_data:
        await context.user_data['client'].disconnect()
    await update.message.reply_text("❌ Cancelled. Send /start to begin again.")
    return ConversationHandler.END

def main():
    """Start the bot."""
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone)],
            CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, code)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, password)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    print("🤖 Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()