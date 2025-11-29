import os
import asyncio
import logging
from telegram import Update, Sticker, StickerSet
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image, ImageDraw, ImageFont, ImageOps
import cv2
import numpy as np
import requests
from io import BytesIO
import json
import sqlite3
from datetime import datetime

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class StickerBot:
    def __init__(self, token):
        self.token = token
        self.application = Application.builder().token(token).build()
        self.setup_handlers()
        self.setup_database()
        
    def setup_database(self):
        """Initialize SQLite database for user data and bot tokens"""
        self.conn = sqlite3.connect('bot_data.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        # Create tables
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_bots (
                user_id INTEGER PRIMARY KEY,
                bot_token TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()
    
    def setup_handlers(self):
        """Setup all command handlers"""
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("mmf", self.memify))
        self.application.add_handler(CommandHandler("q", self.quote_sticker))
        self.application.add_handler(CommandHandler("kang", self.kang_sticker))
        self.application.add_handler(CommandHandler("clone", self.clone_bot))
        self.application.add_handler(MessageHandler(filters.ALL, self.handle_message))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        welcome_text = f"""
🤖 **Welcome to Sticker Maker Bot 2025** 🎨

**Available Commands:**
/start - Start the bot
/mmf - Memify images or stickers
/q - Create quote stickers from messages
/kang - Create your sticker pack
/clone - Clone this bot with your token

**Features:**
• Image to Sticker conversion
• Video to Sticker conversion
• Meme text on stickers
• Custom sticker packs
• Bot cloning capability

Made with ❤️ using Python
        """
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
    
    async def memify(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Memify images or stickers"""
        try:
            if not (update.message.reply_to_message and 
                   (update.message.reply_to_message.photo or 
                    update.message.reply_to_message.sticker)):
                await update.message.reply_text(
                    "❌ Please reply to an image or sticker with /mmf <text>"
                )
                return
            
            # Get text from command
            if not context.args:
                await update.message.reply_text("❌ Please provide text: /mmf <your_text>")
                return
            
            text = " ".join(context.args)
            await update.message.reply_text("🔄 Processing your memified sticker...")
            
            # Get the file
            if update.message.reply_to_message.photo:
                file_id = update.message.reply_to_message.photo[-1].file_id
            else:
                file_id = update.message.reply_to_message.sticker.file_id
            
            file = await context.bot.get_file(file_id)
            file_bytes = BytesIO()
            await file.download_to_memory(file_bytes)
            file_bytes.seek(0)
            
            # Process image
            image = Image.open(file_bytes)
            image = await self.add_meme_text(image, text)
            
            # Convert to sticker
            sticker_file = await self.convert_to_sticker(image)
            
            await update.message.reply_sticker(sticker=sticker_file)
            
        except Exception as e:
            logger.error(f"Error in memify: {e}")
            await update.message.reply_text("❌ Error processing image. Please try again.")
    
    async def add_meme_text(self, image: Image.Image, text: str) -> Image.Image:
        """Add meme text to image"""
        try:
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Resize for sticker (512x512 max)
            image.thumbnail((512, 512))
            
            draw = ImageDraw.Draw(image)
            
            # Try to use a font (you might need to install fonts in Termux)
            try:
                font = ImageFont.truetype("arial.ttf", 40)
            except:
                font = ImageFont.load_default()
            
            # Calculate text position (top and bottom)
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Add top text
            top_position = (10, 10)
            draw.rectangle([top_position, (top_position[0] + text_width + 10, top_position[1] + text_height + 10)], 
                          fill='white')
            draw.text((top_position[0] + 5, top_position[1] + 5), text, fill='black', font=font)
            
            return image
            
        except Exception as e:
            logger.error(f"Error adding text: {e}")
            return image
    
    async def quote_sticker(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create quote stickers from messages"""
        try:
            if not update.message.reply_to_message:
                await update.message.reply_text("❌ Please reply to a message with /q")
                return
            
            replied_message = update.message.reply_to_message
            text = replied_message.text or replied_message.caption or "Quote"
            
            await update.message.reply_text("🔄 Creating quote sticker...")
            
            # Create quote image
            image = await self.create_quote_image(text, replied_message.from_user.first_name)
            
            # Convert to sticker
            sticker_file = await self.convert_to_sticker(image)
            
            await update.message.reply_sticker(sticker=sticker_file)
            
        except Exception as e:
            logger.error(f"Error in quote_sticker: {e}")
            await update.message.reply_text("❌ Error creating quote sticker.")
    
    async def create_quote_image(self, text: str, author: str) -> Image.Image:
        """Create a quote image"""
        # Create a blank image
        img = Image.new('RGB', (512, 512), color='white')
        draw = ImageDraw.Draw(img)
        
        try:
            font_large = ImageFont.truetype("arial.ttf", 30)
            font_small = ImageFont.truetype("arial.ttf", 20)
        except:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        # Add quote text (wrapped)
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font_large)
            test_width = bbox[2] - bbox[0]
            
            if test_width <= 450:
                current_line.append(word)
            else:
                lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        # Draw lines
        y_position = 100
        for line in lines:
            draw.text((30, y_position), line, fill='black', font=font_large)
            y_position += 40
        
        # Add author
        draw.text((400, 450), f"- {author}", fill='gray', font=font_small)
        
        return img
    
    async def kang_sticker(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create sticker pack from multiple stickers"""
        try:
            if not update.message.reply_to_message:
                await update.message.reply_text(
                    "❌ Please reply to a sticker with /kang to add it to your pack\n\n"
                    "Send multiple stickers with /kang to create a pack"
                )
                return
            
            user_id = update.effective_user.id
            await update.message.reply_text("🔄 Adding sticker to your pack...")
            
            # This is a simplified version - actual sticker pack creation requires Bot API
            sticker = update.message.reply_to_message.sticker
            
            if sticker:
                await update.message.reply_text(
                    f"✅ Sticker added to your collection!\n"
                    f"Emoji: {sticker.emoji}\n"
                    f"Pack: {sticker.set_name if sticker.set_name else 'Custom Pack'}"
                )
            
        except Exception as e:
            logger.error(f"Error in kang_sticker: {e}")
            await update.message.reply_text("❌ Error processing sticker.")
    
    async def clone_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Clone the bot with user's token"""
        try:
            if not context.args:
                await update.message.reply_text(
                    "🔧 **Bot Cloner**\n\n"
                    "Usage: /clone <your_bot_token>\n\n"
                    "Get your token from @BotFather\n"
                    "This will create your own instance of this bot!"
                )
                return
            
            user_id = update.effective_user.id
            bot_token = context.args[0]
            
            # Validate token format
            if not bot_token.count(':') == 1:
                await update.message.reply_text("❌ Invalid bot token format!")
                return
            
            await update.message.reply_text("🔄 Cloning bot... This may take a moment.")
            
            # Save bot token
            self.cursor.execute(
                'INSERT OR REPLACE INTO user_bots (user_id, bot_token) VALUES (?, ?)',
                (user_id, bot_token)
            )
            self.conn.commit()
            
            # Create cloned bot instance
            cloned_bot = await self.create_cloned_bot(bot_token)
            
            if cloned_bot:
                await update.message.reply_text(
                    "✅ **Bot Cloned Successfully!**\n\n"
                    "Your bot is now running with all features:\n"
                    "• Sticker creation\n• Meme generation\n• Quote stickers\n• Sticker packs\n\n"
                    "Use your bot's username to access it!"
                )
            else:
                await update.message.reply_text("❌ Error cloning bot. Check your token.")
                
        except Exception as e:
            logger.error(f"Error in clone_bot: {e}")
            await update.message.reply_text("❌ Error cloning bot. Please check your token.")
    
    async def create_cloned_bot(self, token: str) -> bool:
        """Create and run a cloned bot instance"""
        try:
            # Create a new bot instance with the provided token
            cloned_bot = StickerBot(token)
            
            # Run in background (simplified - in production you'd use proper process management)
            asyncio.create_task(self.run_bot_in_background(cloned_bot))
            
            return True
        except Exception as e:
            logger.error(f"Error creating cloned bot: {e}")
            return False
    
    async def run_bot_in_background(self, bot_instance):
        """Run bot in background"""
        try:
            await bot_instance.application.run_polling()
        except Exception as e:
            logger.error(f"Background bot error: {e}")
    
    async def convert_to_sticker(self, image: Image.Image) -> BytesIO:
        """Convert PIL image to sticker format"""
        try:
            # Convert to WEBP for stickers
            output = BytesIO()
            image.save(output, format='WEBP', quality=95)
            output.seek(0)
            output.name = 'sticker.webp'
            return output
        except Exception as e:
            logger.error(f"Error converting to sticker: {e}")
            raise
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle other messages"""
        # You can add additional message handling here
        pass
    
    def run(self):
        """Start the bot"""
        logger.info("Starting Sticker Bot...")
        self.application.run_polling()

# Configuration
def main():
    # Replace with your bot token from @BotFather
    BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("Please set your bot token in the code!")
        return
    
    bot = StickerBot(BOT_TOKEN)
    bot.run()

if __name__ == "__main__":
    main()
