import os
import logging
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageSequence
from io import BytesIO
import requests
import json
from datetime import datetime, timedelta
import asyncio
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode
import mimetypes
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
API_ID = os.environ.get('API_ID', '')
API_HASH = os.environ.get('API_HASH', '')

# Parse OWNER_ID from environment variable (single owner)
OWNER_ID = int(os.environ.get('OWNER_ID', '0'))

# Parse ADMIN_IDS from environment variable (comma-separated)
admin_ids_str = os.environ.get('ADMIN_IDS', '')
ADMIN_IDS = []
if admin_ids_str:
    try:
        ADMIN_IDS = [int(id.strip()) for id in admin_ids_str.split(',')]
    except ValueError:
        logger.warning(f"Invalid ADMIN_IDS format: {admin_ids_str}")

# Ensure owner is always in admin list
if OWNER_ID and OWNER_ID not in ADMIN_IDS:
    ADMIN_IDS.append(OWNER_ID)

# Other configuration
MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE', '52428800'))  # 50MB default
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///stickers.db')

# Sticker configuration
STICKER_PACK_NAME = "StickerBotPack_by_{}"
STICKER_PACK_TITLE = "StickerBot Collection"

class StickerMakerBot:
    def __init__(self):
        self.user_states = {}
        self.clone_queue = {}
        self.user_stats = {}
        self.bot_start_time = datetime.now()
        
    def is_owner(self, user_id: int) -> bool:
        """Check if user is owner"""
        return user_id == OWNER_ID
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin or owner"""
        return user_id in ADMIN_IDS or self.is_owner(user_id)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        user_id = user.id
        
        # Initialize user stats
        if user_id not in self.user_stats:
            self.user_stats[user_id] = {
                'name': user.first_name,
                'username': user.username,
                'sticker_count': 0,
                'memes_created': 0,
                'quotes_created': 0,
                'first_seen': datetime.now(),
                'last_active': datetime.now()
            }
        
        # Show owner/admin badge
        role = ""
        if self.is_owner(user_id):
            role = "👑 *Owner*"
        elif self.is_admin(user_id):
            role = "⭐ *Admin*"
        
        welcome_text = f"""
✨ *Welcome to Sticker Maker Bot* ✨

{role}
👤 *Hello {user.first_name}!*

I can help you create amazing stickers!

📌 *Available Commands:*
/start - Show this message
/mmf - Memify images/stickers (add text to media)
/q - Create quote stickers from messages
/kang - Add sticker to your pack
/help - Show help

{'👑 *Owner Commands:*' if self.is_owner(user_id) else '⭐ *Admin Commands:*' if self.is_admin(user_id) else ''}
{'/clone - Clone this bot' if self.is_admin(user_id) else ''}
{'/stats - Bot statistics' if self.is_admin(user_id) else ''}
{'/broadcast - Broadcast message' if self.is_owner(user_id) else ''}
{'/users - User statistics' if self.is_owner(user_id) else ''}
{'/restart - Restart bot' if self.is_owner(user_id) else ''}

📁 *Supported Formats:*
• Images (JPEG, PNG, WebP)
• Static Stickers
• Videos/GIFs (short clips)

