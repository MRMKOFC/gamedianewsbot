import requests
from bs4 import BeautifulSoup
import telegram
import asyncio
import logging
from urllib.parse import urljoin
from io import BytesIO
import time
import html
import json
import os
from datetime import datetime
from PIL import Image

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger()

# Telegram bot setup (from GitHub Secrets)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
POST_WITHOUT_IMAGE = True
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# Banner Image URL
BANNER_URL = "https://pixvid.org/images/2025/06/23/20250623_152444.png"

# Duplicate prevention
POSTED_FILE = "posted.json"


def load_posted():
    try:
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_posted(posted_set):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(posted_set), f, ensure_ascii=False, indent=2)


bot = telegram.Bot(token=BOT_TOKEN)


def escape_html(text):
    return html.escape(text) if text else text


def is_today(date_str):
    """Check if date_str matches today"""
    try:
        post_date = datetime.strptime(date_str, "%b %d, %Y")
        return post_date.date() == datetime.utcnow().date()
    except Exception:
        return False


async def send_to_telegram(title, summary, art_data=None):
    title = escape_html(title)
    summary = escape_html(summary)
    caption = f"<b>{title}</b> ⚡\n\n<i>{summary}</i>\n\n🍁 | @GamediaNews_acn"
    logger.info(f"Formatted message: {caption}")

    photo_payload = None
    if art_data:
        try:
            # Download banner (foreground)
            resp_banner = requests.get(BANNER_URL, timeout=10)
            resp_banner.raise_for_status()
            banner_fg = Image.open(BytesIO(resp_banner.content)).convert("RGBA")

            # Open news image (background)
            art_img_bg = Image.open(art_data).convert("RGBA")

            # Resize and combine
            final_size = banner_fg.size
            base_image = art_img_bg.resize(final_size, Image.LANCZOS)
            base_image.paste(banner_fg, (0, 0), banner_fg)

            buf = BytesIO()
            base_image.save(buf, format="PNG")
            buf.seek(0)
            photo_payload = buf
        except Exception as e:
            logger.error(f"Image processing failed for '{title}': {e}")
            photo_payload = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if photo_payload:
                await bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=photo_payload,
                    caption=caption,
                    parse_mode="HTML"
                )
            elif POST_WITHOUT_IMAGE:
                await bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=caption,
                    parse_mode="HTML"
                )
            else:
                logger.warning(f"Skipping post for '{title}' as image missing.")
                return

            logger.info(f"Posted: {title}")
            return
        except telegram.error.TimedOut:
            logger.warning(f"Timeout on attempt {attempt} for {title}")
        except telegram.error.BadRequest as e:
            logger.error(f"BadRequest for '{title}': {e}")
            return
        except Exception as e:
            logger.error(f"Error posting '{title}': {e}")

        if attempt < MAX_RETRIES:
            await asyncio.sleep(RETRY_DELAY)

    logger.error(f"Failed to post '{title}' after {MAX_RETRIES} attempts")


async def scrape_gamerant():
    url = "https://gamerant.com/gaming/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    posted_titles = load_posted()

    # Fetch page with retries
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            break
        except Exception as e:
            logger.warning(f"Fetch attempt {attempt} failed: {e}")
            if attempt == MAX_RETRIES:
                logger.error("Failed to fetch GameRant after retries.")
                return
            time.sleep(RETRY_DELAY)

    articles = soup.select("div.display-card.article")[:20]
    if not articles:
        logger.warning("No articles found.")
        return

    for art in articles:
        title_el = art.select_one("h5, h3, [class*='title']")
        title = title_el.text.strip() if title_el else None
        if not title or title in posted_titles:
            continue  # Skip duplicates

        # Try to get publication date
        date_el = art.select_one("span.published, time, .date")
        date_str = date_el.text.strip() if date_el else None

        if date_str and not is_today(date_str):
            logger.info(f"Skipping '{title}' (not today)")
            continue

        sum_el = art.select_one("p.synopsis, p, [class*='excerpt']")
        summary = (sum_el.text.strip()[:150] + "...") if sum_el else "No summary available"

        # Image logic
        image_data = None
        img_el = art.select_one("img[data-src], img[src]")
        if img_el:
            src = img_el.get("data-src") or img_el.get("src")
            img_url = urljoin(url, src)
            try:
                ir = requests.get(img_url, timeout=5)
                ir.raise_for_status()
                image_data = BytesIO(ir.content)
            except Exception as e:
                logger.error(f"Image download failed for '{title}': {e}")

        await send_to_telegram(
            title,
            summary,
            image_data if image_data or not POST_WITHOUT_IMAGE else None
        )
        posted_titles.add(title)

    save_posted(posted_titles)


async def main():
    await scrape_gamerant()


if __name__ == "__main__":
    asyncio.run(main())
