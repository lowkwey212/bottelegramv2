import logging
import sqlite3
import json
import random
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode
import asyncio

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = "7688520768:AAEcaPvYr1NG33qGxJgYL_inIOgoXGSc4Wg"
ADMIN_IDS = [7461947639]  # Add admin user IDs here
PAYMENT_QR_IMAGE = "qr.jpg"  # Path to your payment QR code image

class GameStoreBot:
    def __init__(self):
        self.init_database()
        
    def init_database(self):
        """Initialize the SQLite database"""
        conn = sqlite3.connect('gamestore.db')
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_admin INTEGER DEFAULT 0
        )
        ''')
        
        # Games table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            description TEXT,
            is_active INTEGER DEFAULT 1
        )
        ''')
        
        # Accounts table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            additional_info TEXT,
            is_sold INTEGER DEFAULT 0,
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (game_id) REFERENCES games (id)
        )
        ''')
        
        # Orders table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            game_id INTEGER,
            account_id INTEGER,
            status TEXT DEFAULT 'pending',
            payment_proof TEXT,
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            delivery_date TIMESTAMP,
            price REAL,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (game_id) REFERENCES games (id),
            FOREIGN KEY (account_id) REFERENCES accounts (id)
        )
        ''')
        
        # Payment history table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            order_id INTEGER,
            amount REAL,
            payment_proof TEXT,
            status TEXT DEFAULT 'pending',
            payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (order_id) REFERENCES orders (id)
        )
        ''')
        
        # Insert default games
        cursor.execute('SELECT COUNT(*) FROM games')
        if cursor.fetchone()[0] == 0:
            games = [
                ('Blox Fruit', 2.00, 'Random Account High level Have SG CDK Mytical fruit'),
                ('Car Parking Multiplayer', 0.5, 'Random Account High Money And Coin'),
                ('Mlbb', 4.00, 'Random Account But have skin 200+')
            ]
            cursor.executemany('INSERT INTO games (name, price, description) VALUES (?, ?, ?)', games)
        
        conn.commit()
        conn.close()
    
    def get_db_connection(self):
        """Get database connection"""
        return sqlite3.connect('gamestore.db')
    
    def is_admin(self, user_id):
        """Check if user is admin"""
        return user_id in ADMIN_IDS
    
    def register_user(self, user_id, username, first_name):
        """Register new user"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, is_admin)
        VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, 1 if user_id in ADMIN_IDS else 0))
        conn.commit()
        conn.close()

# Initialize bot instance
bot_instance = GameStoreBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = update.effective_user
    bot_instance.register_user(user.id, user.username, user.first_name)
    
    if bot_instance.is_admin(user.id):
        keyboard = [
            [KeyboardButton("🎮 Games Store"), KeyboardButton("👨‍💼 Admin Panel")],
            [KeyboardButton("📊 My Orders"), KeyboardButton("💳 Payment History")],
            [KeyboardButton("ℹ️ Help")]
        ]
    else:
        keyboard = [
            [KeyboardButton("🎮 Games Store")],
            [KeyboardButton("📊 My Orders"), KeyboardButton("💳 Payment History")],
            [KeyboardButton("ℹ️ Help")]
        ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    welcome_text = f"""
🎮 **Welcome to Gaming Store Bot!** 🎮

Hello {user.first_name}! 👋

Available Games:
• Blox Fruit 🏴‍☠️
• Car Parking Multiplayer 🚗
• Mobile Legends ⚔️

What would you like to do?
    """
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def games_store(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show games store"""
    conn = bot_instance.get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, price, description FROM games WHERE is_active = 1')
    games = cursor.fetchall()
    
    # Get stock count for each game
    game_stock = {}
    for game in games:
        cursor.execute('SELECT COUNT(*) FROM accounts WHERE game_id = ? AND is_sold = 0', (game[0],))
        stock = cursor.fetchone()[0]
        game_stock[game[0]] = stock
    
    conn.close()
    
    keyboard = []
    store_text = "🎮 **GAMES STORE** 🎮\n\n"
    
    for game in games:
        game_id, name, price, description = game
        stock = game_stock[game_id]
        
        if stock > 0:
            store_text += f"🎯 **{name}**\n"
            store_text += f"💰 Price: ${price:.2f}\n"
            store_text += f"📦 Stock: {stock} accounts\n"
            store_text += f"📝 {description}\n\n"
            
            keyboard.append([InlineKeyboardButton(f"Buy {name} - ${price:.2f}", callback_data=f"buy_{game_id}")])
        else:
            store_text += f"🎯 **{name}** ❌ OUT OF STOCK\n"
            store_text += f"💰 Price: ${price:.2f}\n"
            store_text += f"📝 {description}\n\n"
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(store_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(store_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def buy_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle game purchase"""
    query = update.callback_query
    await query.answer()
    
    game_id = int(query.data.split('_')[1])
    user_id = query.from_user.id
    
    # Get game info
    conn = bot_instance.get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT name, price FROM games WHERE id = ?', (game_id,))
    game_info = cursor.fetchone()
    
    if not game_info:
        await query.edit_message_text("❌ Game not found!")
        return
    
    game_name, price = game_info
    
    # Check stock
    cursor.execute('SELECT COUNT(*) FROM accounts WHERE game_id = ? AND is_sold = 0', (game_id,))
    stock = cursor.fetchone()[0]
    
    if stock == 0:
        await query.edit_message_text(f"❌ Sorry, {game_name} is out of stock!")
        return
    
    # Create pending order
    cursor.execute('''
    INSERT INTO orders (user_id, game_id, status, price)
    VALUES (?, ?, 'pending_payment', ?)
    ''', (user_id, game_id, price))
    
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Send payment instructions
    payment_text = f"""
💳 **PAYMENT REQUIRED** 💳

🎮 Game: {game_name}
💰 Price: ${price:.2f}
📋 Order ID: #{order_id}

📱 **Payment Instructions:**
1. Scan the QR code below
2. Send exactly ${price:.2f}
3. Take a screenshot of payment confirmation
4. Send the screenshot to this bot

⚠️ **Important:** Your order will be processed only after admin verification of payment proof.
    """
    
    keyboard = [[InlineKeyboardButton("✅ I've Made Payment", callback_data=f"payment_proof_{order_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send payment QR code
    try:
        with open(PAYMENT_QR_IMAGE, 'rb') as photo:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=photo,
                caption=payment_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
    except FileNotFoundError:
        await query.edit_message_text(
            payment_text + "\n\n❌ QR code image not found. Please contact admin.",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

async def payment_proof_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request payment proof"""
    query = update.callback_query
    await query.answer()
    
    order_id = int(query.data.split('_')[2])
    context.user_data['awaiting_payment_proof'] = order_id
    
    await query.edit_message_text(
        "📸 **Please send your payment proof screenshot now**\n\n"
        "Send the image showing your successful payment transaction."
    )

async def handle_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment proof image"""
    if 'awaiting_payment_proof' not in context.user_data:
        return
    
    if not update.message.photo:
        await update.message.reply_text("❌ Please send an image as payment proof.")
        return
    
    order_id = context.user_data['awaiting_payment_proof']
    user_id = update.effective_user.id
    
    # Get the largest photo
    photo = update.message.photo[-1]
    photo_file = await context.bot.get_file(photo.file_id)
    
    # Save photo
    photo_path = f"payment_proofs/proof_{order_id}_{user_id}.jpg"
    os.makedirs("payment_proofs", exist_ok=True)
    await photo_file.download_to_drive(photo_path)
    
    # Update order with payment proof
    conn = bot_instance.get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE orders SET payment_proof = ?, status = 'pending_approval'
    WHERE id = ? AND user_id = ?
    ''', (photo_path, order_id, user_id))
    
    # Add to payment history
    cursor.execute('SELECT price FROM orders WHERE id = ?', (order_id,))
    price = cursor.fetchone()[0]
    
    cursor.execute('''
    INSERT INTO payment_history (user_id, order_id, amount, payment_proof, status)
    VALUES (?, ?, ?, ?, 'pending')
    ''', (user_id, order_id, price, photo_path))
    
    conn.commit()
    conn.close()
    
    # Clear user data
    del context.user_data['awaiting_payment_proof']
    
    # Notify user
    await update.message.reply_text(
        "✅ Payment proof received!\n\n"
        f"📋 Order ID: #{order_id}\n"
        "⏳ Status: Waiting for admin approval\n\n"
        "You will receive your account details once the admin approves your payment."
    )
    
    # Notify all admins
    conn = bot_instance.get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT o.id, g.name, o.price, u.username, u.first_name
    FROM orders o
    JOIN games g ON o.game_id = g.id
    JOIN users u ON o.user_id = u.user_id
    WHERE o.id = ?
    ''', (order_id,))
    
    order_info = cursor.fetchone()
    conn.close()
    
    if order_info:
        order_id, game_name, price, username, first_name = order_info
        admin_text = f"""
🔔 **NEW PAYMENT RECEIVED** 🔔

📋 Order ID: #{order_id}
👤 Customer: {first_name} (@{username or 'N/A'})
🎮 Game: {game_name}
💰 Amount: ${price:.2f}

Please review the payment proof and approve/reject the order.
        """
        
        keyboard = [
            [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{order_id}")],
            [InlineKeyboardButton("❌ Reject", callback_data=f"reject_{order_id}")],
            [InlineKeyboardButton("👁️ View Proof", callback_data=f"view_proof_{order_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show admin panel"""
    user_id = update.effective_user.id
    
    if not bot_instance.is_admin(user_id):
        await update.message.reply_text("❌ You don't have admin privileges!")
        return
    
    keyboard = [
        [InlineKeyboardButton("➕ Add Account", callback_data="add_account")],
        [InlineKeyboardButton("📦 Manage Stock", callback_data="manage_stock")],
        [InlineKeyboardButton("📋 Pending Orders", callback_data="pending_orders")],
        [InlineKeyboardButton("📊 Sales Stats", callback_data="sales_stats")],
        [InlineKeyboardButton("💳 Payment History", callback_data="admin_payments")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    admin_text = """
👨‍💼 **ADMIN PANEL** 👨‍💼

Select an option to manage the store:
    """
    
    if update.callback_query:
        await update.callback_query.edit_message_text(admin_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(admin_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def add_account_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start adding account process"""
    query = update.callback_query
    await query.answer()
    
    if not bot_instance.is_admin(query.from_user.id):
        await query.edit_message_text("❌ Access denied!")
        return
    
    # Show games to select
    conn = bot_instance.get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM games WHERE is_active = 1')
    games = cursor.fetchall()
    conn.close()
    
    keyboard = []
    for game_id, game_name in games:
        keyboard.append([InlineKeyboardButton(game_name, callback_data=f"select_game_{game_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🎮 **SELECT GAME TO ADD ACCOUNT**\n\nChoose the game for the new account:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def select_game_for_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Select game for new account"""
    query = update.callback_query
    await query.answer()
    
    game_id = int(query.data.split('_')[2])
    context.user_data['adding_account_game_id'] = game_id
    
    # Get game name
    conn = bot_instance.get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM games WHERE id = ?', (game_id,))
    game_name = cursor.fetchone()[0]
    conn.close()
    
    context.user_data['adding_account_game_name'] = game_name
    context.user_data['awaiting_account_details'] = True
    
    await query.edit_message_text(
        f"📝 **ADDING ACCOUNT FOR {game_name.upper()}**\n\n"
        "Please send the account details in this format:\n\n"
        "```\n"
        "Username: your_username\n"
        "Password: your_password\n"
        "Email: your_email@example.com\n"
        "Additional Info: any extra info\n"
        "```\n\n"
        "⚠️ Make sure to include all details!",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_account_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new account details"""
    if not context.user_data.get('awaiting_account_details'):
        return
    
    if not bot_instance.is_admin(update.effective_user.id):
        return
    
    text = update.message.text
    lines = text.strip().split('\n')
    
    account_data = {}
    for line in lines:
        if ':' in line:
            key, value = line.split(':', 1)
            account_data[key.strip().lower()] = value.strip()
    
    if 'username' not in account_data or 'password' not in account_data:
        await update.message.reply_text(
            "❌ Invalid format! Please include at least Username and Password."
        )
        return
    
    game_id = context.user_data['adding_account_game_id']
    game_name = context.user_data['adding_account_game_name']
    
    # Add account to database
    conn = bot_instance.get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO accounts (game_id, username, password, email, additional_info)
    VALUES (?, ?, ?, ?, ?)
    ''', (
        game_id,
        account_data.get('username', ''),
        account_data.get('password', ''),
        account_data.get('email', ''),
        account_data.get('additional info', '')
    ))
    
    conn.commit()
    conn.close()
    
    # Clear user data
    del context.user_data['awaiting_account_details']
    del context.user_data['adding_account_game_id']
    del context.user_data['adding_account_game_name']
    
    await update.message.reply_text(
        f"✅ **Account Added Successfully!**\n\n"
        f"🎮 Game: {game_name}\n"
        f"👤 Username: {account_data.get('username', 'N/A')}\n"
        f"📧 Email: {account_data.get('email', 'N/A')}\n\n"
        "The account is now available in the store!",
        parse_mode=ParseMode.MARKDOWN
    )