⚡ *Simply send me any image/sticker to get started!*
        """
        
        keyboard = [
            [InlineKeyboardButton("📸 Memify Image", callback_data="memify_help")],
            [InlineKeyboardButton("💬 Create Quote", callback_data="quote_help")],
            [InlineKeyboardButton("➕ Add to Pack", callback_data="kang_help")],
        ]
        
        # Add admin buttons for admin users
        if self.is_admin(user_id):
            keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        user_id = update.effective_user.id
        
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

*Tips:*
- Use '\\n' for new lines in text
- Max file size: 50MB
- Sticker dimensions: 512x512px recommended
"""
        
        # Add admin help if user is admin
        if self.is_admin(user_id):
            help_text += """
*Admin Commands:*
`/clone` - Clone this bot (requires bot token)
`/stats` - Show bot statistics
`/broadcast` - Broadcast message to all users (Owner only)
`/users` - Show user statistics (Owner only)
`/restart` - Restart the bot (Owner only)
"""
        
        help_text += "\n*Need Help?* Contact the bot owner for support."
        
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
                    # Check file size
                    media_file.seek(0, 2)  # Seek to end
                    file_size = media_file.tell()
                    media_file.seek(0)  # Seek back to start
                    
                    if file_size > MAX_FILE_SIZE:
                        await update.message.reply_text(f"❌ File too large! Max size: {MAX_FILE_SIZE/1024/1024:.1f}MB")
                        return
                    
                    # Process image
                    meme_image = await self.add_text_to_image(media_file, text)
                    
                    if meme_image:
                        # Send as sticker or photo
                        await update.message.reply_sticker(sticker=meme_image)
                        # Update user stats
                        if user_id in self.user_stats:
                            self.user_stats[user_id]['memes_created'] += 1
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
        user_id = update.effective_user.id
        
        if update.message.reply_to_message:
            replied = update.message.reply_to_message
            author = " ".join(context.args) if context.args else replied.from_user.first_name
            
            quote_text = replied.text or replied.caption or "No text found"
            
            await update.message.reply_text("🔄 Creating quote sticker...")
            
            # Create quote image
            quote_image = await self.generate_quote_image(quote_text, author)
            
            if quote_image:
                await update.message.reply_sticker(sticker=quote_image)
                # Update user stats
                if user_id in self.user_stats:
                    self.user_stats[user_id]['quotes_created'] += 1
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
            # Update user stats
            if user_id in self.user_stats:
                self.user_stats[user_id]['sticker_count'] += 1
        elif message.sticker:
            await self.add_to_sticker_set(user_id, message.sticker, context)
            if user_id in self.user_stats:
                self.user_stats[user_id]['sticker_count'] += 1
        else:
            await message.reply_text("❌ Please reply to a sticker or send one")

    async def clone_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /clone command"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
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

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ This command is for admins only")
            return
        
        # Calculate uptime
        uptime = datetime.now() - self.bot_start_time
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        stats_text = f"""
📊 *Bot Statistics*

👥 *Total Users:* {len(self.user_stats)}
📈 *Active Users (24h):* {self.get_recent_users_count()}
🖼️ *Stickers Created:* {sum(user['sticker_count'] for user in self.user_stats.values())}
😂 *Memes Created:* {sum(user['memes_created'] for user in self.user_stats.values())}
💬 *Quotes Created:* {sum(user['quotes_created'] for user in self.user_stats.values())}

⏰ *Uptime:* {days}d {hours}h {minutes}m {seconds}s
🔄 *Clone Queue:* {len(self.clone_queue)}

*Owner Info:*
👑 Owner ID: `{OWNER_ID}`
⭐ Admins: {len(ADMIN_IDS)} user(s)

*Environment:*
• BOT_TOKEN: {'✅ Set' if BOT_TOKEN != 'YOUR_BOT_TOKEN_HERE' else '❌ Not Set'}
• MAX_FILE_SIZE: {MAX_FILE_SIZE/1024/1024:.1f} MB
• Bot Username: @{context.bot.username if context.bot.username else 'Not set'}

*Bot ID:* `{context.bot.id}`
        """
        
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

    async def users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /users command (owner only)"""
        user_id = update.effective_user.id
        
        if not self.is_owner(user_id):
            await update.message.reply_text("❌ This command is for owner only")
            return
        
        if not self.user_stats:
            await update.message.reply_text("📭 No users data available yet.")
            return
        
        # Get top 10 users by activity
        sorted_users = sorted(
            self.user_stats.items(),
            key=lambda x: x[1]['sticker_count'] + x[1]['memes_created'] + x[1]['quotes_created'],
            reverse=True
        )[:10]
        
        users_text = "👥 *Top 10 Users*\n\n"
        
        for idx, (uid, data) in enumerate(sorted_users, 1):
            username = f"@{data['username']}" if data['username'] else "No username"
            total_activity = data['sticker_count'] + data['memes_created'] + data['quotes_created']
            users_text += f"{idx}. {data['name']} ({username})\n"
            users_text += f"   📊 Stickers: {data['sticker_count']} | Memes: {data['memes_created']} | Quotes: {data['quotes_created']}\n"
            users_text += f"   🆔 ID: `{uid}`\n\n"
        
        users_text += f"📈 *Total Unique Users:* {len(self.user_stats)}"
        
        await update.message.reply_text(users_text, parse_mode=ParseMode.MARKDOWN)

    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /broadcast command (owner only)"""
        user_id = update.effective_user.id
        
        if not self.is_owner(user_id):
            await update.message.reply_text("❌ This command is for owner only")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: `/broadcast <message>`", 
                                          parse_mode=ParseMode.MARKDOWN)
            return
        
        message = " ".join(context.args)
        broadcast_text = f"""
📢 *Broadcast Message*

{message}

---
*Sent by bot owner*
        """
        
        # Send to owner first for preview
        await update.message.reply_text(f"📤 Sending broadcast to {len(self.user_stats)} users...\n\nPreview:\n{message}")
        
        # Send to all users
        success = 0
        failed = 0
        
        for user_id in self.user_stats.keys():
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=broadcast_text,
                    parse_mode=ParseMode.MARKDOWN
                )
                success += 1
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Failed to send broadcast to {user_id}: {e}")
                failed += 1
        
        await update.message.reply_text(
            f"✅ Broadcast completed!\n\n"
            f"✅ Success: {success}\n"
            f"❌ Failed: {failed}\n"
            f"📊 Total: {len(self.user_stats)}"
        )

    async def restart_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /restart command (owner only)"""
        user_id = update.effective_user.id
        
        if not self.is_owner(user_id):
            await update.message.reply_text("❌ This command is for owner only")
            return
        
        await update.message.reply_text("🔄 Restarting bot...")
        logger.info(f"Bot restart requested by owner {user_id}")
        
        # Save stats or state if needed
        os._exit(0)  # Force exit

    async def owner_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /owner command"""
        owner_info_text = f"""
👑 *Bot Owner Information*

*Owner ID:* `{OWNER_ID}`
*Admins:* {len(ADMIN_IDS)} user(s)

*Bot Information:*
• Name: Sticker Maker Bot
• Version: 2.0
• Created: 2025
• Framework: python-telegram-bot

*Commands:*
/start - Start the bot
/help - Show help
/owner - Show owner info (this message)

*Support:* Contact the bot owner for assistance.
"""
        
        await update.message.reply_text(owner_info_text, parse_mode=ParseMode.MARKDOWN)

    async def handle_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming media"""
        message = update.message
        
        # Track user
        user_id = update.effective_user.id
        if user_id not in self.user_stats:
            self.user_stats[user_id] = {
                'name': update.effective_user.first_name,
                'username': update.effective_user.username,
                'sticker_count': 0,
                'memes_created': 0,
                'quotes_created': 0,
                'first_seen': datetime.now(),
                'last_active': datetime.now()
            }
        else:
            self.user_stats[user_id]['last_active'] = datetime.now()
        
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

    async def process_video(self, message, context):
        """Process incoming video/gif"""
        keyboard = [
            [
                InlineKeyboardButton("🎥 Extract Frame", callback_data=f"extract_frame_{message.message_id}"),
                InlineKeyboardButton("⏱️ Duration", callback_data=f"duration_{message.message_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await message.reply_text(
            "Video/GIF detected. What would you like to do?",
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
        
        user_id = query.from_user.id
        data = query.data
        
        if data.startswith("add_text_"):
            await self.handle_add_text(query, context)
        elif data.startswith("make_sticker_"):
            await self.handle_make_sticker(query, context)
        elif data.startswith("extract_frame_"):
            await self.extract_frame(query, context)
        elif data == "kang_sticker":
            await self.handle_kang_callback(query, context)
        elif data == "admin_panel":
            if self.is_admin(user_id):
                await self.show_admin_panel(query, context)
            else:
                await query.edit_message_text("❌ Access denied. Admin only.")
        elif "help" in data:
            await self.show_help(query, context)

    async def show_admin_panel(self, query, context):
        """Show admin panel"""
        user_id = query.from_user.id
        
        admin_text = f"""
