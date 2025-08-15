import logging
import json
import requests
import re
import html
import os
import tempfile
import asyncio
from datetime import datetime
from bs4 import BeautifulSoup
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, BadRequest
import aiohttp
import aiofiles

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class InstagramDownloaderBot:
    def __init__(self):
        self.api_id = int(os.getenv('API_ID'))
        self.api_hash = os.getenv('API_HASH')
        self.bot_token = os.getenv('BOT_TOKEN')

        # Initialize Pyrogram client
        self.app = Client(
            "instagram_bot",
            api_id=self.api_id,
            api_hash=self.api_hash,
            bot_token=self.bot_token,
            workdir="./sessions"
        )

        # Ensure sessions directory exists
        os.makedirs("./sessions", exist_ok=True)
        os.makedirs("./downloads", exist_ok=True)

        self.setup_handlers()

    def setup_handlers(self):
        """Set up command and message handlers"""

        @self.app.on_message(filters.command("start"))
        async def start_handler(client, message: Message):
            await self.start_command(message)

        @self.app.on_message(filters.command("help"))
        async def help_handler(client, message: Message):
            await self.help_command(message)

        @self.app.on_message(filters.text & ~filters.command(["start", "help"]))
        async def message_handler(client, message: Message):
            await self.handle_message(message)

    async def start_command(self, message: Message):
        """Send welcome message with HTML formatting"""
        welcome_text = """
🎬📸 <b>Instagram Reels &amp; Photos Downloader Bot</b>

Welcome! Send me any Instagram URL and I'll download it for you.

<b>What I can download:</b>
🎥 <b>Reels</b> - Video content (up to 2GB)
📸 <b>Photos</b> - Single or multiple images
📱 <b>Posts</b> - Any Instagram post content

<b>How to use:</b>
1. Copy an Instagram link
2. Send it to me  
3. Wait for processing ⏳
4. Get your content! 📥

<b>Supported formats:</b>
• instagram.com/reel/xxxxx (Videos)
• instagram.com/p/xxxxx (Photos/Videos)

Type /help for more information.

<b>Developer:</b> @medusaXD

<b>Enhanced Features:</b>
✅ Large file support (up to 2GB)
✅ Fast async downloads
✅ Progress tracking
✅ Error recovery
        """
        await message.reply_text(welcome_text, parse_mode='html')

    async def help_command(self, message: Message):
        """Send help information with HTML formatting"""
        help_text = """
📖 <b>Help - Instagram Downloader Bot</b>

<b>Commands:</b>
• <code>/start</code> - Start the bot
• <code>/help</code> - Show this help message

<b>Supported Content:</b>
🎥 <b>Video Reels</b> - Downloaded as MP4 (up to 2GB)
📸 <b>Single Photos</b> - Downloaded as JPG (HD Quality)
🖼️ <b>Multiple Photos</b> - Sent individually

<b>How to download:</b>
1. Open Instagram app or website
2. Copy the link of any post or reel
3. Send the link to this bot
4. Wait for processing (10-60 seconds)
5. Download will be sent automatically

<b>Supported URLs:</b>
• <code>https://instagram.com/reel/xxxxx</code>
• <code>https://instagram.com/p/xxxxx</code>
• <code>https://www.instagram.com/reel/xxxxx</code>
• <code>https://www.instagram.com/p/xxxxx</code>

<b>Features:</b>
🚀 <b>Fast Downloads</b> - Async processing
📊 <b>Progress Tracking</b> - Real-time updates
🔄 <b>Auto Retry</b> - Handles temporary failures
💾 <b>Large Files</b> - Supports files up to 2GB
🛡️ <b>Error Handling</b> - Comprehensive error recovery

<i>Note: Only public posts can be downloaded.</i>

<b>Developer:</b> @medusaXD
        """
        await message.reply_text(help_text, parse_mode='html')

    def extract_instagram_urls(self, text: str):
        """Extract Instagram URLs from message text"""
        instagram_pattern = r'https?://(?:www\.)?instagram\.com/(?:reel|p)/([a-zA-Z0-9_-]+)/?'
        full_urls = re.findall(r'https?://(?:www\.)?instagram\.com/(?:reel|p)/[a-zA-Z0-9_-]+/?', text)
        return full_urls

    async def get_reel_data(self, url: str):
        """Get reel data for video content with async requests"""
        target_url = "https://snapdownloader.com/tools/instagram-reels-downloader/download"

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                params = {'url': url}
                async with session.get(target_url, params=params, headers=headers) as response:
                    if response.status != 200:
                        return None

                    html_content = await response.text()

            # Extract video URL using regex
            video_match = re.search(r'<a[^>]+href="([^"]+\.mp4[^"]*)"[^>]*>', html_content)
            video_url = video_match.group(1) if video_match else ""

            # Extract thumbnail URL using regex  
            thumb_match = re.search(r'<a[^>]+href="([^"]+\.jpg[^"]*)"[^>]*>', html_content)
            thumb_url = thumb_match.group(1) if thumb_match else ""

            # Decode HTML entities
            video_url = html.unescape(video_url) if video_url else ""
            thumb_url = html.unescape(thumb_url) if thumb_url else ""

            if video_url:
                return {
                    "status": "success",
                    "type": "video",
                    "video": video_url,
                    "thumbnail": thumb_url,
                    "dev": "@medusaXD"
                }
            else:
                return None

        except Exception as e:
            logger.error(f"Error getting reel data: {str(e)}")
            return None

    async def get_photo_data(self, url: str):
        """Get photo data for image content with async requests"""
        target_url = "https://snapdownloader.com/tools/instagram-photo-downloader/download"

        try:
            headers = {
                'authority': 'snapdownloader.com',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'accept-language': 'en-US,en;q=0.9',
                'cache-control': 'no-cache',
                'pragma': 'no-cache',
                'referer': 'https://snapdownloader.com/tools/instagram-photo-downloader',
                'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
            }

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                params = {'url': url}
                async with session.get(target_url, params=params, headers=headers) as response:
                    if response.status != 200:
                        return None

                    html_content = await response.text()

            # Parse HTML using BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # Find download links for different resolutions
            resolutions = ['1080 x 1080', '750 x 750', '640 x 640']
            links = []

            for res in resolutions:
                download_links = soup.find_all('a', class_=lambda x: x and 'btn-download' in x)
                for a in download_links:
                    text = a.get_text(strip=True)
                    href = a.get('href', '')
                    if href:
                        href = html.unescape(href)
                        if f"Download ({res})" in text or res.replace(' x ', 'x') in href:
                            links.append(href)
                if links:
                    break

            if links:
                return {
                    "status": "success",
                    "type": "photos", 
                    "total_image": len(links),
                    "images": [{"image": link} for link in links],
                    "dev": "@medusaXD"
                }
            else:
                return None

        except Exception as e:
            logger.error(f"Error getting photo data: {str(e)}")
            return None

    def detect_content_type(self, url: str):
        """Detect if URL is for reel/video or photo content"""
        if '/reel/' in url:
            return 'reel'
        elif '/p/' in url:
            return 'mixed'
        else:
            return 'unknown'

    async def download_file_async(self, url: str, filename: str, progress_message: Message = None):
        """Download file asynchronously with progress tracking"""
        try:
            timeout = aiohttp.ClientTimeout(total=300)  # 5 minutes timeout
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return False

                    file_size = int(response.headers.get('content-length', 0))

                    async with aiofiles.open(filename, 'wb') as file:
                        downloaded = 0
                        last_update = 0

                        async for chunk in response.content.iter_chunked(8192):
                            await file.write(chunk)
                            downloaded += len(chunk)

                            # Update progress every 10%
                            if file_size > 0 and progress_message:
                                progress = (downloaded / file_size) * 100
                                if progress - last_update >= 10:
                                    try:
                                        await progress_message.edit_text(
                                            f"⏬ <b>Downloading...</b> {progress:.1f}% ({downloaded/1024/1024:.1f}MB/{file_size/1024/1024:.1f}MB)",
                                            parse_mode='html'
                                        )
                                        last_update = progress
                                    except:
                                        pass

                    return True

        except Exception as e:
            logger.error(f"Error downloading file: {str(e)}")
            return False

    async def handle_message(self, message: Message):
        """Handle incoming messages with HTML formatting"""
        try:
            message_text = message.text
            instagram_urls = self.extract_instagram_urls(message_text)

            if not instagram_urls:
                await message.reply_text(
                    "❌ <b>No Instagram URL found!</b>\n\n"
                    "Please send a valid Instagram URL.\n"
                    "<b>Example:</b> <code>https://instagram.com/p/xxxxx</code>",
                    parse_mode='html'
                )
                return

            # Process first URL found
            url = instagram_urls[0]
            content_type = self.detect_content_type(url)

            # Send processing message with HTML formatting
            processing_msg = await message.reply_text("🔄 <b>Processing your request...</b>", parse_mode='html')

            if content_type in ['reel', 'mixed']:
                # Try video first
                data = await self.get_reel_data(url)

                if data and data.get('status') == 'success':
                    await self.process_video(data, message, processing_msg)
                    return

                # If video fails and it's mixed, try photo
                if content_type == 'mixed':
                    data = await self.get_photo_data(url)
                    if data and data.get('status') == 'success':
                        await self.process_photos(data, message, processing_msg)
                        return

            elif content_type == 'mixed':
                # Try photo for /p/ URLs
                data = await self.get_photo_data(url)
                if data and data.get('status') == 'success':
                    await self.process_photos(data, message, processing_msg)
                    return

            # If all methods fail
            await processing_msg.edit_text(
                "❌ <b>Failed to fetch content</b>\n\n"
                "<b>Possible reasons:</b>\n"
                "• Post is private\n"
                "• Invalid URL\n"
                "• Temporary server issue\n\n"
                "<i>Please try again later.</i>",
                parse_mode='html'
            )

        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            await message.reply_text(
                "❌ <b>An error occurred while processing your request.</b>\n\n"
                "<i>Please try again later.</i>",
                parse_mode='html'
            )

    async def process_video(self, data: dict, original_message: Message, processing_msg: Message):
        """Process and send video content with HTML formatting"""
        try:
            video_url = data.get('video', '')
            if not video_url:
                await processing_msg.edit_text("❌ <b>No video URL found</b>", parse_mode='html')
                return

            # Generate temporary filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_filename = f"./downloads/reel_{timestamp}.mp4"

            await processing_msg.edit_text("⏬ <b>Downloading video...</b>", parse_mode='html')

            # Download video with progress tracking
            success = await self.download_file_async(video_url, temp_filename, processing_msg)

            if not success:
                await processing_msg.edit_text("❌ <b>Failed to download video</b>", parse_mode='html')
                return

            await processing_msg.edit_text("📤 <b>Uploading video...</b>", parse_mode='html')

            # Check file size
            file_size = os.path.getsize(temp_filename)
            if file_size > 2 * 1024 * 1024 * 1024:  # 2GB limit
                await processing_msg.edit_text(
                    "❌ <b>File too large!</b>\n\n"
                    f"<b>File size:</b> {file_size/1024/1024:.1f}MB\n"
                    "<b>Maximum allowed:</b> 2GB",
                    parse_mode='html'
                )
                os.remove(temp_filename)
                return

            # Send video using Pyrogram's enhanced file handling
            await original_message.reply_video(
                temp_filename,
                caption="🎥 <b>Downloaded by Instagram Downloader Bot</b>\n\n<b>Developer:</b> @authorizationFingerprint",
                parse_mode='html',
                progress=self.progress_callback,
                progress_args=(processing_msg, "upload")
            )

            await processing_msg.delete()

            # Clean up
            if os.path.exists(temp_filename):
                os.remove(temp_filename)

        except FloodWait as e:
            await asyncio.sleep(e.value)
            await self.process_video(data, original_message, processing_msg)
        except Exception as e:
            logger.error(f"Error processing video: {str(e)}")
            await processing_msg.edit_text("❌ <b>Failed to process video</b>", parse_mode='html')

    async def process_photos(self, data: dict, original_message: Message, processing_msg: Message):
        """Process and send photo content with HTML formatting"""
        try:
            images = data.get('images', [])
            if not images:
                await processing_msg.edit_text("❌ <b>No images found</b>", parse_mode='html')
                return

            total_images = len(images)
            await processing_msg.edit_text(f"📸 <b>Downloading {total_images} image(s)...</b>", parse_mode='html')

            for idx, img_data in enumerate(images, 1):
                img_url = img_data.get('image', '')
                if not img_url:
                    continue

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                temp_filename = f"./downloads/photo_{timestamp}_{idx}.jpg"

                await processing_msg.edit_text(
                    f"⏬ <b>Downloading image {idx}/{total_images}...</b>",
                    parse_mode='html'
                )

                success = await self.download_file_async(img_url, temp_filename)

                if success:
                    await original_message.reply_photo(
                        temp_filename,
                        caption=f"📸 <b>Image {idx}/{total_images}</b>\n\n<b>Downloaded by Instagram Downloader Bot</b>\n<b>Developer:</b> @authorizationFingerprint",
                        parse_mode='html'
                    )

                    # Clean up
                    if os.path.exists(temp_filename):
                        os.remove(temp_filename)

                # Small delay between photos
                await asyncio.sleep(1)

            await processing_msg.delete()

        except Exception as e:
            logger.error(f"Error processing photos: {str(e)}")
            await processing_msg.edit_text("❌ <b>Failed to process images</b>", parse_mode='html')

    async def progress_callback(self, current, total, processing_msg, operation):
        """Progress callback for file operations with HTML formatting"""
        try:
            percentage = (current / total) * 100
            await processing_msg.edit_text(
                f"{'📤 <b>Uploading</b>' if operation == 'upload' else '⏬ <b>Downloading</b>'}... {percentage:.1f}%\n"
                f"({current/1024/1024:.1f}MB / {total/1024/1024:.1f}MB)",
                parse_mode='html'
            )
        except:
            pass

    def run(self):
        """Start the bot"""
        logger.info("🚀 Starting Instagram Downloader Bot...")
        self.app.run()

# Bot instance
bot = InstagramDownloaderBot()

if __name__ == "__main__":
    bot.run()