async def approve_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Approve order and deliver account"""
    query = update.callback_query
    await query.answer()
    
    if not bot_instance.is_admin(query.from_user.id):
        await query.edit_message_text("❌ Access denied!")
        return
    
    order_id = int(query.data.split('_')[1])
    
    conn = bot_instance.get_db_connection()
    cursor = conn.cursor()
    
    # Get order details
    cursor.execute('''
    SELECT o.user_id, o.game_id, o.price, g.name, u.first_name
    FROM orders o
    JOIN games g ON o.game_id = g.id
    JOIN users u ON o.user_id = u.user_id
    WHERE o.id = ? AND o.status = 'pending_approval'
    ''', (order_id,))
    
    order_info = cursor.fetchone()
    
    if not order_info:
        await query.edit_message_text("❌ Order not found or already processed!")
        return
    
    user_id, game_id, price, game_name, customer_name = order_info
    
    # Get random available account
    cursor.execute('''
    SELECT id, username, password, email, additional_info
    FROM accounts
    WHERE game_id = ? AND is_sold = 0
    ORDER BY RANDOM()
    LIMIT 1
    ''', (game_id,))
    
    account = cursor.fetchone()
    
    if not account:
        await query.edit_message_text("❌ No accounts available for this game!")
        return
    
    account_id, username, password, email, additional_info = account
    
    # Mark account as sold and update order
    cursor.execute('UPDATE accounts SET is_sold = 1 WHERE id = ?', (account_id,))
    cursor.execute('''
    UPDATE orders SET status = 'completed', account_id = ?, delivery_date = CURRENT_TIMESTAMP
    WHERE id = ?
    ''', (account_id, order_id))
    
    # Update payment history
    cursor.execute('''
    UPDATE payment_history SET status = 'approved'
    WHERE order_id = ?
    ''', (order_id,))
    
    conn.commit()
    conn.close()
    
    # Send account to customer
    account_text = f"""
