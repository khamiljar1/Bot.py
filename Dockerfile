# পাইথনের অফিশিয়াল ইমেজ ব্যবহার করা হচ্ছে
FROM python:3.10-slim

# কাজের ফোল্ডার ঠিক করা হচ্ছে
WORKDIR /app

# প্রথমে রিকোয়ারমেন্টস ফাইলটি কপি করা হচ্ছে
COPY requirements.txt .

# রেলওয়েকে লাইব্রেরিগুলো ইনস্টল করার নির্দেশ দেওয়া হচ্ছে
RUN pip install --no-cache-dir -r requirements.txt

# এবার কোডের বাকি সব ফাইল কপি করা হচ্ছে
COPY . .

# আপনার মেইন পাইথন ফাইলটি রান করা হচ্ছে
CMD ["python", "newfile.py"]
