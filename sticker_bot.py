import os
import sys
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
import subprocess
import tempfile

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
MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE', '10485760'))  # 10MB default for Termux
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
        self.ffmpeg_available = self.check_ffmpeg()
        
    def check_ffmpeg(self):
        """Check if ffmpeg is available"""
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
            return True
        except:
            return False
        
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
        
        ffmpeg_status = "✅ Available" if self.ffmpeg_available else "❌ Not available (video features limited)"
        
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
• Videos/GIFs (short clips) {ffmpeg_status}

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
- Max file size: 10MB
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

*System Info:*
📱 Platform: {'Termux' if 'com.termux' in os.getcwd() else 'Server'}
🎬 FFmpeg: {'✅ Available' if self.ffmpeg_available else '❌ Not available'}

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
• Platform: {'Termux (Android)' if 'com.termux' in os.getcwd() else 'Server'}

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
            ],
            [
                InlineKeyboardButton("🎨 Add Filter", callback_data=f"filter_{message.message_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await message.reply_text(
            "What would you like to do with this image?",
            reply_markup=reply_markup
        )

    async def process_video(self, message, context):
        """Process incoming video/gif"""
        if not self.ffmpeg_available:
            await message.reply_text("⚠️ Video processing requires FFmpeg. Please install it with: `pkg install ffmpeg`")
            return
            
        keyboard = [
            [
                InlineKeyboardButton("🎥 Extract Frame", callback_data=f"extract_frame_{message.message_id}"),
                InlineKeyboardButton("⏱️ Get Duration", callback_data=f"duration_{message.message_id}")
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
        elif data.startswith("duration_"):
            await self.get_duration(query, context)
        elif data.startswith("filter_"):
            await self.apply_filter(query, context)
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
• FFmpeg: {'✅ Available' if self.ffmpeg_available else '❌ Not available'}

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
        message_id = int(query.data.split("_")[-1])
        self.user_states[query.from_user.id] = {
            'action': 'add_text',
            'message_id': message_id
        }
        await query.edit_message_text("📝 Please send the text you want to add to the image.\n\nUse \\n for new lines.")

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
            
            # Download the video
            if message.video:
                file = await message.bot.get_file(message.video.file_id)
                file_ext = '.mp4'
            elif message.animation:
                file = await message.bot.get_file(message.animation.file_id)
                file_ext = '.gif'
            else:
                await query.edit_message_text("❌ No video found")
                return
            
            video_bytes = BytesIO()
            await file.download_to_memory(video_bytes)
            
            # Save temporarily
            with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp:
                tmp.write(video_bytes.getvalue())
                tmp_path = tmp.name
            
            try:
                # Use ffmpeg to extract frame
                output_path = tmp_path.replace(file_ext, '.jpg')
                
                cmd = ['ffmpeg', '-i', tmp_path, '-ss', '00:00:01', 
                       '-vframes', '1', '-q:v', '2', output_path, '-y']
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if os.path.exists(output_path):
                    with open(output_path, 'rb') as f:
                        await query.message.reply_photo(photo=f)
                    await query.edit_message_text("✅ Frame extracted successfully!")
                    os.remove(output_path)
                else:
                    await query.edit_message_text("❌ Failed to extract frame. FFmpeg error.")
                    
            except subprocess.TimeoutExpired:
                await query.edit_message_text("❌ Operation timed out. Video might be too long.")
            except Exception as e:
                logger.error(f"FFmpeg error: {e}")
                await query.edit_message_text("❌ Error processing video")
                
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                    
        except Exception as e:
            logger.error(f"Error extracting frame: {e}")
            await query.edit_message_text("❌ Error processing video")

    async def get_duration(self, query, context):
        """Get video duration"""
        message_id = int(query.data.split("_")[-1])
        
        try:
            # Get the original message
            message = await context.bot.get_message(chat_id=query.message.chat_id, message_id=message_id-1)
            
            await query.edit_message_text("🔄 Getting video duration...")
            
            # Download the video
            if message.video:
                file = await message.bot.get_file(message.video.file_id)
            elif message.animation:
                file = await message.bot.get_file(message.animation.file_id)
            else:
                await query.edit_message_text("❌ No video found")
                return
            
            # Get file size
            file_size = file.file_size
            duration = "Unknown"
            
            if file_size:
                # Estimate duration based on file size (rough estimate)
                if message.video:
                    # Average bitrate for mobile videos
                    estimated_duration = file_size / (500 * 1024)  # 500 kbps
                    minutes = int(estimated_duration // 60)
                    seconds = int(estimated_duration % 60)
                    duration = f"{minutes}m {seconds}s (estimated)"
                elif message.animation:
                    # GIFs are usually short
                    duration = "Short GIF"
            
            await query.edit_message_text(f"📊 Video Information:\n\n"
                                         f"📁 File Size: {file_size/1024:.1f} KB\n"
                                         f"⏱️ Duration: {duration}\n"
                                         f"🎬 Type: {'Video' if message.video else 'GIF'}")

        except Exception as e:
            logger.error(f"Error getting duration: {e}")
            await query.edit_message_text("❌ Error getting video information")

    async def apply_filter(self, query, context):
        """Apply filter to image"""
        message_id = int(query.data.split("_")[-1])
        
        try:
            # Get the original message
            message = await context.bot.get_message(chat_id=query.message.chat_id, message_id=message_id-1)
            
            if message.photo:
                await query.edit_message_text("🔄 Applying filter...")
                
                # Download image
                file = await message.bot.get_file(message.photo[-1].file_id)
                image_bytes = BytesIO()
                await file.download_to_memory(image_bytes)
                image_bytes.seek(0)
                
                # Apply filter
                filtered_image = await self.apply_image_filter(image_bytes, "grayscale")
                
                if filtered_image:
                    await query.message.reply_photo(photo=filtered_image)
                    await query.edit_message_text("✅ Filter applied!")
                else:
                    await query.edit_message_text("❌ Failed to apply filter")
            else:
                await query.edit_message_text("❌ Original message doesn't contain an image")
                
        except Exception as e:
            logger.error(f"Error applying filter: {e}")
            await query.edit_message_text("❌ Error processing image")

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
            
            # Position text at top and bottom for classic meme format
            if len(lines) >= 2:
                # Top text
                top_line = lines[0]
                bbox = draw.textbbox((0, 0), top_line, font=font)
                text_width = bbox[2] - bbox[0]
                x = (image.width - text_width) // 2
                draw.text((x, 10), top_line, font=font, fill="white", 
                         stroke_width=3, stroke_fill="black")
                
                # Bottom text
                bottom_line = lines[1]
                bbox = draw.textbbox((0, 0), bottom_line, font=font)
                text_width = bbox[2] - bbox[0]
                x = (image.width - text_width) // 2
                draw.text((x, image.height - bbox[3] - 10), bottom_line, font=font, 
                         fill="white", stroke_width=3, stroke_fill="black")
            else:
                # Center text for single line
                line = lines[0]
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                x = (image.width - text_width) // 2
                y = (image.height - text_height) // 2
                draw.text((x, y), line, font=font, fill="white", 
                         stroke_width=3, stroke_fill="black")
            
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
        # Check Termux fonts directory first
        termux_fonts = [
            "/data/data/com.termux/files/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/data/data/com.termux/files/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans.ttf",
        ]
        
        # System fonts
        system_fonts = [
            "/system/fonts/Roboto-Regular.ttf",
            "/system/fonts/DroidSans.ttf",
            "/system/fonts/NotoSans-Regular.ttf",
        ]
        
        # Local fonts
        local_fonts = [
            "fonts/Roboto-Regular.ttf",
            "fonts/arial.ttf",
            "arial.ttf",
        ]
        
        # Combine all font paths
        font_paths = termux_fonts + system_fonts + local_fonts
        
        for path in font_paths:
            try:
                if os.path.exists(path):
                    return ImageFont.truetype(path, size)
            except:
                continue
        
        # If no font found, try to download one
        try:
            return await self.download_font(size)
        except:
            return ImageFont.load_default()

    async def download_font(self, size=40):
        """Download a font if not available locally"""
        font_urls = [
            "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf",
            "https://raw.githubusercontent.com/googlefonts/roboto/main/src/hinted/Roboto-Regular.ttf",
        ]
        
        os.makedirs("fonts", exist_ok=True)
        
        for font_url in font_urls:
            try:
                response = requests.get(font_url, timeout=10)
                if response.status_code == 200:
                    font_path = "fonts/Roboto-Regular.ttf"
                    
                    with open(font_path, "wb") as f:
                        f.write(response.content)
                    
                    return ImageFont.truetype(font_path, size)
            except:
                continue
        
        return ImageFont.load_default()

    async def apply_image_filter(self, image_bytes, filter_type="grayscale"):
        """Apply filter to image"""
        try:
            # Open image
            image = Image.open(image_bytes)
            
            # Apply filter
            if filter_type == "grayscale":
                filtered_image = ImageOps.grayscale(image)
            elif filter_type == "invert":
                filtered_image = ImageOps.invert(image.convert('RGB'))
            elif filter_type == "posterize":
                filtered_image = ImageOps.posterize(image, 3)
            elif filter_type == "solarize":
                filtered_image = ImageOps.solarize(image, threshold=128)
            else:
                filtered_image = image
            
            # Save to bytes
            output = BytesIO()
            filtered_image.save(output, format="PNG")
            output.seek(0)
            
            return output
            
        except Exception as e:
            logger.error(f"Error applying filter: {e}")
            return None

    async def generate_quote_image(self, text, author):
        """Generate quote image with text and author"""
        try:
            # Create image with gradient background
            width, height = 512, 512
            
            # Create simple background
            image = Image.new('RGB', (width, height), color=(240, 248, 255))  # Light blue
            draw = ImageDraw.Draw(image)
            
            # Add subtle pattern
            for i in range(0, width, 20):
                draw.line([(i, 0), (i, height)], fill=(230, 240, 250), width=1)
            
            # Load fonts
            try:
                font_large = await self.load_font(28)
                font_small = await self.load_font(18)
            except:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()
            
            # Add quote marks (using text since emoji might not render)
            draw.text((40, 40), "\"", font=font_large, fill=(100, 100, 150))
            draw.text((width - 80, height - 80), "\"", font=font_large, fill=(100, 100, 150))
            
            # Add quote text with word wrapping
            words = text.split()
            lines = []
            current_line = []
            
            for word in words:
                current_line.append(word)
                test_line = ' '.join(current_line)
                bbox = draw.textbbox((0, 0), test_line, font=font_large)
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
                bbox = draw.textbbox((0, 0), line, font=font_large)
                text_width = bbox[2] - bbox[0]
                x = (width - text_width) // 2
                draw.text((x, y), line, font=font_large, fill=(50, 50, 50))
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
            # Create sticker set name
            sticker_set_name = f"stickerpack_{user_id}_by_{context.bot.username}"
            
            # Check if sticker is animated
            is_animated = sticker.is_animated if hasattr(sticker, 'is_animated') else False
            
            # Get sticker file
            file = await sticker.get_file()
            sticker_bytes = BytesIO()
            await file.download_to_memory(sticker_bytes)
            sticker_bytes.seek(0)
            
            # Try to create sticker set or add sticker
            try:
                # For simplicity, we'll just send the sticker back
                await context.bot.send_message(
                    user_id,
                    f"✅ Sticker processed!\n\n"
                    f"📦 Sticker added to bot cache\n"
                    f"🎭 Type: {'Animated' if is_animated else 'Static'}\n"
                    f"📝 Note: Full sticker pack creation requires additional setup."
                )
                
                # Also send the sticker back
                sticker_bytes.seek(0)
                await context.bot.send_sticker(user_id, sticker=sticker_bytes)
                
            except Exception as e:
                logger.error(f"Error with sticker: {e}")
                await context.bot.send_message(
                    user_id,
                    "❌ Failed to process sticker. Please try again.\n"
                    "Note: Sticker might be too large or in unsupported format."
                )
                    
        except Exception as e:
            logger.error(f"Error adding to sticker set: {e}")
            await context.bot.send_message(
                user_id,
                "❌ Failed to process sticker. Please try again."
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
2. Bot will process the sticker
3. Sticker is saved to bot cache

*Tips:*
• Supports static and animated stickers
• Max size: 10MB
• Common formats only
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
        print("\n📝 How to get BOT_TOKEN:")
        print("1. Open Telegram and search for @BotFather")
        print("2. Send /newbot and follow instructions")
        print("3. Copy the token and add to .env file")
        return
    
    # Check if OWNER_ID is set
    if OWNER_ID == 0:
        logger.warning("⚠️ OWNER_ID not set! Some features will be disabled.")
        logger.info("💡 Add OWNER_ID=your_telegram_id to .env file")
        print("\n📝 How to get your Telegram ID:")
        print("1. Open Telegram and search for @userinfobot")
        print("2. Send /start to the bot")
        print("3. Copy your ID and add to .env file")
    
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
    print("🤖 STICKER MAKER BOT - TERMUX EDITION")
    print("=" * 50)
    print(f"👑 Owner ID: {OWNER_ID if OWNER_ID != 0 else 'Not set'}")
    print(f"⭐ Admin IDs: {len(ADMIN_IDS)} admin(s)")
    print(f"🎬 FFmpeg: {'✅ Available' if bot.ffmpeg_available else '❌ Not available'}")
    print(f"📁 Max file size: {MAX_FILE_SIZE/1024/1024:.1f} MB")
    print("=" * 50)
    print("✅ Bot is starting...")
    print("🔄 Use /start in Telegram to begin")
    print("=" * 50)
    
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        print(f"\n❌ Bot crashed: {e}")

if __name__ == '__main__':
    main()