🎉 **ORDER APPROVED & DELIVERED!** 🎉

📋 Order ID: #{order_id}
🎮 Game: {game_name}
💰 Paid: ${price:.2f}

🔐 **YOUR ACCOUNT DETAILS:**
👤 Username: `{username}`
🔑 Password: `{password}`
📧 Email: `{email or 'Not provided'}`
ℹ️ Additional Info: {additional_info or 'None'}

⚠️ **Important:**
• Change password after first login
• Don't share account details
• Contact support if you face any issues

Thank you for your purchase! 🎮
    """
    
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=account_text,
            parse_mode=ParseMode.MARKDOWN
        )
        
        await query.edit_message_text(
            f"✅ **Order #{order_id} approved and delivered to {customer_name}!**\n\n"
            f"🎮 Game: {game_name}\n"
            f"💰 Amount: ${price:.2f}\n"
            f"👤 Account: {username}"
        )
        
    except Exception as e:
        await query.edit_message_text(f"❌ Failed to deliver account: {str(e)}")

async def reject_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reject order"""
    query = update.callback_query
    await query.answer()
    
    if not bot_instance.is_admin(query.from_user.id):
        await query.edit_message_text("❌ Access denied!")
        return
    
    order_id = int(query.data.split('_')[1])
    
    conn = bot_instance.get_db_connection()
    cursor = conn.cursor()
    
    # Get order details
    cursor.execute('''
    SELECT o.user_id, g.name, o.price, u.first_name
    FROM orders o
    JOIN games g ON o.game_id = g.id
    JOIN users u ON o.user_id = u.user_id
    WHERE o.id = ? AND o.status = 'pending_approval'
    ''', (order_id,))
    
    order_info = cursor.fetchone()
    
    if not order_info:
        await query.edit_message_text("❌ Order not found or already processed!")
        return
    
    user_id, game_name, price, customer_name = order_info
    
    # Update order status
    cursor.execute('UPDATE orders SET status = "rejected" WHERE id = ?', (order_id,))
    cursor.execute('UPDATE payment_history SET status = "rejected" WHERE order_id = ?', (order_id,))
    
    conn.commit()
    conn.close()
    
    # Notify customer
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"❌ **ORDER REJECTED**\n\n"
                f"📋 Order ID: #{order_id}\n"
                f"🎮 Game: {game_name}\n"
                f"💰 Amount: ${price:.2f}\n\n"
                f"Your payment proof was rejected. Please contact admin for more information.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        await query.edit_message_text(
            f"❌ **Order #{order_id} rejected!**\n\n"
            f"Customer {customer_name} has been notified."
        )
        
    except Exception as e:
        await query.edit_message_text(f"❌ Failed to notify customer: {str(e)}")

