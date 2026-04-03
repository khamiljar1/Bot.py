import os
import sys

# লাইব্রেরিগুলো ইনস্টল না থাকলে রেলওয়ে নিজে থেকেই করে নেবে
try:
    import matplotlib.pyplot as plt
    import requests
    import websocket
except ImportError:
    print("Installing missing libraries...")
    os.system("pip install matplotlib requests websocket-client")
    os.execv(sys.executable, ['python'] + sys.argv)

from collections import deque
import json

SYMBOL = "btcusdt"
prices = deque(maxlen=100)

BOT_TOKEN = "8573216613:AAHenpEHoGeRRU2GhhAHlChA7wz6yPugPag"
CHAT_ID = "8283358607"

update_counter = 0

# ... আপনার বাকি কোডগুলো এরপর থেকে হুবহু বসে যাবে ...