👑 *Admin Panel*

*User:* {query.from_user.first_name}
*Role:* {'👑 Owner' if self.is_owner(user_id) else '⭐ Admin'}

*Bot Stats:*
• Users: {len(self.user_stats)}
• Uptime: {(datetime.now() - self.bot_start_time).days} days

*Quick Actions:*
        """
        
        keyboard = [
            [InlineKeyboardButton("📊 Statistics", callback_data="cmd_stats")],
            [InlineKeyboardButton("👥 Users", callback_data="cmd_users")],
            [InlineKeyboardButton("🔄 Restart", callback_data="cmd_restart")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="cmd_broadcast")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(admin_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

    async def handle_add_text(self, query, context):
        """Handle add text callback"""
        await query.edit_message_text("Please send the text you want to add to the image.")

    async def handle_make_sticker(self, query, context):
        """Handle make sticker callback"""
        message_id = int(query.data.split("_")[-1])
        
        try:
            # Get the original message
            message = await context.bot.get_message(chat_id=query.message.chat_id, message_id=message_id-1)
            
            if message.photo:
                await query.edit_message_text("🔄 Converting image to sticker...")
                
                # Download image
                file = await message.bot.get_file(message.photo[-1].file_id)
                image_bytes = BytesIO()
                await file.download_to_memory(image_bytes)
                image_bytes.seek(0)
                
                # Convert to sticker
                sticker = await self.image_to_sticker(image_bytes)
                
                if sticker:
                    await query.message.reply_sticker(sticker=sticker)
                    await query.edit_message_text("✅ Image converted to sticker!")
                else:
                    await query.edit_message_text("❌ Failed to convert image")
            else:
                await query.edit_message_text("❌ Original message doesn't contain an image")
                
        except Exception as e:
            logger.error(f"Error making sticker: {e}")
            await query.edit_message_text("❌ Error processing image")

    async def extract_frame(self, query, context):
        """Extract frame from video/gif"""
        message_id = int(query.data.split("_")[-1])
        
        try:
            # Get the original message
            message = await context.bot.get_message(chat_id=query.message.chat_id, message_id=message_id-1)
            
            await query.edit_message_text("🔄 Extracting frame from video...")
            
            # For Termux, we'll use a simpler approach
            # Download the video
            if message.video:
                file = await message.bot.get_file(message.video.file_id)
            elif message.animation:
                file = await message.bot.get_file(message.animation.file_id)
            else:
                await query.edit_message_text("❌ No video found")
                return
            
            video_bytes = BytesIO()
            await file.download_to_memory(video_bytes)
            video_bytes.seek(0)
            
            # Save temporarily and use ffmpeg if available
            import subprocess
            import tempfile
            
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
                tmp.write(video_bytes.read())
                tmp_path = tmp.name
            
            try:
                # Use ffmpeg to extract frame
                output_path = tmp_path.replace('.mp4', '.jpg')
                subprocess.run([
                    'ffmpeg', '-i', tmp_path, '-ss', '00:00:01', '-vframes', '1', output_path,
                    '-y'  # Overwrite output file if exists
                ], timeout=10)
                
                if os.path.exists(output_path):
                    with open(output_path, 'rb') as f:
                        await query.message.reply_photo(photo=f)
                    os.remove(output_path)
                else:
                    await query.edit_message_text("❌ Failed to extract frame")
                    
            except Exception as e:
                logger.error(f"FFmpeg error: {e}")
                await query.edit_message_text("❌ FFmpeg not available or video format not supported")
                
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                    
        except Exception as e:
            logger.error(f"Error extracting frame: {e}")
            await query.edit_message_text("❌ Error processing video")

    async def handle_kang_callback(self, query, context):
        """Handle kang callback"""
        await query.edit_message_text("Please use /kang command with a sticker.")

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

    async def image_to_sticker(self, image_bytes):
        """Convert image to sticker format"""
        try:
            # Open image
            image = Image.open(image_bytes)
            
            # Convert to RGB if necessary
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            
            # Resize to sticker dimensions (512x512 max)
            max_size = (512, 512)
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Create square image if not already square
            if image.width != image.height:
                size = max(image.width, image.height)
                square_image = Image.new('RGB', (size, size), (255, 255, 255))
                offset = ((size - image.width) // 2, (size - image.height) // 2)
                square_image.paste(image, offset)
                image = square_image
            
            # Save to bytes
            output = BytesIO()
            image.save(output, format="PNG")
            output.seek(0)
            
            return output
            
        except Exception as e:
            logger.error(f"Error converting image to sticker: {e}")
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
            lines = text.split('\n') if '\n' in text else [text]
            
            # Load font
            try:
                font = await self.load_font(40)
            except:
                font = ImageFont.load_default()
            
            # Calculate text position (center)
            total_height = 0
            line_heights = []
            
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                line_height = bbox[3] - bbox[1]
                line_heights.append(line_height)
                total_height += line_height + 10
            
            y_position = (image.height - total_height) // 2
            
            for i, line in enumerate(lines):
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                x = (image.width - text_width) // 2
                
                # Add text with outline
                draw.text((x, y_position), line, font=font, fill="white", 
                         stroke_width=3, stroke_fill="black")
                
                y_position += line_heights[i] + 10
            
            # Save to bytes
            output = BytesIO()
            image.save(output, format="PNG")
            output.seek(0)
            
            return output
            
        except Exception as e:
            logger.error(f"Error adding text to image: {e}")
            return None

    async def load_font(self, size=40):
        """Load font with multiple fallbacks for Termux"""
        font_paths = [
            "arial.ttf",
            "/data/data/com.termux/files/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/system/fonts/Roboto-Regular.ttf",
            "/system/fonts/DroidSans.ttf",
            "fonts/arial.ttf",
            "fonts/Roboto-Regular.ttf"
        ]
        
        for path in font_paths:
            try:
                if os.path.exists(path):
                    return ImageFont.truetype(path, size)
            except:
                continue
        
        # Try to download a font if none exists
        try:
            return await self.download_font(size)
        except:
            return ImageFont.load_default()

    async def download_font(self, size=40):
        """Download a font if not available locally"""
        font_url = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf"
        
        try:
            response = requests.get(font_url, timeout=10)
            if response.status_code == 200:
                # Save font to local directory
                os.makedirs("fonts", exist_ok=True)
                font_path = "fonts/Roboto-Regular.ttf"
                
                with open(font_path, "wb") as f:
                    f.write(response.content)
                
                return ImageFont.truetype(font_path, size)
        except Exception as e:
            logger.error(f"Failed to download font: {e}")
        
        return ImageFont.load_default()

    async def generate_quote_image(self, text, author):
        """Generate quote image with text and author"""
        try:
            # Create image with gradient background
            width, height = 512, 512
            
            # Create gradient background
            image = Image.new('RGB', (width, height), color='white')
            draw = ImageDraw.Draw(image)
            
            # Add gradient effect
            for i in range(height):
                r = 240 - int(i * 0.1)
                g = 248 - int(i * 0.1)
                b = 255 - int(i * 0.05)
                draw.line([(0, i), (width, i)], fill=(r, g, b))
            
            # Load fonts
            try:
                font_large = await self.load_font(30)
                font_small = await self.load_font(20)
                font_italic = await self.load_font(25)
            except:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()
                font_italic = ImageFont.load_default()
            
            # Add quote marks
            draw.text((50, 50), "❝", font=font_large, fill=(100, 100, 100))
            draw.text((width - 100, height - 100), "❞", font=font_large, fill=(100, 100, 100))
            
            # Add quote text with word wrapping
            words = text.split()
            lines = []
            current_line = []
            
            for word in words:
                current_line.append(word)
                test_line = ' '.join(current_line)
                bbox = draw.textbbox((0, 0), test_line, font=font_italic)
                line_width = bbox[2] - bbox[0]
                
                if line_width > width - 100:  # 50px margin on each side
                    current_line.pop()
                    lines.append(' '.join(current_line))
                    current_line = [word]
            
            if current_line:
                lines.append(' '.join(current_line))
            
            # Draw lines (limit to 6 lines)
            y = 100
            for line in lines[:6]:
                bbox = draw.textbbox((0, 0), line, font=font_italic)
                text_width = bbox[2] - bbox[0]
                x = (width - text_width) // 2
                draw.text((x, y), line, font=font_italic, fill=(50, 50, 50))
                y += 40
            
            # Add author
            author_text = f"— {author}"
            bbox = draw.textbbox((0, 0), author_text, font=font_small)
            text_width = bbox[2] - bbox[0]
            x = width - text_width - 50
            draw.text((x, height - 80), author_text, font=font_small, fill=(100, 100, 100))
            
            # Add decorative line
            draw.line([(width//2 - 50, height - 60), (width//2 + 50, height - 60)], 
                     fill=(150, 150, 150), width=2)
            
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
            sticker_set_name = f"stickerpack_{user_id}_by_{context.bot.username}"
            
            # Try to create sticker set or add sticker
            try:
                await context.bot.create_new_sticker_set(
                    user_id=user_id,
                    name=sticker_set_name,
                    title=f"{context.bot.username}'s Collection",
                    stickers=[sticker],
                    sticker_format="static" if not sticker.is_animated else "animated",
                    emojis="😀"
                )
                await context.bot.send_message(
                    user_id,
                    f"✅ Sticker pack created!\n"
                    f"📦 Pack: `{sticker_set_name}`\n"
                    f"🔗 Link: https://t.me/addstickers/{sticker_set_name}"
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
                "❌ Failed to add sticker. Please try again.\n"
                "Note: You need to start @Stickers bot first."
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

    def get_recent_users_count(self, hours=24):
        """Count users active in last N hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return sum(1 for user in self.user_stats.values() 
                  if user.get('last_active', datetime.min) > cutoff_time)

