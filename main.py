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
from pyrogram.enums import ParseMode
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

        # TeraBox API configuration
        self.terabox_api_url = "http://smex.unaux.com/tera.php"
        self.terabox_api_key = "tera-m7Tz3nqA9u4ybKaG5x0p"

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
🎬📸 <b>Multi-Platform Downloader Bot</b>

Welcome! Send me any supported URL and I'll download it for you.

<b>What I can download:</b>
🎥 <b>Instagram Reels</b> - Video content (up to 2GB)
📸 <b>Instagram Photos</b> - Single or multiple images
📱 <b>Instagram Posts</b> - Any Instagram post content
📦 <b>TeraBox Files</b> - Videos and files from TeraBox

<b>How to use:</b>
1. Copy a supported link
2. Send it to me  
3. Wait for processing ⏳
4. Get your content! 📥

<b>Supported platforms:</b>
• Instagram (Reels/Photos)
• TeraBox (Files/Videos)

Type /help for more information.

<b>Developer:</b> @medusaXD

<b>Enhanced Features:</b>
✅ Large file support (up to 2GB)
✅ Fast async downloads
✅ Progress tracking
✅ Error recovery
✅ Multi-platform support
        """
        await message.reply_text(welcome_text, parse_mode=ParseMode.HTML)

    async def help_command(self, message: Message):
        """Send help information with HTML formatting"""
        help_text = """
📖 <b>Help - Multi-Platform Downloader Bot</b>

<b>Commands:</b>
• <code>/start</code> - Start the bot
• <code>/help</code> - Show this help message

<b>Supported Content:</b>
🎥 <b>Instagram Reels</b> - Downloaded as MP4 (up to 2GB)
📸 <b>Instagram Photos</b> - Downloaded as JPG (HD Quality)
📦 <b>TeraBox Files</b> - Any file type supported by TeraBox

<b>How to download:</b>
1. Open Instagram or TeraBox app/website
2. Copy the link of any post/file
3. Send the link to this bot
4. Wait for processing (10-60 seconds)
5. Download will be sent automatically

<b>Supported URLs:</b>

<b>Instagram:</b>
• <code>https://instagram.com/reel/xxxxx</code>
• <code>https://instagram.com/p/xxxxx</code>
• <code>https://www.instagram.com/reel/xxxxx</code>
• <code>https://www.instagram.com/p/xxxxx</code>

<b>TeraBox:</b>
• <code>https://terabox.com/s/xxxxx</code>
• <code>https://www.terabox.com/s/xxxxx</code>
• <code>https://1024tera.com/s/xxxxx</code>

<b>Features:</b>
🚀 <b>Fast Downloads</b> - Async processing
📊 <b>Progress Tracking</b> - Real-time updates
🔄 <b>Auto Retry</b> - Handles temporary failures
💾 <b>Large Files</b> - Supports files up to 2GB
🛡️ <b>Error Handling</b> - Comprehensive error recovery
🌐 <b>Multi-Platform</b> - Instagram + TeraBox support

<i>Note: Only public content can be downloaded.</i>

