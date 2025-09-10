#!/bin/bash

# --- رنگ‌ها برای خروجی زیباتر ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# --- تابع برای نمایش پیام‌های اطلاعاتی ---
info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# --- تابع برای نمایش پیام‌های موفقیت ---
success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# --- شروع اسکریپت ---
clear
echo -e "${GREEN}=====================================================${NC}"
echo -e "${YELLOW}      نصب‌کننده خودکار ربات SMS Bomber      ${NC}"
echo -e "${GREEN}=====================================================${NC}"
echo

# 1. دریافت اطلاعات از کاربر
info "لطفاً اطلاعات زیر را برای پیکربندی ربات وارد کنید:"
read -p "توکن ربات تلگرام (Bot Token): " BOT_TOKEN
read -p "شناسه عددی ادمین (Admin ID): " ADMIN_ID
read -p "نام کاربری ادمین (بدون @): " ADMIN_USERNAME
read -p "محدودیت مصرف CPU (مثلاً 20): " CPU_LIMIT
read -p "محدودیت مصرف RAM (مثلاً 20): " RAM_LIMIT

# 2. نصب پیش‌نیازها
info "در حال به‌روزرسانی سرور و نصب پیش‌نیازها..."
sudo apt-get update > /dev/null 2>&1
sudo apt-get install -y git openjdk-17-jre python3 python3-venv > /dev/null 2>&1
success "پیش‌نیازها با موفقیت نصب شدند."

# 3. کلون کردن پروژه از گیت‌هاب
info "در حال دریافت فایل‌های پروژه از گیت‌هاب..."
# آدرس ریپازیتوری خود را جایگزین کنید
git clone https://github.com/your-username/sms-bomber-bot.git /root/sms_bot > /dev/null 2>&1
cd /root/sms_bot
success "فایل‌های پروژه با موفقیت در پوشه /root/sms_bot قرار گرفتند."

# 4. پیکربندی فایل پایتون ربات
info "در حال پیکربندی ربات با اطلاعات شما..."
sed -i "s/BOT_TOKEN = \".*\"/BOT_TOKEN = \"$BOT_TOKEN\"/" telegram_bot.py
sed -i "s/ADMIN_ID = .*/ADMIN_ID = $ADMIN_ID/" telegram_bot.py
sed -i "s/ADMIN_USERNAME = \".*\"/ADMIN_USERNAME = \"$ADMIN_USERNAME\"/" telegram_bot.py
success "فایل ربات با موفقیت پیکربندی شد."

# 5. راه‌اندازی محیط مجازی پایتون
info "در حال ساخت و فعال‌سازی محیط مجازی پایتون..."
python3 -m venv venv
source venv/bin/activate
pip install python-telegram-bot > /dev/null 2>&1
deactivate
success "محیط مجازی با موفقیت ساخته و کتابخانه‌ها نصب شدند."

# 6. ساخت و پیکربندی سرویس systemd
info "در حال ساخت سرویس systemd برای اجرای دائمی ربات..."
SERVICE_FILE_CONTENT="[Unit]
Description=Telegram SMS Bomber Bot
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/root/sms_bot
ExecStart=/root/sms_bot/venv/bin/python3 /root/sms_bot/telegram_bot.py
Restart=always
RestartSec=10
CPUQuota=${CPU_LIMIT}%
MemoryMax=${RAM_LIMIT}%

[Install]
WantedBy=multi-user.target"

echo "$SERVICE_FILE_CONTENT" | sudo tee /etc/systemd/system/telegram_bomber_bot.service > /dev/null
success "فایل سرویس با محدودیت CPU و RAM ساخته شد."

# 7. راه‌اندازی نهایی سرویس
info "در حال فعال‌سازی و راه‌اندازی سرویس ربات..."
sudo systemctl daemon-reload
sudo systemctl enable telegram_bomber_bot.service > /dev/null 2>&1
sudo systemctl restart telegram_bomber_bot.service
success "سرویس ربات با موفقیت راه‌اندازی شد."

# --- نمایش پیام پایانی ---
echo
echo -e "${GREEN}=====================================================${NC}"
echo -e "${YELLOW}          نصب با موفقیت به پایان رسید!          ${NC}"
echo -e "${GREEN}=====================================================${NC}"
echo
info "ربات شما اکنون در حال اجراست. می‌توانید به تلگرام بروید و آن را تست کنید."
echo
info "دستورات مفید برای مدیریت سرویس:"
echo -e "  - مشاهده وضعیت: ${YELLOW}sudo systemctl status telegram_bomber_bot.service${NC}"
echo -e "  - مشاهده لاگ‌ها: ${YELLOW}sudo journalctl -u telegram_bomber_bot.service -f${NC}"
echo -e "  - متوقف کردن: ${YELLOW}sudo systemctl stop telegram_bomber_bot.service${NC}"
echo -e "  - راه‌اندازی مجدد: ${YELLOW}sudo systemctl restart telegram_bomber_bot.service${NC}"
echo
