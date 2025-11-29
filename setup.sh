#!/data/data/com.termux/files/usr/bin/bash

echo "📦 Installing Sticker Bot 2025..."

# Update packages
pkg update -y && pkg upgrade -y

# Install dependencies
pkg install -y python git ffmpeg libjpeg-turbo

# Install Python packages
pip install telethon pyrogram pillow python-telegram-bot opencv-python numpy requests

# Download bot files (you'll need to create these files manually first)
echo "✅ Installation complete!"
echo "📝 Edit the bot token in sticker_bot.py"
echo "🚀 Run: python sticker_bot.py"