# Main function
def main():
    """Start the bot"""
    # Check if BOT_TOKEN is set
    if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        logger.error("❌ BOT_TOKEN not set! Please set it in .env file")
        logger.info("💡 Create a .env file with:")
        logger.info("   BOT_TOKEN=your_token_here")
        logger.info("   OWNER_ID=your_telegram_id")
        return
    
    # Check if OWNER_ID is set
    if OWNER_ID == 0:
        logger.warning("⚠️ OWNER_ID not set! Some features will be disabled.")
        logger.info("💡 Add OWNER_ID=your_telegram_id to .env file")
    
    bot = StickerMakerBot()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("owner", bot.owner_info))
    application.add_handler(CommandHandler("mmf", bot.memify_image))
    application.add_handler(CommandHandler("q", bot.create_quote))
    application.add_handler(CommandHandler("kang", bot.kang_sticker))
    application.add_handler(CommandHandler("clone", bot.clone_bot))
    application.add_handler(CommandHandler("stats", bot.stats_command))
    application.add_handler(CommandHandler("users", bot.users_command))
    application.add_handler(CommandHandler("broadcast", bot.broadcast_command))
    application.add_handler(CommandHandler("restart", bot.restart_command))
    
    # Media handlers
    application.add_handler(MessageHandler(
        filters.PHOTO | filters.STICKER | filters.ANIMATION | filters.VIDEO,
        bot.handle_media
    ))
    
    # Callback query handler
    application.add_handler(CallbackQueryHandler(bot.callback_handler))
    
    # Start bot
    print("=" * 50)
    print("🤖 Sticker Maker Bot")
    print("=" * 50)
    print("🔗 Loading configuration from .env file")
    print(f"👑 Owner ID: {OWNER_ID if OWNER_ID != 0 else 'Not set'}")
    print(f"⭐ Admin IDs: {len(ADMIN_IDS)} admin(s)")
    print(f"🤖 Bot Username: @{application.bot.username}")
    print(f"📊 User tracking: Enabled")
    print("=" * 50)
    print("✅ Bot is starting...")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
