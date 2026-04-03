import os
import sys

# রেলওয়েতে ফাইল ছাড়া অটোমেশনের জন্য লাইব্রেরি অটো-ইনস্টল করার ট্রিক
try:
    import numpy as np
    import pandas as pd
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ReplyKeyboardMarkup, KeyboardButton
    from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
except ImportError:
    print("Installing required libraries on Railway...")
    os.system("pip install python-telegram-bot==20.8 numpy pandas")
    print("Installation complete. Restarting script...")
    os.execv(sys.executable, ['python'] + sys.argv)

import asyncio
import json
import urllib.request

# ==========================================
# 🔑 CONFIGURATION & CREDENTIALS
# ==========================================
TOKEN = "8573216613:AAHenpEHoGeRRU2GhhAHlChA7wz6yPugPag"
CHAT_ID = "8283358607"

LENGTH = 14
ATR_LEN = 14

active_scans = {}  
active_alerts = {} 

monitored_assets = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", 
    "AUDUSD=X", "AUDCAD=X", "GC=F", "SI=F", "USOIL", "NZDUSD=X",
    "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD", 
    "ADA-USD", "DOGE-USD", "DOT-USD", "MATIC-USD", "TRX-USD"
]

def get_permanent_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🏠 Home")]], 
        resize_keyboard=True, 
        one_time_keyboard=False,
        is_persistent=True       
    )

def calculate_indicators(df):
    if len(df) < 50: 
        return None, None, None, None, None

    df['ema8'] = df['close'].ewm(span=8, adjust=False).mean()
    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp1 - exp2
    df['signal_line'] = df['macd'].ewm(span=9, adjust=False).mean()
    
    df['sma20'] = df['close'].rolling(window=20).mean()
    df['std20'] = df['close'].rolling(window=20).std()
    df['upper_bb'] = df['sma20'] + (df['std20'] * 2)
    df['lower_bb'] = df['sma20'] - (df['std20'] * 2)
    
    df["high_low"] = df["high"] - df["low"]
    df["high_cp"] = np.abs(df["high"] - df["close"].shift(1))
    df["low_cp"] = np.abs(df["low"] - df["close"].shift(1))
    df["tr"] = df[["high_low", "high_cp", "low_cp"]].max(axis=1)
    df["atr"] = df["tr"].rolling(window=ATR_LEN).mean()

    low_14 = df['low'].rolling(window=14).min()
    high_14 = df['high'].rolling(window=14).max()
    df['k_percent'] = 100 * ((df['close'] - low_14) / (high_14 - low_14))
    df['d_percent'] = df['k_percent'].rolling(window=3).mean()

    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]
    
    buy_score = 0
    sell_score = 0
    
    if last_row['ema8'] > last_row['ema21']: buy_score += 1
    if last_row['ema8'] < last_row['ema21']: sell_score += 1
    
    if last_row['close'] > last_row['ema50']: buy_score += 1
    if last_row['close'] < last_row['ema50']: sell_score += 1
    
    if last_row['rsi'] > 50 and prev_row['rsi'] <= 50: buy_score += 1
    if last_row['rsi'] < 50 and prev_row['rsi'] >= 50: sell_score += 1
    
    if 40 < last_row['rsi'] < 70: buy_score += 1
    if 30 < last_row['rsi'] < 60: sell_score += 1
    
    if last_row['macd'] > last_row['signal_line'] and prev_row['macd'] <= prev_row['signal_line']: buy_score += 1
    if last_row['macd'] < last_row['signal_line'] and prev_row['macd'] >= prev_row['signal_line']: sell_score += 1
    
    if last_row['macd'] > 0: buy_score += 1
    if last_row['macd'] < 0: sell_score += 1
    
    if last_row['close'] > last_row['sma20']: buy_score += 1
    if last_row['close'] < last_row['sma20']: sell_score += 1
    
    if last_row['close'] > prev_row['open'] and last_row['open'] < prev_row['close']: buy_score += 1
    if last_row['close'] < prev_row['open'] and last_row['open'] > prev_row['close']: sell_score += 1
    
    if last_row['k_percent'] > last_row['d_percent'] and prev_row['k_percent'] <= prev_row['d_percent']: buy_score += 1
    if last_row['k_percent'] < last_row['d_percent'] and prev_row['k_percent'] >= prev_row['d_percent']: sell_score += 1
    
    if last_row['k_percent'] > 20: buy_score += 1
    if last_row['k_percent'] < 80: sell_score += 1
    
    if last_row['high'] > prev_row['high']: buy_score += 1
    if last_row['low'] < prev_row['low']: sell_score += 1
    
    if len(df) >= 3:
        if df['close'].iloc[-1] > df['close'].iloc[-2] > df['close'].iloc[-3]: buy_score += 1
        if df['close'].iloc[-1] < df['close'].iloc[-2] < df['close'].iloc[-3]: sell_score += 1

    buy_signal = (buy_score >= 12)
    sell_signal = (sell_score >= 12)

    return buy_signal, sell_signal, last_row["close"], last_row["atr"], df

