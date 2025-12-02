import os
import logging
from PIL import Image, ImageDraw, ImageFont, ImageOps
from io import BytesIO
import requests
import json
from datetime import datetime
import asyncio
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode
import mimetypes
from dotenv import load_dotenv  # Added this import

# Load environment variables from .env file
load_dotenv()  # Added this line

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration - Now loads from environment variables
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
API_ID = os.environ.get('API_ID', '')
API_HASH = os.environ.get('API_HASH', '')

# Parse ADMIN_IDS from environment variable (comma-separated)
admin_ids_str = os.environ.get('ADMIN_IDS', '')
ADMIN_IDS = []
if admin_ids_str:
    try:
        ADMIN_IDS = [int(id.strip()) for id in admin_ids_str.split(',')]
    except ValueError:
        logger.warning(f"Invalid ADMIN_IDS format: {admin_ids_str}")
        ADMIN_IDS = [123456789]  # Default admin ID

# Other configuration from environment variables
MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE', '52428800'))  # 50MB default
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///stickers.db')

# Sticker configuration
STICKER_PACK_NAME = "StickerBotPack_by_{}"
STICKER_PACK_TITLE = "StickerBot Collection"

class StickerMakerBot:
    def __init__(self):
        self.user_states = {}
        self.clone_queue = {}
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        welcome_text = f"""
✨ *Welcome to Sticker Maker Bot* ✨

👤 *Hello {user.first_name}!*

I can help you create amazing stickers!

📌 *Available Commands:*
/start - Show this message
/mmf - Memify images/stickers (add text to media)
/q - Create quote stickers from messages
/kang - Add sticker to your pack
/clone - Clone this bot (Admin only)
/help - Show help

📁 *Supported Formats:*
• Images (JPEG, PNG, WebP)
• Animated Stickers
• Videos (GIF, MP4 - short clips)

⚡ *Simply send me any image/sticker to get started!*
        """
        
        keyboard = [
            [InlineKeyboardButton("📸 Memify Image", callback_data="memify_help")],
            [InlineKeyboardButton("💬 Create Quote", callback_data="quote_help")],
            [InlineKeyboardButton("🔄 Clone Bot", callback_data="clone_help")],
            [InlineKeyboardButton("➕ Add to Pack", callback_data="kang_help")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
🆘 *Help Guide* 🆘

*Commands:*

1. `/mmf` - Add text to images/stickers
   Usage: Send `/mmf` then reply to an image with text
   Example: `/mmf Top Text\nBottom Text`

2. `/q` - Create quote sticker from message
   Usage: Reply to a message with `/q`
   You can add author text after: `/q - Author Name`

3. `/kang` - Add sticker to your pack
   Usage: Reply to a sticker with `/kang` or send sticker with caption

4. `/clone` - Clone this bot (Admin Feature)
   Usage: `/clone <your_bot_token>`
   Note: Only bot admins can use this

*Tips:*
- Use '\\n' for new lines in text
- For animated stickers, send as video/gif
- Max file size: 50MB
- Sticker dimensions: 512x512px recommended

*Need Help?* Contact @YourSupportChannel
        """
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

    async def memify_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /mmf command for memifying images"""
        user_id = update.effective_user.id
        
        if update.message.reply_to_message:
            replied = update.message.reply_to_message
            text = " ".join(context.args) if context.args else ""
            
            if replied.photo or replied.sticker or replied.animation or replied.video:
                await update.message.reply_text("🔄 Processing your meme...")
                
                # Download media
                media_file = await self.download_media(replied)
                
                if media_file:
                    # Process image
                    meme_image = await self.add_text_to_image(media_file, text)
                    
                    if meme_image:
                        # Send as sticker or photo
                        await update.message.reply_sticker(sticker=meme_image)
                    else:
                        await update.message.reply_text("❌ Failed to create meme")
                else:
                    await update.message.reply_text("❌ Could not download media")
            else:
                await update.message.reply_text("❌ Please reply to an image, sticker, or video")
        else:
            await update.message.reply_text("❌ Please reply to a message with `/mmf <text>`")

    async def create_quote(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /q command for creating quote stickers"""
        if update.message.reply_to_message:
            replied = update.message.reply_to_message
            author = " ".join(context.args) if context.args else replied.from_user.first_name
            
            quote_text = replied.text or replied.caption or "No text found"
            
            await update.message.reply_text("🔄 Creating quote sticker...")
            
            # Create quote image
            quote_image = await self.generate_quote_image(quote_text, author)
            
            if quote_image:
                await update.message.reply_sticker(sticker=quote_image)
            else:
                await update.message.reply_text("❌ Failed to create quote")
        else:
            await update.message.reply_text("❌ Please reply to a message with `/q`")

    async def kang_sticker(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /kang command for adding stickers to pack"""
        user_id = update.effective_user.id
        message = update.message
        
        if message.reply_to_message and message.reply_to_message.sticker:
            sticker = message.reply_to_message.sticker
            await self.add_to_sticker_set(user_id, sticker, context)
        elif message.sticker:
            await self.add_to_sticker_set(user_id, message.sticker, context)
        else:
            await message.reply_text("❌ Please reply to a sticker or send one")

    async def clone_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /clone command"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ This command is for admins only")
            return
            
        if context.args:
            token = context.args[0]
            await update.message.reply_text(f"🔄 Cloning bot with token: {token[:15]}...\n\n"
                                          "This feature requires additional setup.\n"
                                          "Please check the deployment guide.")
        else:
            await update.message.reply_text("Usage: `/clone <bot_token>`", 
                                          parse_mode=ParseMode.MARKDOWN)

    async def handle_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming media"""
        message = update.message
        
        if message.photo:
            await self.process_image(message, context)
        elif message.sticker:
            await self.suggest_kang(message)
        elif message.animation or message.video:
            await self.process_video(message, context)

    async def process_image(self, message, context):
        """Process incoming image"""
        keyboard = [
            [
                InlineKeyboardButton("📝 Add Text", callback_data=f"add_text_{message.message_id}"),
                InlineKeyboardButton("✨ Make Sticker", callback_data=f"make_sticker_{message.message_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await message.reply_text(
            "What would you like to do with this image?",
            reply_markup=reply_markup
        )

    async def suggest_kang(self, message):
        """Suggest adding sticker to pack"""
        keyboard = [
            [InlineKeyboardButton("➕ Add to My Pack", callback_data="kang_sticker")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await message.reply_text(
            "Want to add this sticker to your pack?",
            reply_markup=reply_markup
        )

    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data.startswith("add_text_"):
            await self.handle_add_text(query, context)
        elif data.startswith("make_sticker_"):
            await self.handle_make_sticker(query, context)
        elif data == "kang_sticker":
            await self.handle_kang_callback(query, context)
        elif "help" in data:
            await self.show_help(query, context)

    async def handle_add_text(self, query, context):
        """Handle add text callback"""
        await query.edit_message_text("Please send the text you want to add to the image.")

    async def handle_make_sticker(self, query, context):
        """Handle make sticker callback"""
        await query.edit_message_text("Converting image to sticker...")
        # Implementation for sticker conversion

    async def download_media(self, message):
        """Download media from message"""
        try:
            if message.photo:
                file_id = message.photo[-1].file_id
            elif message.sticker:
                file_id = message.sticker.file_id
            elif message.animation:
                file_id = message.animation.file_id
            elif message.video:
                file_id = message.video.file_id
            else:
                return None
                
            file = await message.bot.get_file(file_id)
            file_bytes = BytesIO()
            await file.download_to_memory(file_bytes)
            file_bytes.seek(0)
            return file_bytes
            
        except Exception as e:
            logger.error(f"Error downloading media: {e}")
            return None

    async def add_text_to_image(self, image_bytes, text):
        """Add text to image for memes"""
        try:
            # Open image
            image = Image.open(image_bytes)
            
            # Convert to RGB if necessary
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            
            # Resize if too large
            max_size = (512, 512)
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Add text
            draw = ImageDraw.Draw(image)
            
            # Split text
            lines = text.split('\n') if '\n' in text else [text[:20], text[20:40]] if len(text) > 20 else [text]
            
            # Load font (you'll need to add a font file)
            try:
                # Try different font paths
                font_paths = [
                    "arial.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/system/fonts/Roboto-Regular.ttf",
                    "fonts/arial.ttf"
                ]
                font = None
                for path in font_paths:
                    try:
                        font = ImageFont.truetype(path, 40)
                        break
                    except:
                        continue
                if not font:
                    font = ImageFont.load_default()
            except:
                font = ImageFont.load_default()
            
            # Calculate text position
            y_position = 10
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                
                x = (image.width - text_width) // 2
                draw.text((x, y_position), line, font=font, fill="white", stroke_width=2, stroke_fill="black")
                y_position += text_height + 10
            
            # Save to bytes
            output = BytesIO()
            image.save(output, format="PNG")
            output.seek(0)
            
            return output
            
        except Exception as e:
            logger.error(f"Error adding text to image: {e}")
            return None

    async def generate_quote_image(self, text, author):
        """Generate quote image with text and author"""
        try:
            # Create image
            width, height = 512, 512
            image = Image.new('RGB', (width, height), color='white')
            draw = ImageDraw.Draw(image)
            
            # Try to load font
            try:
                font_paths = [
                    "arial.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/system/fonts/Roboto-Regular.ttf",
                    "fonts/arial.ttf"
                ]
                font_large = None
                font_small = None
                for path in font_paths:
                    try:
                        font_large = ImageFont.truetype(path, 30)
                        font_small = ImageFont.truetype(path, 20)
                        break
                    except:
                        continue
                if not font_large:
                    font_large = ImageFont.load_default()
                    font_small = ImageFont.load_default()
            except:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()
            
            # Add quote text
            words = text.split()
            lines = []
            current_line = []
            
            for word in words:
                current_line.append(word)
                line = ' '.join(current_line)
                bbox = draw.textbbox((0, 0), line, font=font_large)
                line_width = bbox[2] - bbox[0]
                
                if line_width > width - 40:
                    current_line.pop()
                    lines.append(' '.join(current_line))
                    current_line = [word]
            
            if current_line:
                lines.append(' '.join(current_line))
            
            # Draw lines
            y = 50
            for line in lines[:8]:  # Limit to 8 lines
                bbox = draw.textbbox((0, 0), line, font=font_large)
                text_width = bbox[2] - bbox[0]
                x = (width - text_width) // 2
                draw.text((x, y), line, font=font_large, fill="black")
                y += 40
            
            # Add author
            author_text = f"— {author}"
            bbox = draw.textbbox((0, 0), author_text, font=font_small)
            text_width = bbox[2] - bbox[0]
            x = width - text_width - 20
            draw.text((x, height - 60), author_text, font=font_small, fill="gray")
            
            # Add decorative elements
            draw.line([(50, 30), (100, 30)], fill="gray", width=2)
            draw.line([(width - 100, 30), (width - 50, 30)], fill="gray", width=2)
            
            # Save to bytes
            output = BytesIO()
            image.save(output, format="PNG")
            output.seek(0)
            
            return output
            
        except Exception as e:
            logger.error(f"Error generating quote: {e}")
            return None

    async def add_to_sticker_set(self, user_id, sticker, context):
        """Add sticker to user's sticker set"""
        try:
            # Get sticker file
            file = await sticker.get_file()
            sticker_bytes = BytesIO()
            await file.download_to_memory(sticker_bytes)
            sticker_bytes.seek(0)
            
            # Create sticker set name
            sticker_set_name = f"stickerpack_by_{context.bot.username}_{user_id}"
            
            # Try to create sticker set or add sticker
            try:
                await context.bot.create_new_sticker_set(
                    user_id=user_id,
                    name=sticker_set_name,
                    title=f"{update.effective_user.first_name}'s Pack",
                    stickers=[sticker],
                    sticker_format="static" if not sticker.is_animated else "animated"
                )
                await context.bot.send_message(
                    user_id,
                    f"✅ Sticker pack created! You can add more stickers with /kang\n\n"
                    f"Your pack: https://t.me/addstickers/{sticker_set_name}"
                )
            except Exception as e:
                if "stickerset name already occupied" in str(e):
                    await context.bot.add_sticker_to_set(
                        user_id=user_id,
                        name=sticker_set_name,
                        sticker=sticker,
                        emojis="👍"
                    )
                    await context.bot.send_message(
                        user_id,
                        "✅ Sticker added to your pack!"
                    )
                else:
                    raise e
                    
        except Exception as e:
            logger.error(f"Error adding to sticker set: {e}")
            await context.bot.send_message(
                user_id,
                "❌ Failed to add sticker. Please try again."
            )

    async def show_help(self, query, context):
        """Show help for different features"""
        data = query.data
        
        if data == "memify_help":
            text = """
📸 *Memify Image Help*

Use `/mmf` to add text to images/stickers:

1. Reply to an image/sticker with `/mmf`
2. Add your text after the command
3. Use `\\n` for multiple lines

*Example:*
`/mmf Top Text\\nBottom Text`

*Supported:*
✅ Images (JPEG, PNG)
✅ Stickers (Static & Animated)
✅ Videos/GIFs (Short clips)
            """
        elif data == "quote_help":
            text = """
💬 *Quote Maker Help*

Use `/q` to create quote stickers:

1. Reply to any message with `/q`
2. Add author name after command (optional)
3. Bot will create a styled quote sticker

*Example:*
`/q - Albert Einstein`

*Features:*
✅ Automatic text wrapping
✅ Author attribution
✅ Clean design
            """
        elif data == "clone_help":
            text = """
🔄 *Clone Bot Help*

*Admin Only Feature*

Use `/clone <bot_token>` to clone this bot.

*Requirements:*
1. Bot token from @BotFather
2. Admin privileges
3. Server/hosting setup

*Note:* Full cloning requires server deployment.
            """
        elif data == "kang_help":
            text = """
➕ *Add to Pack Help*

Use `/kang` to add stickers to your pack:

1. Send or reply to a sticker with `/kang`
2. Bot will add it to your personal pack
3. First time creates new pack

*Tips:*
• You can add multiple stickers
• Pack is private to you
• Access via @Stickers bot
            """
        else:
            text = "Select a feature to learn more about it."
        
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command (admin only)"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ This command is for admins only")
            return
            
        stats_text = f"""
📊 *Bot Statistics*

👥 *Users:* {len(self.user_states)}
🔄 *Clone Queue:* {len(self.clone_queue)}
🖼️ *Active Sessions:* {len(self.user_states)}

*Environment:*
• BOT_TOKEN: {'Set' if BOT_TOKEN != 'YOUR_BOT_TOKEN_HERE' else 'Not Set'}
• ADMIN_IDS: {len(ADMIN_IDS)} admin(s)
• MAX_FILE_SIZE: {MAX_FILE_SIZE/1024/1024:.1f} MB

*Bot Info:*
• Username: @{context.bot.username}
• ID: {context.bot.id}
        """
        
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

# Main function
def main():
    """Start the bot"""
    # Check if BOT_TOKEN is set
    if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        logger.error("❌ BOT_TOKEN not set! Please set it in .env file")
        logger.info("💡 Create a .env file with: BOT_TOKEN=your_token_here")
        return
    
    bot = StickerMakerBot()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("mmf", bot.memify_image))
    application.add_handler(CommandHandler("q", bot.create_quote))
    application.add_handler(CommandHandler("kang", bot.kang_sticker))
    application.add_handler(CommandHandler("clone", bot.clone_bot))
    application.add_handler(CommandHandler("stats", bot.stats_command))
    
    # Media handlers
    application.add_handler(MessageHandler(
        filters.PHOTO | filters.STICKER | filters.ANIMATION | filters.VIDEO,
        bot.handle_media
    ))
    
    # Callback query handler
    application.add_handler(CallbackQueryHandler(bot.callback_handler))
    
    # Start bot
    print("🤖 Sticker Maker Bot is starting...")
    print("🔗 Loading configuration from .env file")
    print(f"👑 Admin IDs: {ADMIN_IDS}")
    print(f"🤖 Bot Username: @{application.bot.username}")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
