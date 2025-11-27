Here are the updated and corrected files with all errors fixed:

## 1. Updated `requirements.txt`

```txt
python-telegram-bot==21.7
Pillow==10.2.0
pycparser==2.22
cachetools==5.3.2
httpx==0.27.0
```

## 2. Updated Main Bot Code (`bot.py`)

```python
import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image, ImageDraw, ImageFont
import textwrap
import io
import uuid

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token from BotFather - Use environment variable for security
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')

class StickerBot:
    def __init__(self):
        self.user_data = {}
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send welcome message when command /start is issued."""
        user = update.effective_user
        welcome_text = f"""
🤖 Welcome {user.first_name} to Sticker Maker Bot! 🎉

Available Commands:
/mmf - Memify images or stickers with text
/q - Create quote stickers from messages  
/kang - Create stickers from images

How to use:
1. Send an image/sticker and reply with /mmf <text>
2. Reply to any message with /q for quote sticker
3. Reply to image with /kang to make sticker

Just send me an image or sticker to get started!
        """
        await update.message.reply_text(welcome_text)
    
    async def memify_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Memify an image or sticker with text."""
        try:
            # Check if we have text to memify with
            if not context.args:
                await update.message.reply_text(
                    "❌ Please provide text for memification!\n"
                    "Usage: `/mmf your text here` (reply to image/sticker)",
                    parse_mode='Markdown'
                )
                return
            
            text = ' '.join(context.args)
            
            # Check message length
            if len(text) > 200:
                await update.message.reply_text("❌ Text too long! Maximum 200 characters.")
                return
            
            # Check if we have a photo or sticker
            if not update.message.reply_to_message:
                await update.message.reply_text(
                    "❌ Please reply to an image or sticker with `/mmf text`",
                    parse_mode='Markdown'
                )
                return
            
            reply_msg = update.message.reply_to_message
            image = None
            
            if reply_msg.sticker:
                # Download sticker
                if reply_msg.sticker.is_animated or reply_msg.sticker.is_video:
                    await update.message.reply_text("❌ Animated and video stickers are not supported yet.")
                    return
                    
                sticker_file = await reply_msg.sticker.get_file()
                sticker_bytes = await sticker_file.download_as_bytearray()
                image = Image.open(io.BytesIO(sticker_bytes))
                
            elif reply_msg.photo:
                # Download the largest photo
                photo_file = await reply_msg.photo[-1].get_file()
                photo_bytes = await photo_file.download_as_bytearray()
                image = Image.open(io.BytesIO(photo_bytes))
                
            elif reply_msg.document and reply_msg.document.mime_type and reply_msg.document.mime_type.startswith('image/'):
                # Download image document
                doc_file = await reply_msg.document.get_file()
                doc_bytes = await doc_file.download_as_bytearray()
                image = Image.open(io.BytesIO(doc_bytes))
                
            else:
                await update.message.reply_text("❌ Please reply to an image or static sticker!")
                return
            
            # Memify the image
            memified_image = self._add_text_to_image(image, text)
            
            # Send back the memified image
            bio = io.BytesIO()
            memified_image.save(bio, 'PNG')
            bio.seek(0)
            
            await update.message.reply_photo(
                photo=bio, 
                caption="🎨 Here's your memified image! Use /kang to make it a sticker."
            )
            
        except Exception as e:
            logger.error(f"Error in memify: {e}")
            await update.message.reply_text("❌ Error processing your request. Please try again with a different image.")
    
    def _add_text_to_image(self, image: Image.Image, text: str) -> Image.Image:
        """Add text to image for memification."""
        try:
            # Convert to RGB if necessary
            if image.mode in ('RGBA', 'P', 'LA'):
                background = Image.new('RGB', image.size, 'white')
                if image.mode == 'RGBA':
                    background.paste(image, mask=image.split()[-1])
                else:
                    background.paste(image)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Resize if too large (for performance)
            max_size = (1024, 1024)
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            draw = ImageDraw.Draw(image)
            
            # Create font - using default font
            try:
                # Try to load a larger default font
                font_size = min(max(image.width // 15, 20), 50)
                font = ImageFont.load_default()
                # Alternative: Use built-in font
                # font = ImageFont.truetype("arial.ttf", font_size)
            except Exception as font_error:
                logger.warning(f"Font error: {font_error}, using default")
                font = ImageFont.load_default()
            
            # Wrap text based on image width
            avg_char_width = 10  # Approximate width per character
            chars_per_line = max(image.width // avg_char_width, 20)
            wrapped_text = textwrap.fill(text, width=min(chars_per_line, 50))
            
            # Calculate text dimensions
            lines = wrapped_text.split('\n')
            line_height = 20
            total_text_height = len(lines) * line_height
            
            # Add padding at top for text
            padding = 20
            new_height = image.height + total_text_height + padding * 2
            new_image = Image.new('RGB', (image.width, new_height), 'white')
            new_image.paste(image, (0, total_text_height + padding))
            
            draw = ImageDraw.Draw(new_image)
            
            # Draw text at top with background
            y_position = padding
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                x_position = (image.width - text_width) // 2
                
                # Draw text background
                bg_padding = 5
                draw.rectangle([
                    x_position - bg_padding, 
                    y_position - bg_padding,
                    x_position + text_width + bg_padding, 
                    y_position + line_height + bg_padding
                ], fill='black')
                
                # Draw text
                draw.text((x_position, y_position), line, fill='white', font=font)
                y_position += line_height
            
            return new_image
            
        except Exception as e:
            logger.error(f"Error in image processing: {e}")
            # Return original image if processing fails
            return image
    
    async def quote_sticker(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create a quote sticker from a message."""
        try:
            if not update.message.reply_to_message:
                await update.message.reply_text(
                    "❌ Please reply to a message with `/q` to create a quote sticker!",
                    parse_mode='Markdown'
                )
                return
            
            replied_msg = update.message.reply_to_message
            text = replied_msg.text or replied_msg.caption or "No text available"
            
            # Limit text length
            if len(text) > 500:
                text = text[:497] + "..."
            
            # Create quote image
            quote_image = self._create_quote_image(text, update.effective_user.first_name)
            
            # Send as photo
            bio = io.BytesIO()
            quote_image.save(bio, 'PNG')
            bio.seek(0)
            
            await update.message.reply_photo(
                photo=bio, 
                caption="📝 Quote sticker created!\nUse /kang to add to your sticker pack."
            )
            
        except Exception as e:
            logger.error(f"Error in quote sticker: {e}")
            await update.message.reply_text("❌ Error creating quote sticker. Please try again.")
    
    def _create_quote_image(self, text: str, author: str) -> Image.Image:
        """Create a quote image with text."""
        try:
            # Create a blank image with nice background
            width, height = 512, 256
            image = Image.new('RGB', (width, height), color='#f0f8ff')  # Alice blue background
            draw = ImageDraw.Draw(image)
            
            # Load font (using default)
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()
            
            # Wrap text
            wrapped_text = textwrap.fill(text, width=40)
            
            # Calculate text position
            lines = wrapped_text.split('\n')
            total_height = len(lines) * 20
            start_y = (height - total_height - 30) // 2
            
            # Draw quote marks
            draw.text((30, start_y - 10), "``", fill='#4682b4', font=font_large)
            
            # Draw main text
            for i, line in enumerate(lines):
                bbox = draw.textbbox((0, 0), line, font=font_large)
                text_width = bbox[2] - bbox[0]
                x = (width - text_width) // 2
                y = start_y + (i * 20)
                draw.text((x, y), line, fill='#2f4f4f', font=font_large)
            
            # Draw author line
            author_text = f"― {author}"
            author_bbox = draw.textbbox((0, 0), author_text, font=font_small)
            author_width = author_bbox[2] - author_bbox[0]
            author_x = width - author_width - 30
            author_y = height - 40
            
            draw.text((author_x, author_y), author_text, fill='#696969', font=font_small)
            
            # Add decorative border
            draw.rectangle([10, 10, width-11, height-11], outline='#4682b4', width=2)
            draw.rectangle([15, 15, width-16, height-16], outline='#87ceeb', width=1)
            
            return image
            
        except Exception as e:
            logger.error(f"Error creating quote image: {e}")
            # Fallback simple image
            image = Image.new('RGB', (512, 256), color='white')
            draw = ImageDraw.Draw(image)
            draw.text((50, 100), "Quote: " + text[:100], fill='black')
            return image
    
    async def kang_sticker(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create sticker from image."""
        try:
            if not update.message.reply_to_message:
                await update.message.reply_text(
                    "❌ Please reply to an image with `/kang` to create a sticker!",
                    parse_mode='Markdown'
                )
                return
            
            reply_msg = update.message.reply_to_message
            image = None
            
            if reply_msg.photo:
                # Download photo
                photo_file = await reply_msg.photo[-1].get_file()
                photo_bytes = await photo_file.download_as_bytearray()
                image = Image.open(io.BytesIO(photo_bytes))
                
            elif reply_msg.sticker and not (reply_msg.sticker.is_animated or reply_msg.sticker.is_video):
                # Download static sticker
                sticker_file = await reply_msg.sticker.get_file()
                sticker_bytes = await sticker_file.download_as_bytearray()
                image = Image.open(io.BytesIO(sticker_bytes))
                
            elif reply_msg.document and reply_msg.document.mime_type and reply_msg.document.mime_type.startswith('image/'):
                # Download image document
                doc_file = await reply_msg.document.get_file()
                doc_bytes = await doc_file.download_as_bytearray()
                image = Image.open(io.BytesIO(doc_bytes))
                
            else:
                await update.message.reply_text("❌ Please reply to a static image or sticker!")
                return
            
            # Process image for sticker
            sticker_image = self._prepare_sticker_image(image)
            
            # Send as document (sticker file)
            bio = io.BytesIO()
            sticker_image.save(bio, 'PNG')
            bio.seek(0)
            
            await update.message.reply_document(
                document=bio,
                filename="sticker.png",
                caption="✅ Sticker ready!\n\n"
                       "To add to your sticker pack:\n"
                       "1. Save this image\n"
                       "2. Create sticker pack via @Stickers bot\n"
                       "3. Upload this image when prompted"
            )
            
        except Exception as e:
            logger.error(f"Error in kang: {e}")
            await update.message.reply_text("❌ Error creating sticker. Please try with a different image.")
    
    def _prepare_sticker_image(self, image: Image.Image) -> Image.Image:
        """Prepare image for sticker format."""
        # Convert to RGB if necessary
        if image.mode in ('RGBA', 'P', 'LA'):
            # Create white background
            background = Image.new('RGB', image.size, 'white')
            if image.mode == 'RGBA':
                background.paste(image, mask=image.split()[-1])
            else:
                background.paste(image)
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize to Telegram sticker dimensions (512x512 max)
        image.thumbnail((512, 512), Image.Resampling.LANCZOS)
        
        # Create square image if not already square
        if image.width != image.height:
            size = max(image.width, image.height)
            square_image = Image.new('RGB', (size, size), 'white')
            offset = ((size - image.width) // 2, (size - image.height) // 2)
            square_image.paste(image, offset)
            image = square_image
        
        return image
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photos sent to the bot."""
        await update.message.reply_text(
            "📸 Photo received!\n\n"
            "You can:\n"
            "• Reply with `/mmf text` to memify\n"
            "• Use `/kang` to make it a sticker\n"
            "• Or reply to text with `/q` for quotes",
            parse_mode='Markdown'
        )
    
    async def handle_sticker(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle stickers sent to the bot."""
        if update.message.sticker.is_animated or update.message.sticker.is_video:
            await update.message.reply_text("🎭 Animated sticker received! (Static memification only)")
        else:
            await update.message.reply_text(
                "🎨 Sticker received!\n\n"
                "You can:\n"
                "• Reply with `/mmf text` to memify it\n"
                "• Use `/kang` to add to your pack",
                parse_mode='Markdown'
            )
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages."""
        if update.message.text and not update.message.text.startswith('/'):
            await update.message.reply_text(
                "💡 Tip: Reply to any message with `/q` to create a quote sticker!\n"
                "Or send an image/sticker to get started.",
                parse_mode='Markdown'
            )
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Log errors."""
        logger.error(f"Exception while handling an update: {context.error}")

def main():
    """Start the bot."""
    if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        print("❌ ERROR: Please set your BOT_TOKEN environment variable or edit the script")
        print("Usage: export BOT_TOKEN='your_bot_token_here'")
        return
    
    # Create bot instance
    sticker_bot = StickerBot()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", sticker_bot.start))
    application.add_handler(CommandHandler("mmf", sticker_bot.memify_image))
    application.add_handler(CommandHandler("q", sticker_bot.quote_sticker))
    application.add_handler(CommandHandler("kang", sticker_bot.kang_sticker))
    
    # Handle messages
    application.add_handler(MessageHandler(filters.PHOTO, sticker_bot.handle_photo))
    application.add_handler(MessageHandler(filters.Sticker.ALL, sticker_bot.handle_sticker))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, sticker_bot.handle_text))
    
    # Error handler
    application.add_error_handler(sticker_bot.error_handler)
    
    # Start the Bot
    print("🤖 Bot is starting...")
    print("✅ Bot is running and ready to use!")
    print("⏹️  Press Ctrl+C to stop the bot")
    
    application.run_polling()

if __name__ == '__main__':
    main()
```

## 3. Updated `README.md`

```markdown
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
