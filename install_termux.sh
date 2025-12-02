#!/data/data/com.termux/files/usr/bin/bash

echo "========================================="
echo "🤖 Sticker Bot - Termux Installation"
echo "========================================="

# Update packages
echo "🔄 Updating packages..."
pkg update -y && pkg upgrade -y

# Install Python and dependencies
echo "🐍 Installing Python..."
pkg install python -y

# Install required packages
echo "📦 Installing required packages..."
pkg install git wget curl ffmpeg -y

# Install Python packages
echo "📦 Installing Python packages..."
pip install --upgrade pip
pip install python-telegram-bot pillow requests aiohttp python-dotenv

# Download bot files
echo "⬇️ Downloading bot files..."
cat > sticker_bot.py << 'EOF'
# [PASTE THE ENTIRE sticker_bot.py CONTENT HERE]
EOF

cat > requirements.txt << 'EOF'
python-telegram-bot[job-queue]==20.7
pillow==10.3.0
requests==2.31.0
aiohttp==3.9.3
python-dotenv==1.0.0
EOF

cat > .env.example << 'EOF'
# Telegram Bot Configuration
BOT_TOKEN=YOUR_BOT_TOKEN_HERE

# Bot Owner (your Telegram ID)
OWNER_ID=YOUR_TELEGRAM_ID

# Additional Admins (comma-separated)
ADMIN_IDS=ANOTHER_TELEGRAM_ID

# Bot Settings
MAX_FILE_SIZE=10485760  # 10MB
EOF

# Create fonts directory
echo "🔤 Setting up fonts..."
mkdir -p fonts

# Download font if needed
if [ ! -f "fonts/Roboto-Regular.ttf" ]; then
    echo "⬇️ Downloading Roboto font..."
    wget -q https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf -O fonts/Roboto-Regular.ttf
fi

# Make script executable
chmod +x sticker_bot.py

echo ""
echo "========================================="
echo "✅ Installation Complete!"
echo "========================================="
echo ""
echo "📝 NEXT STEPS:"
echo "1. Edit the .env file:"
echo "   nano .env"
echo ""
echo "2. Get your BOT_TOKEN from @BotFather"
echo "3. Get your Telegram ID from @userinfobot"
echo ""
echo "3. Run the bot:"
echo "   cd ~/sticker-bot"
echo "   python sticker_bot.py"
echo ""
echo "4. For background running:"
echo "   tmux new -s sticker_bot"
echo ""
echo "📚 Commands to remember:"
echo "   /start - Start bot"
echo "   /mmf - Make memes"
echo "   /q - Create quotes"
echo "   /kang - Add stickers"
echo "========================================="
