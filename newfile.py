from collections import deque
import json
import matplotlib.pyplot as plt
import requests
import websocket

SYMBOL = "btcusdt"
prices = deque(maxlen=100)

# আপনার টেলিগ্রাম বটের তথ্য বসানো হয়েছে
BOT_TOKEN = "8573216613:AAHenpEHoGeRRU2GhhAHlChA7wz6yPugPag"
CHAT_ID = "8283358607"

# অনেক ঘন ঘন মেসেজ পাঠালে টেলিগ্রাম ব্লক করতে পারে,
# তাই প্রতি ২০টি নতুন প্রাইস ডাটা আসার পর একটি করে চার্ট পাঠানো হবে।
update_counter = 0


def send_chart_to_telegram(image_path):
    """টেলিগ্রামে ছবি পাঠানোর ফাংশন"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    try:
        with open(image_path, "rb") as photo:
            files = {"photo": photo}
            data = {"chat_id": CHAT_ID, "caption": "📊 Live BTC Trend Update"}
            requests.post(url, files=files, data=data)
            print("📤 চার্ট টেলিগ্রামে পাঠানো হয়েছে।")
    except Exception as e:
        print(f"❌ Telegram Error: {e}")


def update_chart():
    if len(prices) < 2:
        return

    # নতুন ফিগার তৈরি (যাতে মেমোরি জ্যাম না হয়)
    fig, ax = plt.subplots()

    # কালার লজিক
    color = "green" if prices[-1] > prices[0] else "red"

    ax.plot(prices, color=color, linewidth=2)
    ax.set_title("Live BTC Trend", color="white")

    # ডার্ক থিম
    ax.set_facecolor("black")
    fig.patch.set_facecolor("black")
    ax.tick_params(colors="white")

    # ইমেজ হিসেবে সেভ করা
    image_path = "live_chart.png"
    plt.savefig(image_path, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)  # মেমোরি খালি করার জন্য ক্লোজ করা জরুরি

    # টেলিগ্রামে পাঠানো
    send_chart_to_telegram(image_path)


def on_message(ws, message):
    global update_counter
    data = json.loads(message)
    price = float(data["p"])
    prices.append(price)

    update_counter += 1

    # প্রতি ২০টি মেসেজ (ট্রেড) পর পর টেলিগ্রামে চার্ট আপডেট যাবে
    if update_counter >= 20:
        update_chart()
        update_counter = 0  # কাউন্টার রিসেট


def on_open(ws):
    print("✅ WebSocket Connected! Sending charts to Telegram...")


socket = f"wss://stream.binance.com:9443/ws/{SYMBOL}@trade"
ws = websocket.WebSocketApp(socket, on_message=on_message, on_open=on_open)
ws.run_forever()