def fetch_live_data(symbol, timeframe):
    interval = timeframe
    if timeframe == "1h": interval = "60m"
    elif timeframe == "2h": interval = "120m"
    elif timeframe == "4h": interval = "240m"
    
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={interval}&range=5d"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        
    res = data['chart']['result'][0]
    timestamps = res['timestamp']
    quote = res['indicators']['quote'][0]
    
    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': quote['open'],
        'high': quote['high'],
        'low': quote['low'],
        'close': quote['close']
    })
    df = df.dropna()
    return df

async def single_asset_engine(symbol, timeframe, app):
    print(f"Engine fired up for: {symbol} on {timeframe}")

    while active_scans.get(timeframe, False):
        try:
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(None, fetch_live_data, symbol, timeframe)
            if df.empty:
                await asyncio.sleep(5)
                continue

            buy, sell, ep, atr, full_df = calculate_indicators(df)
            clean_symbol = symbol.replace("=X", "").replace("=F", "").replace("-USD", "/USD").replace("GC", "GOLD").replace("SI", "SILVER")

            if buy and not active_alerts.get(timeframe, False):
                active_alerts[timeframe] = True
                sl = full_df["low"].iloc[-1] if full_df["low"].iloc[-1] < full_df["low"].iloc[-2] else full_df["low"].iloc[-2]
                t1, t2, t3, t4 = ep + (atr * 0.5), ep + (atr * 1.0), ep + (atr * 1.5), ep + (atr * 2.0)

                text = (
                    f"🟢 **BUY SIGNAL DETECTED!** 🟢\n"
                    f"Asset: {clean_symbol}\n"
                    f"Timeframe: {timeframe}\n"
                    f"Entry Point: {ep:.5f}\n"
                    f"Stop Loss: {sl:.5f}\n"
                    f"🎯 T1: {t1:.5f}\n🎯 T2: {t2:.5f}\n🎯 T3: {t3:.5f}\n🎯 T4: {t4:.5f}"
                )
                await app.bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="Markdown")
                asyncio.create_task(spam_reminder(app, timeframe))

            elif sell and not active_alerts.get(timeframe, False):
                active_alerts[timeframe] = True
                sl = full_df["high"].iloc[-1] if full_df["high"].iloc[-1] > full_df["high"].iloc[-2] else full_df["high"].iloc[-2]
                t1, t2, t3, t4 = ep - (atr * 0.5), ep - (atr * 1.0), ep - (atr * 1.5), ep - (atr * 2.0)

                text = (
                    f"🔴 **SELL SIGNAL DETECTED!** 🔴\n"
                    f"Asset: {clean_symbol}\n"
                    f"Timeframe: {timeframe}\n"
                    f"Entry Point: {ep:.5f}\n"
                    f"Stop Loss: {sl:.5f}\n"
                    f"🎯 T1: {t1:.5f}\n🎯 T2: {t2:.5f}\n🎯 T3: {t3:.5f}\n🎯 T4: {t4:.5f}"
                )
                await app.bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="Markdown")
                asyncio.create_task(spam_reminder(app, timeframe))

        except Exception as e:
            await asyncio.sleep(5)
            continue
        
        await asyncio.sleep(5)

async def start_all_engines(timeframe, app):
    tasks = []
    for symbol in monitored_assets:
        tasks.append(asyncio.create_task(single_asset_engine(symbol, timeframe, app)))
    await asyncio.gather(*tasks)

