import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
from io import BytesIO
import subprocess

class AdvancedStickerBot:
    def __init__(self, token):
        self.token = token
        self.application = Application.builder().token(token).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("video", self.video_to_sticker))
        self.application.add_handler(MessageHandler(filters.VIDEO | filters.ANIMATION, self.handle_video))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🎥 **Video Sticker Bot**\n\n"
            "Send me a video or use /video to convert to sticker!\n"
            "Max duration: 3 seconds\n"
            "Max size: 10MB"
        )
    
    async def video_to_sticker(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message.reply_to_message or not update.message.reply_to_message.video:
            await update.message.reply_text("❌ Please reply to a video with /video")
            return
        
        await self.process_video_sticker(update, update.message.reply_to_message.video)
    
    async def handle_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        video = update.message.video or update.message.animation
        await self.process_video_sticker(update, video)
    
    async def process_video_sticker(self, update: Update, video):
        try:
            await update.message.reply_text("🔄 Processing video sticker...")
            
            # Download video
            file = await video.get_file()
            video_bytes = BytesIO()
            await file.download_to_memory(video_bytes)
            video_bytes.seek(0)
            
            # Save temporary file
            with open("temp_video.mp4", "wb") as f:
                f.write(video_bytes.getvalue())
            
            # Convert to webm (Telegram sticker format)
            output_path = "output_sticker.webm"
            
            # Use ffmpeg to convert (ensure ffmpeg is installed in Termux)
            cmd = [
                'ffmpeg', '-i', 'temp_video.mp4',
                '-c', 'vp9', '-b:v', '0', '-crf', '40',
                '-vf', 'scale=512:512:force_original_aspect_ratio=decrease:flags=lanczos+full_chroma_inp+full_chroma_int',
                '-r', '30', '-t', '3', '-an',
                output_path
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Send as sticker
            with open(output_path, 'rb') as sticker_file:
                await update.message.reply_sticker(sticker=sticker_file)
            
            # Cleanup
            os.remove("temp_video.mp4")
            os.remove(output_path)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error processing video: {str(e)}")

def main():
    BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
    bot = AdvancedStickerBot(BOT_TOKEN)
    bot.application.run_polling()

if __name__ == "__main__":
    main()