async def view_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View payment proof"""
    query = update.callback_query
    await query.answer()
    
    if not bot_instance.is_admin(query.from_user.id):
        await query.edit_message_text("❌ Access denied!")
        return
    
    order_id = int(query.data.split('_')[2])
    
    conn = bot_instance.get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT payment_proof FROM orders WHERE id = ?', (order_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result or not result[0]:
        await query.edit_message_text("❌ No payment proof found!")
        return
    
    proof_path = result[0]
    
    try:
        with open(proof_path, 'rb') as photo:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=photo,
                caption=f"💳 Payment proof for Order #{order_id}"
            )
    except FileNotFoundError:
        await query.edit_message_text("❌ Payment proof file not found!")

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's orders"""
    user_id = update.effective_user.id
    
    conn = bot_instance.get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT o.id, g.name, o.price, o.status, o.order_date, a.username
    FROM orders o
    JOIN games g ON o.game_id = g.id
    LEFT JOIN accounts a ON o.account_id = a.id
    WHERE o.user_id = ?
    ORDER BY o.order_date DESC
    LIMIT 10
    ''', (user_id,))
    
    orders = cursor.fetchall()
    conn.close()
    
    if not orders:
        text = "📋 **MY ORDERS**\n\nYou haven't made any orders yet!"
    else:
        text = "📋 **MY ORDERS**\n\n"
        
        for order in orders:
            order_id, game_name, price, status, order_date, account_username = order
            
            status_emoji = {
                'pending_payment': '⏳',
                'pending_approval': '🔍',
                'completed': '✅',
                'rejected': '❌'
            }.get(status, '❓')
            
            text += f"{status_emoji} **Order #{order_id}**\n"
            text += f"🎮 {game_name}\n"
            text += f"💰 ${price:.2f}\n"
            text += f"📅 {order_date.split()[0]}\n"
            
            if account_username and status == 'completed':
                text += f"👤 Account: {account_username}\n"
            
            text += f"Status: {status.replace('_', ' ').title()}\n\n"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def payment_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's payment history"""
    user_id = update.effective_user.id
    
    conn = bot_instance.get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT ph.id, ph.amount, ph.status, ph.payment_date, o.id as order_id, g.name
    FROM payment_history ph
    JOIN orders o ON ph.order_id = o.id
    JOIN games g ON o.game_id = g.id
    WHERE ph.user_id = ?
    ORDER BY ph.payment_date DESC
    LIMIT 10
    ''', (user_id,))
    
    payments = cursor.fetchall()
    conn.close()
    
    if not payments:
        text = "💳 **PAYMENT HISTORY**\n\nNo payment history found!"
    else:
        text = "💳 **PAYMENT HISTORY**\n\n"
        
        for payment in payments:
            payment_id, amount, status, payment_date, order_id, game_name = payment
            
            status_emoji = {
                'pending': '⏳',
                'approved': '✅',
                'rejected': '❌'
            }.get(status, '❓')
            
            text += f"{status_emoji} **Payment #{payment_id}**\n"
            text += f"📋 Order: #{order_id}\n"
            text += f"🎮 Game: {game_name}\n"
            text += f"💰 Amount: ${amount:.2f}\n"
            text += f"📅 Date: {payment_date.split()[0]}\n"
            text += f"Status: {status.title()}\n\n"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def sales_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show sales statistics (Admin only)"""
    query = update.callback_query
    await query.answer()
    
    if not bot_instance.is_admin(query.from_user.id):
        await query.edit_message_text("❌ Access denied!")
        return
    
    conn = bot_instance.get_db_connection()
    cursor = conn.cursor()
    
    # Total sales
    cursor.execute('SELECT COUNT(*), SUM(price) FROM orders WHERE status = "completed"')
    total_orders, total_revenue = cursor.fetchone()
    total_revenue = total_revenue or 0
    
    # Sales by game
    cursor.execute('''
    SELECT g.name, COUNT(*) as orders, SUM(o.price) as revenue
    FROM orders o
    JOIN games g ON o.game_id = g.id
    WHERE o.status = "completed"
    GROUP BY g.id, g.name
    ORDER BY revenue DESC
    ''')
    game_stats = cursor.fetchall()
    
    # Pending orders
    cursor.execute('SELECT COUNT(*) FROM orders WHERE status = "pending_approval"')
    pending_orders = cursor.fetchone()[0]
    
    # Stock status
    cursor.execute('''
    SELECT g.name, COUNT(a.id) as stock
    FROM games g
    LEFT JOIN accounts a ON g.id = a.game_id AND a.is_sold = 0
    WHERE g.is_active = 1
    GROUP BY g.id, g.name
    ''')
    stock_stats = cursor.fetchall()
    
    conn.close()
    
    text = "📊 **SALES STATISTICS**\n\n"
    text += f"💰 **Total Revenue:** ${total_revenue:.2f}\n"
    text += f"📦 **Total Orders:** {total_orders}\n"
    text += f"⏳ **Pending Orders:** {pending_orders}\n\n"
    
    text += "🎮 **Sales by Game:**\n"
    for game_name, orders, revenue in game_stats:
        text += f"• {game_name}: {orders} orders (${revenue:.2f})\n"
    
    text += "\n📦 **Current Stock:**\n"
    for game_name, stock in stock_stats:
        text += f"• {game_name}: {stock} accounts\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def manage_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manage stock (Admin only)"""
    query = update.callback_query
    await query.answer()
    
    if not bot_instance.is_admin(query.from_user.id):
        await query.edit_message_text("❌ Access denied!")
        return
    
    conn = bot_instance.get_db_connection()
    cursor = conn.cursor()
    
    # Get stock info
    cursor.execute('''
    SELECT g.id, g.name, 
           COUNT(CASE WHEN a.is_sold = 0 THEN 1 END) as available,
           COUNT(CASE WHEN a.is_sold = 1 THEN 1 END) as sold
    FROM games g
    LEFT JOIN accounts a ON g.id = a.game_id
    WHERE g.is_active = 1
    GROUP BY g.id, g.name
    ''')
    
    stock_info = cursor.fetchall()
    conn.close()
    
    text = "📦 **STOCK MANAGEMENT**\n\n"
    
    keyboard = []
    for game_id, game_name, available, sold in stock_info:
        text += f"🎮 **{game_name}**\n"
        text += f"✅ Available: {available}\n"
        text += f"❌ Sold: {sold}\n"
        text += f"📊 Total: {available + sold}\n\n"
        
        keyboard.append([InlineKeyboardButton(f"View {game_name} Accounts", callback_data=f"view_accounts_{game_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def view_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View accounts for specific game (Admin only)"""
    query = update.callback_query
    await query.answer()
    
    if not bot_instance.is_admin(query.from_user.id):
        await query.edit_message_text("❌ Access denied!")
        return
    
    game_id = int(query.data.split('_')[2])
    
    conn = bot_instance.get_db_connection()
    cursor = conn.cursor()
    
    # Get game name
    cursor.execute('SELECT name FROM games WHERE id = ?', (game_id,))
    game_name = cursor.fetchone()[0]
    
    # Get accounts
    cursor.execute('''
    SELECT id, username, email, is_sold, added_date
    FROM accounts
    WHERE game_id = ?
    ORDER BY is_sold, added_date DESC
    ''', (game_id,))
    
    accounts = cursor.fetchall()
    conn.close()
    
    text = f"📦 **{game_name.upper()} ACCOUNTS**\n\n"
    
    if not accounts:
        text += "No accounts found for this game."
    else:
        available_count = sum(1 for acc in accounts if not acc[3])
        sold_count = len(accounts) - available_count
        
        text += f"✅ Available: {available_count}\n"
        text += f"❌ Sold: {sold_count}\n\n"
        
        text += "**Available Accounts:**\n"
        for acc_id, username, email, is_sold, added_date in accounts:
            if not is_sold:
                text += f"• {username} ({email or 'No email'})\n"
        
        if sold_count > 0:
            text += f"\n**Recently Sold:**\n"
            sold_shown = 0
            for acc_id, username, email, is_sold, added_date in accounts:
                if is_sold and sold_shown < 5:
                    text += f"• {username} (Sold: {added_date.split()[0]})\n"
                    sold_shown += 1
    
    keyboard = [
        [InlineKeyboardButton("➕ Add Account", callback_data=f"select_game_{game_id}")],
        [InlineKeyboardButton("🔙 Back to Stock", callback_data="manage_stock")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def pending_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show pending orders (Admin only)"""
    query = update.callback_query
    await query.answer()
    
    if not bot_instance.is_admin(query.from_user.id):
        await query.edit_message_text("❌ Access denied!")
        return
    
    conn = bot_instance.get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT o.id, g.name, o.price, u.username, u.first_name, o.order_date, o.status
    FROM orders o
    JOIN games g ON o.game_id = g.id
    JOIN users u ON o.user_id = u.user_id
    WHERE o.status IN ('pending_approval', 'pending_payment')
    ORDER BY o.order_date DESC
    ''')
    
    pending = cursor.fetchall()
    conn.close()
    
    if not pending:
        text = "📋 **PENDING ORDERS**\n\nNo pending orders!"
        keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]]
    else:
        text = "📋 **PENDING ORDERS**\n\n"
        keyboard = []
        
        for order_id, game_name, price, username, first_name, order_date, status in pending:
            status_emoji = "🔍" if status == "pending_approval" else "⏳"
            text += f"{status_emoji} **Order #{order_id}**\n"
            text += f"👤 {first_name} (@{username or 'N/A'})\n"
            text += f"🎮 {game_name}\n"
            text += f"💰 ${price:.2f}\n"
            text += f"📅 {order_date.split()[0]}\n"
            text += f"Status: {status.replace('_', ' ').title()}\n\n"
            
            if status == "pending_approval":
                keyboard.append([
                    InlineKeyboardButton(f"✅ Approve #{order_id}", callback_data=f"approve_{order_id}"),
                    InlineKeyboardButton(f"❌ Reject #{order_id}", callback_data=f"reject_{order_id}")
                ])
        
        keyboard.append([InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def admin_payment_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all payment history (Admin only)"""
    query = update.callback_query
    await query.answer()
    
    if not bot_instance.is_admin(query.from_user.id):
        await query.edit_message_text("❌ Access denied!")
        return
    
    conn = bot_instance.get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT ph.id, ph.amount, ph.status, ph.payment_date, 
           u.first_name, u.username, g.name, o.id
    FROM payment_history ph
    JOIN orders o ON ph.order_id = o.id
    JOIN users u ON ph.user_id = u.user_id
    JOIN games g ON o.game_id = g.id
    ORDER BY ph.payment_date DESC
    LIMIT 20
    ''')
    
    payments = cursor.fetchall()
    conn.close()
    
    if not payments:
        text = "💳 **ALL PAYMENTS**\n\nNo payment history found!"
    else:
        text = "💳 **ALL PAYMENTS** (Last 20)\n\n"
        
        for payment in payments:
            payment_id, amount, status, payment_date, first_name, username, game_name, order_id = payment
            
            status_emoji = {
                'pending': '⏳',
                'approved': '✅',
                'rejected': '❌'
            }.get(status, '❓')
            
            text += f"{status_emoji} **Payment #{payment_id}**\n"
            text += f"👤 {first_name} (@{username or 'N/A'})\n"
            text += f"📋 Order: #{order_id}\n"
            text += f"🎮 {game_name}\n"
            text += f"💰 ${amount:.2f}\n"
            text += f"📅 {payment_date.split()[0]}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help information"""
    help_text = """
🆘 **HELP & SUPPORT**

**How to Buy:**
1. Browse games in 🎮 Games Store
2. Click on the game you want
3. Follow payment instructions
4. Send payment proof screenshot
5. Wait for admin approval
6. Receive your account details

**Payment Methods:**
• Scan QR code and pay exact amount
• Take screenshot of successful payment
• Send proof to bot immediately

**Order Status:**
• ⏳ Pending Payment - Waiting for payment
• 🔍 Pending Approval - Payment under review
• ✅ Completed - Account delivered
• ❌ Rejected - Payment rejected

**Important Notes:**
• Change password after receiving account
• Don't share account details
• Contact admin for support

**Need Help?**
Contact our support team for assistance.
    """
    
    if update.callback_query:
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to main menu"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    
    if bot_instance.is_admin(user.id):
        keyboard = [
            [KeyboardButton("🎮 Games Store"), KeyboardButton("👨‍💼 Admin Panel")],
            [KeyboardButton("📊 My Orders"), KeyboardButton("💳 Payment History")],
            [KeyboardButton("ℹ️ Help")]
        ]
    else:
        keyboard = [
            [KeyboardButton("🎮 Games Store")],
            [KeyboardButton("📊 My Orders"), KeyboardButton("💳 Payment History")],
            [KeyboardButton("ℹ️ Help")]
        ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    welcome_text = f"""
🎮 **Welcome back to Gaming Store Bot!** 🎮

Hello {user.first_name}! 👋

Available Games:
• Blox Fruit 🏴‍☠️
• Car Parking Multiplayer 🚗
• Mobile Legends ⚔️

What would you like to do?
    """
    
    await query.edit_message_text(welcome_text, parse_mode=ParseMode.MARKDOWN)
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="🏠 Back to main menu!",
        reply_markup=reply_markup
    )

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    text = update.message.text
    
    if text == "🎮 Games Store":
        await games_store(update, context)
    elif text == "👨‍💼 Admin Panel":
        await admin_panel(update, context)
    elif text == "📊 My Orders":
        await my_orders(update, context)
    elif text == "💳 Payment History":
        await payment_history(update, context)
    elif text == "ℹ️ Help":
        await help_command(update, context)
    elif context.user_data.get('awaiting_account_details'):
        await handle_account_details(update, context)
    else:
        await update.message.reply_text(
            "🤖 I didn't understand that. Please use the menu buttons below!"
        )

async def handle_callback_queries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries"""
    query = update.callback_query
    data = query.data
    
    if data.startswith("buy_"):
        await buy_game(update, context)
    elif data.startswith("payment_proof_"):
        await payment_proof_request(update, context)
    elif data.startswith("approve_"):
        await approve_order(update, context)
    elif data.startswith("reject_"):
        await reject_order(update, context)
    elif data.startswith("view_proof_"):
        await view_payment_proof(update, context)
    elif data == "admin_panel":
        await admin_panel(update, context)
    elif data == "add_account":
        await add_account_start(update, context)
    elif data.startswith("select_game_"):
        await select_game_for_account(update, context)
    elif data == "manage_stock":
        await manage_stock(update, context)
    elif data.startswith("view_accounts_"):
        await view_accounts(update, context)
    elif data == "pending_orders":
        await pending_orders(update, context)
    elif data == "sales_stats":
        await sales_stats(update, context)
    elif data == "admin_payments":
        await admin_payment_history(update, context)
    elif data == "back_to_menu":
        await back_to_menu(update, context)
    else:
        await query.answer("Unknown command!")

def main():
    """Start the bot"""
    print("🚀 Starting Gaming Store Bot...")
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_payment_proof))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
    application.add_handler(CallbackQueryHandler(handle_callback_queries))
    
    # Start the bot
    print("✅ Bot is running! Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()