<b>Developer:</b> @medusaXD
        """
        await message.reply_text(help_text, parse_mode=ParseMode.HTML)

    def extract_instagram_urls(self, text: str):
        """Extract Instagram URLs from message text"""
        instagram_pattern = r'https?://(?:www\.)?instagram\.com/(?:reel|p)/[a-zA-Z0-9_-]+/?'
        full_urls = re.findall(instagram_pattern, text)
        return full_urls

    def extract_terabox_urls(self, text: str):
        """Extract TeraBox URLs from message text"""
        terabox_pattern = r'https?://(?:www\.)?(terabox\.com|1024tera\.com)/s/[a-zA-Z0-9_-]+/?'
        full_urls = re.findall(terabox_pattern, text)
        # Return full URLs, not just the matched groups
        return [f"https://{match}" if not text[text.find(match)-8:text.find(match)].startswith('http') 
                else text[text.find(f"https://{match}"):text.find(f"https://{match}")+len(f"https://{match}")+20].split()[0]
                for match in full_urls]

    def extract_all_urls(self, text: str):
        """Extract all supported URLs from message text"""
        # More comprehensive URL extraction
        instagram_urls = re.findall(r'https?://(?:www\.)?instagram\.com/(?:reel|p)/[a-zA-Z0-9_-]+/?', text)
        terabox_urls = re.findall(r'https?://(?:www\.)?(terabox\.com|1024tera\.com)/s/[a-zA-Z0-9_-]+/?', text)

        return {
            'instagram': instagram_urls,
            'terabox': terabox_urls
        }

    async def get_terabox_data(self, url: str):
        """Get TeraBox file data using the API"""
        try:
            params = {
                'link': url,
                'key': self.terabox_api_key
            }

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(self.terabox_api_url, params=params) as response:
                    if response.status != 200:
                        logger.error(f"TeraBox API returned status {response.status}")
                        return None

                    data = await response.json()

                    # Check if we have required fields
                    if 'direct_link' in data and data['direct_link']:
                        return {
                            "status": "success",
                            "type": "terabox",
                            "file_name": data.get('file_name', 'terabox_file'),
                            "direct_link": data['direct_link'],
                            "thumb": data.get('thumb', ''),
                            "size": data.get('size', 'Unknown'),
                            "sizebytes": data.get('sizebytes', 0),
                            "dev": "@medusaXD"
                        }
                    else:
                        logger.error(f"TeraBox API response missing direct_link: {data}")
                        return None

        except Exception as e:
            logger.error(f"Error getting TeraBox data: {str(e)}")
            return None

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

    def detect_url_type(self, url: str):
        """Detect the type of URL"""
        if 'instagram.com' in url:
            if '/reel/' in url:
                return 'instagram_reel'
            elif '/p/' in url:
                return 'instagram_mixed'
        elif 'terabox.com' in url or '1024tera.com' in url:
            return 'terabox'
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
                                            parse_mode=ParseMode.HTML
                                        )
                                        last_update = progress
                                    except:
                                        pass

                    return True

        except Exception as e:
            logger.error(f"Error downloading file: {str(e)}")
            return False

    async def handle_message(self, message: Message):
        """Handle incoming messages with multi-platform support"""
        try:
            message_text = message.text
            urls = self.extract_all_urls(message_text)

            # Check for any supported URLs
            all_urls = urls['instagram'] + urls['terabox']

            if not all_urls:
                await message.reply_text(
                    "❌ <b>No supported URL found!</b>\n\n"
                    "Please send a valid URL from:\n"
                    "• <b>Instagram:</b> <code>https://instagram.com/p/xxxxx</code>\n"
                    "• <b>TeraBox:</b> <code>https://terabox.com/s/xxxxx</code>",
                    parse_mode=ParseMode.HTML
                )
                return

            # Process first URL found
            if urls['instagram']:
                url = urls['instagram'][0]
                url_type = self.detect_url_type(url)
                await self.process_instagram_url(url, url_type, message)
            elif urls['terabox']:
                url = urls['terabox'][0]
                await self.process_terabox_url(url, message)

        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            await message.reply_text(
                "❌ <b>An error occurred while processing your request.</b>\n\n"
                "<i>Please try again later.</i>",
                parse_mode=ParseMode.HTML
            )

    async def process_instagram_url(self, url: str, url_type: str, message: Message):
        """Process Instagram URLs"""
        processing_msg = await message.reply_text("🔄 <b>Processing Instagram URL...</b>", parse_mode=ParseMode.HTML)

        if url_type in ['instagram_reel', 'instagram_mixed']:
            # Try video first
            data = await self.get_reel_data(url)

            if data and data.get('status') == 'success':
                await self.process_video(data, message, processing_msg, url)
                return

            # If video fails and it's mixed, try photo
            if url_type == 'instagram_mixed':
                data = await self.get_photo_data(url)
                if data and data.get('status') == 'success':
                    await self.process_photos(data, message, processing_msg)
                    return

        # If all methods fail
        await processing_msg.edit_text(
            "❌ <b>Failed to fetch Instagram content</b>\n\n"
            "<b>Possible reasons:</b>\n"
            "• Post is private\n"
            "• Invalid URL\n"
            "• Temporary server issue\n\n"
            "<i>Please try again later.</i>",
            parse_mode=ParseMode.HTML
        )

    async def process_terabox_url(self, url: str, message: Message):
        """Process TeraBox URLs"""
        processing_msg = await message.reply_text("🔄 <b>Processing TeraBox URL...</b>", parse_mode=ParseMode.HTML)

        data = await self.get_terabox_data(url)

        if data and data.get('status') == 'success':
            await self.process_terabox_file(data, message, processing_msg, url)
        else:
            await processing_msg.edit_text(
                "❌ <b>Failed to fetch TeraBox content</b>\n\n"
                "<b>Possible reasons:</b>\n"
                "• File is private or expired\n"
                "• Invalid URL\n"
                "• Temporary server issue\n\n"
                "<i>Please try again later.</i>",
                parse_mode=ParseMode.HTML
            )

    async def process_terabox_file(self, data: dict, original_message: Message, processing_msg: Message, original_url: str):
        """Process and send TeraBox files"""
        try:
            direct_link = data.get('direct_link', '')
            file_name = data.get('file_name', 'terabox_file')
            file_size = data.get('sizebytes', 0)
            size_text = data.get('size', 'Unknown')

            if not direct_link:
                await processing_msg.edit_text("❌ <b>No download link found</b>", parse_mode=ParseMode.HTML)
                return

            # Generate temporary filename with proper extension
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_extension = os.path.splitext(file_name)[1] if '.' in file_name else '.mp4'
            temp_filename = f"./downloads/terabox_{timestamp}{file_extension}"

            await processing_msg.edit_text(f"⏬ <b>Downloading TeraBox file...</b>\n📁 <b>File:</b> {file_name}\n📊 <b>Size:</b> {size_text}", parse_mode=ParseMode.HTML)

            # Download file with progress tracking
            success = await self.download_file_async(direct_link, temp_filename, processing_msg)

            if not success:
                await processing_msg.edit_text("❌ <b>Failed to download TeraBox file</b>", parse_mode=ParseMode.HTML)
                return

            await processing_msg.edit_text("📤 <b>Uploading file...</b>", parse_mode=ParseMode.HTML)

            # Check file size
            actual_file_size = os.path.getsize(temp_filename)
            if actual_file_size > 2 * 1024 * 1024 * 1024:  # 2GB limit
                await processing_msg.edit_text(
                    "❌ <b>File too large!</b>\n\n"
                    f"<b>File size:</b> {actual_file_size/1024/1024:.1f}MB\n"
                    "<b>Maximum allowed:</b> 2GB",
                    parse_mode=ParseMode.HTML
                )
                os.remove(temp_filename)
                return

            # Determine if it's a video or document
            video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']
            is_video = any(file_extension.lower().endswith(ext) for ext in video_extensions)

            if is_video:
                # Send as video
                await original_message.reply_video(
                    temp_filename,
                    caption=f"🔗 Original URL: {original_url}",
                    progress=self.progress_callback,
                    progress_args=(processing_msg, "upload")
                )
            else:
                # Send as document
                await original_message.reply_document(
                    temp_filename,
                    caption=f"🔗 Original URL: {original_url}",
                    progress=self.progress_callback,
                    progress_args=(processing_msg, "upload")
                )

            await processing_msg.delete()

            # Clean up
            if os.path.exists(temp_filename):
                os.remove(temp_filename)

        except FloodWait as e:
            await asyncio.sleep(e.value)
            await self.process_terabox_file(data, original_message, processing_msg, original_url)
        except Exception as e:
            logger.error(f"Error processing TeraBox file: {str(e)}")
            await processing_msg.edit_text("❌ <b>Failed to process TeraBox file</b>", parse_mode=ParseMode.HTML)

    async def process_video(self, data: dict, original_message: Message, processing_msg: Message, original_url: str):
        """Process and send video content with simplified caption"""
        try:
            video_url = data.get('video', '')
            if not video_url:
                await processing_msg.edit_text("❌ <b>No video URL found</b>", parse_mode=ParseMode.HTML)
                return

            # Generate temporary filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_filename = f"./downloads/reel_{timestamp}.mp4"

            await processing_msg.edit_text("⏬ <b>Downloading video...</b>", parse_mode=ParseMode.HTML)

            # Download video with progress tracking
            success = await self.download_file_async(video_url, temp_filename, processing_msg)

            if not success:
                await processing_msg.edit_text("❌ <b>Failed to download video</b>", parse_mode=ParseMode.HTML)
                return

            await processing_msg.edit_text("📤 <b>Uploading video...</b>", parse_mode=ParseMode.HTML)

            # Check file size
            file_size = os.path.getsize(temp_filename)
            if file_size > 2 * 1024 * 1024 * 1024:  # 2GB limit
                await processing_msg.edit_text(
                    "❌ <b>File too large!</b>\n\n"
                    f"<b>File size:</b> {file_size/1024/1024:.1f}MB\n"
                    "<b>Maximum allowed:</b> 2GB",
                    parse_mode=ParseMode.HTML
                )
                os.remove(temp_filename)
                return

            # Send video with simplified caption (only original URL)
            await original_message.reply_video(
                temp_filename,
                caption=f"🔗 Original URL: {original_url}",
                progress=self.progress_callback,
                progress_args=(processing_msg, "upload")
            )

            await processing_msg.delete()

            # Clean up
            if os.path.exists(temp_filename):
                os.remove(temp_filename)

        except FloodWait as e:
            await asyncio.sleep(e.value)
            await self.process_video(data, original_message, processing_msg, original_url)
        except Exception as e:
            logger.error(f"Error processing video: {str(e)}")
            await processing_msg.edit_text("❌ <b>Failed to process video</b>", parse_mode=ParseMode.HTML)

    async def process_photos(self, data: dict, original_message: Message, processing_msg: Message):
        """Process and send photo content with HTML formatting"""
        try:
            images = data.get('images', [])
            if not images:
                await processing_msg.edit_text("❌ <b>No images found</b>", parse_mode=ParseMode.HTML)
                return

            total_images = len(images)
            await processing_msg.edit_text(f"📸 <b>Downloading {total_images} image(s)...</b>", parse_mode=ParseMode.HTML)

            for idx, img_data in enumerate(images, 1):
                img_url = img_data.get('image', '')
                if not img_url:
                    continue

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                temp_filename = f"./downloads/photo_{timestamp}_{idx}.jpg"

                await processing_msg.edit_text(
                    f"⏬ <b>Downloading image {idx}/{total_images}...</b>",
                    parse_mode=ParseMode.HTML
                )

                success = await self.download_file_async(img_url, temp_filename)

                if success:
                    await original_message.reply_photo(
                        temp_filename,
                        caption=f"📸 <b>Image {idx}/{total_images}</b>\n\n<b>Downloaded by Multi-Platform Bot</b>\n<b>Developer:</b> @medusaXD",
                        parse_mode=ParseMode.HTML
                    )

                    # Clean up
                    if os.path.exists(temp_filename):
                        os.remove(temp_filename)

                # Small delay between photos
                await asyncio.sleep(1)

            await processing_msg.delete()

        except Exception as e:
            logger.error(f"Error processing photos: {str(e)}")
            await processing_msg.edit_text("❌ <b>Failed to process images</b>", parse_mode=ParseMode.HTML)

    async def progress_callback(self, current, total, processing_msg, operation):
        """Progress callback for file operations with HTML formatting"""
        try:
            percentage = (current / total) * 100
            await processing_msg.edit_text(
                f"{'📤 <b>Uploading</b>' if operation == 'upload' else '⏬ <b>Downloading</b>'}... {percentage:.1f}%\n"
                f"({current/1024/1024:.1f}MB / {total/1024/1024:.1f}MB)",
                parse_mode=ParseMode.HTML
            )
        except:
            pass

    def run(self):
        """Start the bot"""
        logger.info("🚀 Starting Multi-Platform Downloader Bot...")
        self.app.run()

# Bot instance
bot = InstagramDownloaderBot()

if __name__ == "__main__":
    bot.run()
