# 🤖 Sticker Maker Bot 2025

A comprehensive Telegram bot for creating stickers from images and videos, with bot cloning functionality. Optimized for Termux and Python.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Telegram](https://img.shields.io/badge/Telegram-Bot_API-green.svg)
![Termux](https://img.shields.io/badge/Termux-Compatible-orange.svg)

## ✨ Features

- 🎨 **Image to Sticker** - Convert images to Telegram stickers
- 🎥 **Video to Sticker** - Convert videos to animated stickers
- 😂 **Memify Images** - Add meme text to images/stickers
- 💬 **Quote Stickers** - Create quote stickers from messages
- 📦 **Sticker Packs** - Manage custom sticker packs
- 🔄 **Bot Cloning** - Clone the bot with your own token
- 📱 **Termux Optimized** - Fully compatible with Android Termux

## 🚀 Quick Start

### Prerequisites

- Android Device with Termux
- Python 3.8+
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)

### Installation

1. **Update Termux:**
```bash
pkg update && pkg upgrade
```

2. **Install Dependencies:**
```bash
pkg install python git ffmpeg libjpeg-turbo
pip install telethon pyrogram pillow python-telegram-bot opencv-python numpy requests
```

3. **Clone Repository:**
```bash
git clone https://github.com/yourusername/sticker-bot-2025.git
cd sticker-bot-2025
```

4. **Configure Bot:**
   - Get token from [@BotFather](https://t.me/BotFather)
   - Edit `sticker_bot.py`:
   ```python
   BOT_TOKEN = "YOUR_ACTUAL_BOT_TOKEN_HERE"
   ```

5. **Run the Bot:**
```bash
python sticker_bot.py
```

## 📋 Bot Commands

| Command | Description | Usage |
|---------|-------------|--------|
| `/start` | Start the bot and show help | `/start` |
| `/mmf` | Add meme text to images/stickers | `/mmf Hello World` |
| `/q` | Create quote stickers from messages | Reply to message with `/q` |
| `/kang` | Add to sticker pack | Reply to sticker with `/kang` |
| `/clone` | Clone bot with your token | `/clone YOUR_BOT_TOKEN` |
| `Send Video` | Auto-convert to video sticker | Send any video file |

## 🎯 Usage Examples

### 1. Creating Meme Stickers
```
1. Send an image or sticker
2. Reply with: /mmf Your Funny Text
3. Get your memified sticker!
```

### 2. Quote Stickers
```
1. Reply to any message with: /q
2. Bot creates a stylish quote sticker
3. Share the quote sticker
```

### 3. Video Stickers
```
1. Send any video (max 3 seconds)
2. Bot automatically converts to webm sticker
3. Use in your chats instantly
```

### 4. Bot Cloning
```
1. Get token from @BotFather
2. Use: /clone YOUR_BOT_TOKEN
3. Your own bot instance starts running
```

## 🔧 Advanced Setup

### Running in Background (Termux)

1. **Install tmux:**
```bash
pkg install tmux
```

2. **Create tmux session:**
```bash
tmux new-session -s stickerbot
python sticker_bot.py
```

3. **Detach session:** `Ctrl+B, D`
4. **Reattach session:** `tmux attach-session -t stickerbot`

### Auto-start on Termux Launch

Create `~/.termux/boot/start-bot`:
```bash
#!/data/data/com.termux/files/usr/bin/bash
cd ~/sticker-bot-2025
tmux new-session -d -s stickerbot 'python sticker_bot.py'
```

Make executable:
```bash
chmod +x ~/.termux/boot/start-bot
```

## 📁 Project Structure

```
sticker-bot-2025/
├── sticker_bot.py              # Main bot file
├── sticker_bot_advanced.py     # Advanced features
├── setup.sh                    # Installation script
├── bot_data.db                 # SQLite database (auto-generated)
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## ⚙️ Configuration

### Environment Variables (Optional)

Create `.env` file:
```env
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=123456789,987654321
MAX_FILE_SIZE=10485760
```

### Sticker Specifications

- **Image Stickers:** 512x512px, WEBP format
- **Video Stickers:** 3 seconds max, WEBM format, 512x512px
- **File Size:** 10MB maximum

## 🐛 Troubleshooting

### Common Issues

1. **"ffmpeg not found"**
   ```bash
   pkg install ffmpeg
   ```

2. **"Python package installation fails"**
   ```bash
   pip install --upgrade pip
   pkg install python-dev libjpeg-turbo-dev
   ```

3. **"Bot doesn't respond"**
   - Check bot token
   - Ensure internet connection
   - Verify bot is started with correct privileges

4. **"Video conversion fails"**
   ```bash
   pkg reinstall ffmpeg
   ```

### Logs and Debugging

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 🔒 Security Notes

- 🤫 Never share your bot token publicly
- 🔐 Keep your Termux session secure
- 📱 Use app passwords if 2FA enabled
- 🗑️ Regularly clean temporary files

## 📈 Performance Tips

1. **Use SSD storage** if possible
2. **Close background apps** when running bot
3. **Monitor storage space** for media files
4. **Use efficient image compression**
5. **Limit concurrent operations** for stability

## 🤝 Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Open a Pull Request

### Development Setup

```bash
git clone https://github.com/yourusername/sticker-bot-2025.git
cd sticker-bot-2025
pip install -r requirements.txt
# Make your changes and test
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- 📧 Email: your-email@example.com
- 💬 Telegram: [@YourSupportChannel](https://t.me/YourSupportChannel)
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/sticker-bot-2025/issues)

## 🙏 Acknowledgments

- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Python-Telegram-Bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [Termux](https://termux.com) community
- [Pillow](https://python-pillow.org) for image processing

---

**⭐ Star this repo if you found it helpful!**

**🐛 Found a bug?** Open an issue on GitHub.

**💡 Have a feature request?** We'd love to hear it!

---

*Last updated: December 2024 | Compatible with Termux 2025*
