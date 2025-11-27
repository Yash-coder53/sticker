# Telegram Sticker Maker & Memify Bot 🤖🎨

A powerful Telegram bot for creating stickers, memifying images, and generating quote stickers directly in your group chats or private messages.

## Features ✨

- **🔄 Sticker Memification** (`/mmf`) - Add text to images and stickers
- **💬 Quote Stickers** (`/q`) - Create stylish quote stickers from messages  
- **📦 Sticker Creation** (`/kang`) - Convert images to sticker format
- **🖼️ Multi-format Support** - PNG, JPEG, WEBP, static stickers
- **🎯 Group Chat Ready** - Works perfectly in Telegram groups
- **🚀 Termux Compatible** - Optimized for Android Termux hosting

## Commands 📝

| Command | Description | Usage |
|---------|-------------|--------|
| `/start` | Start the bot | `/start` |
| `/mmf` | Memify images/stickers | `/mmf Your text` (reply to image) |
| `/q` | Create quote stickers | `/q` (reply to text message) |
| `/kang` | Create stickers from images | `/kang` (reply to image) |

## Installation & Setup 🛠️

### Prerequisites
- Python 3.7+
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- Termux (Android) or any Python environment

### Step 1: Get Bot Token
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow instructions
3. Copy your bot token

### Step 2: Termux Setup
```bash
# Update packages
pkg update && pkg upgrade

# Install Python and required tools
pkg install python git

# Clone or create project directory
mkdir telegram-sticker-bot && cd telegram-sticker-bot
```

### Step 3: Install Dependencies
```bash
# Install requirements
pip install -r requirements.txt

# If any issues, install individually:
pip install python-telegram-bot pillow
```

### Step 4: Set Bot Token
```bash
# Set as environment variable (recommended)
export BOT_TOKEN="your_actual_bot_token_here"

# Or edit bot.py and replace YOUR_BOT_TOKEN_HERE
```

### Step 5: Run the Bot
```bash
python bot.py
```

## Termux Hosting Guide 📱

### Keep Bot Running in Background
```bash
# Install session manager
pkg install tmux

# Create new session
tmux new-session -s stickerbot

# Run your bot
python bot.py

# Detach from session: Ctrl+B, then D
# Reattach: tmux attach-session -t stickerbot
```

### Auto-start on Boot (Optional)
Create `~/.termux/boot/start-bot`:
```bash
#!/data/data/com.termux/files/usr/bin/bash
cd ~/telegram-sticker-bot
export BOT_TOKEN="your_token"
python bot.py
```

Make executable:
```bash
chmod +x ~/.termux/boot/start-bot
```

## Usage Examples 💡

### 1. Memify an Image
1. Send an image to bot or reply to image
2. Use: `/mmf This is hilarious!`
3. Bot returns memified image

### 2. Create Quote Sticker  
1. Reply to any text message with `/q`
2. Bot creates stylish quote sticker

### 3. Make Sticker from Image
1. Reply to image with `/kang`
2. Bot provides PNG file ready for sticker packs

## Troubleshooting 🔧

### Common Issues

**Installation Errors:**
```bash
# If Pillow fails to install:
pkg install python libjpeg-turbo
pip install --upgrade pip
pip install pillow --no-cache-dir
```

**Bot Not Responding:**
- Check bot token is correct
- Verify bot is added to chat
- Check internet connection

**Image Processing Errors:**
- Try different image format
- Reduce image size
- Use simpler images

## File Structure 📁

```
telegram-sticker-bot/
├── bot.py                 # Main bot application
├── requirements.txt       # Python dependencies
├── README.md             # Documentation
└── start.sh             # Quick start script (optional)
```

## Support 💬

For issues:
1. Check this README first
2. Verify all dependencies installed
3. Check bot token is correct
4. Ensure images are supported formats

## License 📄

MIT License - Feel free to modify and distribute.

---

**Happy Sticker Making! 🎨✨**
```

## 4. Quick Start Script (`start.sh`)

```bash
#!/bin/bash
# start.sh - Quick start script for Telegram Sticker Bot

echo "🤖 Starting Telegram Sticker Bot..."
cd ~/telegram-sticker-bot

# Check if BOT_TOKEN is set
if [ -z "$BOT_TOKEN" ]; then
    echo "❌ ERROR: BOT_TOKEN environment variable not set!"
    echo "Please set it using:"
    echo "export BOT_TOKEN='your_bot_token_here'"
    echo "Or edit bot.py and add your token directly"
    exit 1
fi

# Check if Python is available
if ! command -v python &> /dev/null; then
    echo "❌ Python not found. Installing..."
    pkg install python -y
fi

# Install/upgrade dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Run the bot
echo "🚀 Starting bot..."
python bot.py
```

Make executable:
```bash
chmod +x start.sh
```

## Key Fixes Applied:

1. **✅ Fixed requirements.txt** - Removed problematic packages
2. **✅ Updated python-telegram-bot** to latest stable version
3. **✅ Enhanced error handling** with proper try-catch blocks
4. **✅ Improved image processing** with better format support
5. **✅ Added input validation** for text length and file types
6. **✅ Better user feedback** with emojis and clear messages
7. **✅ Fixed font issues** by using default fonts
8. **✅ Added environment variable support** for security
9. **✅ Improved quote sticker design** with better visuals
10. **✅ Added comprehensive logging** for debugging

The bot should now install and run without errors!