async def spam_reminder(app, timeframe):
    keyboard = [[InlineKeyboardButton(f"🛑 Stop Alert ({timeframe})", callback_data=f"stop_{timeframe}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    while active_alerts.get(timeframe, False):
        await app.bot.send_message(
            chat_id=CHAT_ID,
            text=f"⚠️ Reminder ({timeframe}): Signal is active! Time to take your trade now!",
            reply_markup=reply_markup,
        )
        await asyncio.sleep(5)

def get_home_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 Start Trading", callback_data="menu_trading")],
        [InlineKeyboardButton("📊 See Workflow Activity", callback_data="menu_workflow")],
        [InlineKeyboardButton("ℹ️ App Info", callback_data="menu_info")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome! I am your personal AI Trading Agent. I will scan the market "
        "and find perfect signals based on your custom logic. Tap below to start.",
        reply_markup=get_home_markup(),
    )
    await update.message.reply_text("হোম বাটন নিচে পার্মানেন্টলি সেট করা হয়েছে।", reply_markup=get_permanent_keyboard())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    p_keyboard = get_permanent_keyboard()

    if query.data == "home":
        await query.message.delete()
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text="Welcome! I am your personal AI Trading Agent. I will scan the market and find perfect signals based on your custom logic. Tap below to start.",
            reply_markup=get_home_markup()
        )
        await context.bot.send_message(chat_id=CHAT_ID, text="হোম বাটন লোড করা আছে।", reply_markup=p_keyboard)

    elif query.data == "menu_info":
        info_text = (
            "This advanced AI trading bot was developed by Abad Rahman Musafir.\n"
            "It uses custom breakout and ATR logic for precise real-time analysis.\n"
            "Our ultimate goal is to make your trading smooth, fast, and highly effective.\n"
            "Thank you for staying and growing with us!"
        )
        await query.message.delete()
        await context.bot.send_message(chat_id=CHAT_ID, text=info_text, reply_markup=p_keyboard)

    elif query.data == "menu_workflow":
        running_tfs = [tf for tf, status in active_scans.items() if status]
        if running_tfs:
            text = (
                f"The bot is currently actively scanning the market! 🔍\n\n"
                f"Your AI logic is running on active timeframes: {', '.join(running_tfs)}\n"
                f"Alerts will be triggered automatically upon breakout detection."
            )
        else:
            text = "⚠️ Currently, no background workflow is running. To initiate operation, please tap the '📈 Start Trading' button from the home page."
        
        await query.message.delete()
        await context.bot.send_message(chat_id=CHAT_ID, text=text, reply_markup=p_keyboard)

    elif query.data == "menu_trading":
        timeframes = [["5m", "15m", "30m"], ["1h", "2h", "4h"]]
        keyboard = [[InlineKeyboardButton(tf, callback_data=f"tf_{tf}") for tf in row] for row in timeframes]
        
        await query.message.delete()
        await context.bot.send_message(
            chat_id=CHAT_ID, 
            text="Please select your preferred timeframe. I will start analyzing the data accordingly.", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await context.bot.send_message(chat_id=CHAT_ID, text="হোম বাটন ফিক্সড আছে।", reply_markup=p_keyboard)

    elif query.data.startswith("tf_"):
        selected_timeframe = query.data.split("_")[1]
        keyboard = [
            [InlineKeyboardButton(f"🚀 Start {selected_timeframe} Scan", callback_data=f"start_{selected_timeframe}")]
        ]
        await query.message.delete()
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=f"Timeframe set to {selected_timeframe} successfully. Click below to initiate execution.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await context.bot.send_message(chat_id=CHAT_ID, text="হোম বাটন ফিক্সড আছে।", reply_markup=p_keyboard)

    elif query.data.startswith("start_"):
        tf_to_start = query.data.split("_")[1]
        active_scans[tf_to_start] = True
        
        await query.message.delete()
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=f"Execution started successfully for {tf_to_start}! 20 independent engines have been fired up to scan all assets simultaneously.",
            reply_markup=get_home_markup()
        )
        await context.bot.send_message(chat_id=CHAT_ID, text="হোম বাটন ফিক্সড আছে।", reply_markup=p_keyboard)
        asyncio.create_task(start_all_engines(tf_to_start, context.application))

    elif query.data.startswith("stop_"):
        tf_to_stop = query.data.split("_")[1]
        active_alerts[tf_to_stop] = False
        
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=f"Alert stopped successfully for {tf_to_stop}! I have resumed background scanning for fresh signals.",
            reply_markup=get_home_markup()
        )
        await context.bot.send_message(chat_id=CHAT_ID, text="হোম বাটন ফিক্সড আছে।", reply_markup=p_keyboard)

async def handle_text_or_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    p_keyboard = get_permanent_keyboard()
    
    if user_text == "🏠 Home":
        await update.message.reply_text(
            "Welcome! I am your personal AI Trading Agent. I will scan the market and find perfect signals based on your custom logic. Tap below to start.",
            reply_markup=get_home_markup(),
        )
        await update.message.reply_text("হোম বাটন ফিক্সড আছে।", reply_markup=p_keyboard)
    else:
        await update.message.reply_text(
            "⚠️ ERROR: You typed a manual text. Please use the operational buttons on screen or press '🏠 Home'.",
            reply_markup=p_keyboard
        )

async def post_init(application: Application):
    await application.bot.send_message(
        chat_id=CHAT_ID, 
        text="🚀 **System Online!**\nবট সফলভাবে চালু হয়েছে। কাজ শুরু করতে নিচের বাটনে চাপ দিন।",
        reply_markup=get_home_markup()
    )
    await application.bot.send_message(
        chat_id=CHAT_ID, 
        text="বটের নিচে হোম বাটন লোড করা হয়েছে। এটি সবসময় ফিক্সড থাকবে।", 
        reply_markup=get_permanent_keyboard()
    )

def main():
    application = Application.builder().token(TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_or_home))

    print("Bot is polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
