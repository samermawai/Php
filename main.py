import os
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler

# Environment variables
TOKEN = os.getenv('TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
ADMIN_ID = int(os.getenv('ADMIN_ID'))

# Global state
waiting_user = None
connections = {}
all_users = set()
waiting_start_time = None

# Command handlers
def start(bot, update):
    user_id = update.message.from_user.id
    all_users.add(user_id)
    update.message.reply_text(
        "🌐 Welcome to Anonymous Chat Bot!\n"
        "Use /connect to find a partner or /invite to invite friends!"
    )

def connect(bot, update):
    global waiting_user, waiting_start_time
    user_id = update.message.from_user.id if hasattr(update, 'message') else update.from_user.id
    
    if user_id in connections:
        update.message.reply_text("⚠️ You're already in a chat! Use /disconnect first.")
        return
    
    if waiting_user == user_id:
        update.message.reply_text("⏳ Already searching for a partner...")
        return

    if not waiting_user:
        waiting_user = user_id
        waiting_start_time = time.time()
        update.message.reply_text("⏳ Searching for a partner...")
    else:
        # Pair users
        connections[user_id] = waiting_user
        connections[waiting_user] = user_id
        bot.send_message(waiting_user, "✅ Connected! Start chatting!")
        update.message.reply_text("✅ Connected! Start chatting!")
        waiting_user = None
        waiting_start_time = None

def invite(bot, update):
    try:
        invite_link = bot.exportChatInviteLink(chat_id=CHAT_ID)
        update.message.reply_text(
            f"Invite friends: {invite_link}\n"
            "More users = better matches! 🚀"
        )
    except Exception as e:
        update.message.reply_text("❌ Failed to generate invite link. Ensure I'm a group admin.")
        print(f"Invite Error: {e}")

def forward_message(bot, update):
    user_id = update.message.from_user.id
    if user_id in connections:
        partner_id = connections[user_id]
        bot.send_message(partner_id, f"💬 {update.message.text}")
    else:
        update.message.reply_text("❌ Not connected! Use /connect first.")

def disconnect(bot, update):
    user_id = update.message.from_user.id
    if user_id in connections:
        partner_id = connections[user_id]
        del connections[user_id], connections[partner_id]
        bot.send_message(partner_id, "🚪 Partner disconnected. Use /connect to restart.")
        update.message.reply_text("✅ Disconnected!")
    else:
        update.message.reply_text("❌ No active connection!")

def reveal(bot, update):
    user_id = update.message.from_user.id
    if user_id in connections:
        partner_id = connections[user_id]
        keyboard = [
            [InlineKeyboardButton("Yes ✅", callback_data=f"reveal_yes_{user_id}"),
             InlineKeyboardButton("No ❌", callback_data=f"reveal_no_{user_id}")]
        ]
        bot.send_message(
            partner_id,
            "🤔 Partner wants to reveal identities! Allow?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        update.message.reply_text("⏳ Waiting for partner's response...")
    else:
        update.message.reply_text("❌ Not connected!")

def button(bot, update):
    query = update.callback_query
    data = query.data
    user_id = int(data.split('_')[-1])
    partner_id = query.from_user.id

    if "reveal_yes" in data and connections.get(partner_id) == user_id:
        # Get names safely
        user_info = bot.get_chat(user_id)
        partner_info = bot.get_chat(partner_id)
        user_name = user_info.first_name or "Anonymous"
        partner_name = partner_info.first_name or "Anonymous"
        
        bot.send_message(partner_id, f"🎉 Partner: {user_name}")
        bot.send_message(user_id, f"🎉 Partner: {partner_name}")
        query.edit_message_text("✅ Identities revealed!")
    elif "reveal_no" in data:
        bot.send_message(user_id, "❌ Partner declined identity reveal.")
        query.edit_message_text("Request declined!")
    elif data == "try_again":
        waiting_user = None  # Reset waiting state
        connect(bot, query.message)  # Retry connection
        query.edit_message_text("🔄 Retrying connection...")
    query.answer()

def check_timeout(bot, job):
    global waiting_user, waiting_start_time
    if waiting_user and (time.time() - waiting_start_time > 45):
        keyboard = [[InlineKeyboardButton("Retry 🔄", callback_data="try_again")]]
        bot.send_message(
            waiting_user,
            "⏰ No users found. Try again or invite friends!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        waiting_user = None

def broadcast(bot, update):
    user_id = update.message.from_user.id
    if user_id == ADMIN_ID:
        message = ' '.join(update.message.text.split()[1:])
        for uid in all_users:
            try:
                bot.send_message(uid, f"📢 Admin Announcement: {message}")
            except Exception as e:
                print(f"Broadcast failed to {uid}: {e}")
        update.message.reply_text("✅ Broadcast sent!")
    else:
        update.message.reply_text("⛔ Admin-only command!")

def main():
    updater = Updater(TOKEN, use_context=False)
    dp = updater.dispatcher

    # Add handlers
    handlers = [
        CommandHandler('start', start),
        CommandHandler('connect', connect),
        CommandHandler('disconnect', disconnect),
        CommandHandler('invite', invite),
        CommandHandler('reveal', reveal),
        CommandHandler('broadcast', broadcast),
        MessageHandler(Filters.text & ~Filters.command, forward_message),
        CallbackQueryHandler(button)
    ]
    for handler in handlers:
        dp.add_handler(handler)

    # Timeout checker
    updater.job_queue.run_repeating(check_timeout, interval=5)

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
