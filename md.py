from __future__ import annotations
import logging
import os
import sys
import time
import re
import uuid
import threading
import unicodedata
import json
import base64
import zipfile
import shutil
import io
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests
import questionary
from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.layout import Layout
from rich.live import Live
from rich.align import Align
from prompt_toolkit.input import create_input
from prompt_toolkit.keys import Keys
from tqdm import tqdm
from PIL import Image as PILImage
try:
    from curl_cffi import requests as requests_cf
except ImportError:
    requests_cf = None
try:
    import zhconv
except ImportError:
    zhconv = None

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename="logs/debug.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)


API = "https://api.mangadex.org"
BAOZIMH_BASE = "https://www.baozimh.com"
HAPPYMH_BASE = "https://m.happymh.com"
LIBRARY_FILE = "library.json"
console = Console()

class TerminalImage:
    def __init__(self, pil_img: PILImage.Image, width: Optional[int] = None):
        self.img = pil_img
        self.width = width

    def __rich_console__(self, console, options):
        max_width = self.width or options.max_width or console.width
        max_width = max(10, max_width - 2)
        w, h = self.img.size
        ratio = max_width / w
        new_w = int(w * ratio)
        new_h = int(h * ratio)
        if new_h % 2 != 0:
            new_h += 1
        try:
            resample = PILImage.Resampling.LANCZOS
        except AttributeError:
            resample = PILImage.BICUBIC
        img = self.img.resize((new_w, new_h), resample=resample)
        img = img.convert("RGB")
        for y in range(0, new_h - 1, 2):
            line = Text()
            for x in range(new_w):
                r1, g1, b1 = img.getpixel((x, y))
                r2, g2, b2 = img.getpixel((x, y + 1))
                color1 = f"rgb({r1},{g1},{b1})"
                color2 = f"rgb({r2},{g2},{b2})"
                line.append("▀", style=f"{color1} on {color2}")
            yield line

COVER_CACHE = {}

def fetch_cover_image(manga_id: str, filename: str) -> Optional[PILImage.Image]:
    if not filename:
        return None
    cache_key = f"{manga_id}/{filename}"
    if cache_key in COVER_CACHE:
        return COVER_CACHE[cache_key]
    
                                                          
    if filename.startswith("http"):
        url = filename
    else:
        url = get_cover_url(manga_id, filename, size=256)
        
    try:
        r = requests.get(url, timeout=5)

        r.raise_for_status()
        img = PILImage.open(io.BytesIO(r.content))
        COVER_CACHE[cache_key] = img
        return img
    except Exception as e:
        logging.error(f"Error: {e}")
        return None

def api_get(path: str, params: dict | None = None) -> dict:
    url = API.rstrip("/") + "/" + path.lstrip("/")
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

                         
def fetch_baozimh_response(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return r
    except Exception as e:
        logging.error(f"Error: {e}")
        return None

def fetch_baozimh_html(url: str) -> Optional[str]:
    r = fetch_baozimh_response(url)
    return r.text if r else None

HAPPYMH_SESSION = None
SESSION_LOCK = threading.Lock()

def get_happymh_session():
    global HAPPYMH_SESSION
    with SESSION_LOCK:
        if HAPPYMH_SESSION is None:
            if requests_cf:
                HAPPYMH_SESSION = requests_cf.Session()
                cookie_file = Path("happymh_cookies.json")
                if cookie_file.exists():
                    try:
                        with open(cookie_file, "r") as f:
                            HAPPYMH_SESSION.cookies.update(json.load(f))
                    except: pass
            else:
                HAPPYMH_SESSION = requests.Session()
    return HAPPYMH_SESSION

def fetch_happymh_response(url: str, referer: Optional[str] = None):
    session = get_happymh_session()
    ref = referer or HAPPYMH_BASE
    
    # Use curl_cffi for Cloudflare bypass if available
    if requests_cf and isinstance(session, requests_cf.Session):
        try:
            r = session.get(
                url, 
                impersonate="chrome120", 
                timeout=20, 
                headers={
                    "Referer": ref,
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Sec-Ch-Ua": '"Chromium";v="120", "Google Chrome";v="120", "Not-A.Brand";v="99"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "same-origin",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1"
                }
            )
            r.raise_for_status()
            return r
        except Exception as e:
            logging.error(f"Happymh CF Error: {e}")
            if hasattr(e, 'response') and e.response is not None and e.response.status_code == 403:
                # If 403, it's likely Cloudflare. 
                # We could try nodriver here, but it's slow.
                pass
            
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": ref,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
    }
    try:
        r = session.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        return r
    except Exception as e:
        logging.error(f"Happymh Standard Error: {e}")
        return None

def fetch_happymh_html(url: str, referer: Optional[str] = None) -> Optional[str]:
    # Check if user provided a research file first (Manual Override)
    research_file = Path("baozimh_research/happymh.txt")
    if research_file.exists():
        try:
            with open(research_file, "r", encoding="utf-8") as f:
                content = f.read()
                if content and len(content) > 100:
                    logging.info(f"Using manual research file content for {url}")
                    return content
        except Exception as e:
            logging.error(f"Error reading research file: {e}")

    r = fetch_happymh_response(url, referer=referer)
    if r:
        return r.text
    
    def extract_html(text):
        if not text: return None
        match = re.search(r'(<html[\s\S]*</html>)', text, re.IGNORECASE)
        if match:
            return match.group(1)
        return text

    # Fallback 1: nodriver (Fastest browser fallback)
    try:
        import subprocess
        logging.info(f"Trying nodriver fallback for {url}")
        res = subprocess.run([sys.executable, "fetch_nodriver.py", url], 
                           capture_output=True, text=True, timeout=60)
        if res.returncode == 0 and res.stdout:
            cleaned = extract_html(res.stdout)
            # Check if nodriver actually bypassed it (human verification might still be there)
            if cleaned and "嗨皮漫画" in cleaned and "人机验证" not in cleaned:
                return cleaned
    except Exception as e:
        logging.error(f"Nodriver fallback failed: {e}")
        
    # Fallback 2: SeleniumBase UC Mode (Most robust)
    try:
        import subprocess
        logging.info(f"Trying SeleniumBase fallback for {url}")
        res = subprocess.run([sys.executable, "fetch_sb.py", url], 
                           capture_output=True, text=True, timeout=120)
        if res.returncode == 0 and res.stdout:
            cleaned = extract_html(res.stdout)
            if cleaned and "嗨皮漫画" in cleaned and "人机验证" not in cleaned:
                return cleaned
    except Exception as e:
        logging.error(f"SeleniumBase fallback failed: {e}")
        
    # Fallback 3: Playwright (Advanced network interception)
    try:
        import subprocess
        logging.info(f"Trying Playwright fallback for {url}")
        res = subprocess.run([sys.executable, "fetch_playwright.py", url], 
                           capture_output=True, text=True, timeout=120)
        if res.returncode == 0 and res.stdout:
            cleaned = extract_html(res.stdout)
            if cleaned and "嗨皮漫画" in cleaned and "人机验证" not in cleaned:
                return cleaned
    except Exception as e:
        logging.error(f"Playwright fallback failed: {e}")
        
    return None

def search_happymh(query: str) -> List[dict]:
    logging.debug(f"Searching Happymh with query: {query}")
    
    # 1. Direct URL Match
    if "happymh.com/manga/" in query:
        manga_id = query.split("/")[-1]
        try:
            html = fetch_happymh_html(query)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                title_tag = soup.select_one(".mg-title") or soup.select_one("h1") or soup.select_one(".MuiTypography-h3") or soup.select_one(".MuiTypography-h4")
                title = title_tag.get_text(strip=True) if title_tag else manga_id
                
                eng = get_english_title(title)
                if eng:
                    title = f"{eng} ({title})"
                
                cover_tag = soup.select_one(".mg-banner img") or soup.select_one(".mg-poster img") or soup.select_one(".MuiCardMedia-root") or soup.select_one("img[src*='poster']")
                cover_url = cover_tag.get("src") or cover_tag.get("data-src") if cover_tag else ""
                
                return [{
                    "id": manga_id,
                    "title": title,
                    "status": "Ongoing",
                    "description": "Loaded from URL (Happymh)",
                    "cover_filename": cover_url,
                    "matched": True,
                    "all_candidates": [],
                    "available_languages": ["zh"],
                    "source": "happymh"
                }]
        except Exception as e:
            logging.error(f"Happymh Direct URL Error: {e}")
            pass
            
        return [{
            "id": manga_id,
            "title": "Direct URL Match (Happymh)",
            "status": "Unknown",
            "description": "Direct URL",
            "cover_filename": "",
            "matched": True,
            "all_candidates": [],
            "available_languages": ["zh"],
            "source": "happymh"
        }]

    # 2. Actual search logic
    # According to user, the search is at /sssearch and doesn't change URL.
    # It likely uses a POST request or a specific query param.
    # Let's try searching via AniList first to get the native title.
    alt_query = get_anilist_chinese_title(query)
    search_q = alt_query if alt_query else query
    
    # Try searching via the known search URL with 'v' or 'q' parameter
    # Some Mui apps use 'v' for search query in some endpoints.
    # But if we don't know the exact endpoint, we can try common ones.
    # For now, we will mainly rely on direct URL or AniList bridge if we can find a way to map it.
    
    # Let's try a simple GET to /sssearch?v=QUERY
    url = f"{HAPPYMH_BASE}/sssearch?v={search_q}"
    html = fetch_happymh_html(url)
    if not html: return []
    
    soup = BeautifulSoup(html, "html.parser")
    results = []
    
    # Looking for comic cards. Based on Mui structure, they might be in a list or grid.
    # Based on general Mui patterns:
    cards = soup.select("a[href^='/manga/'], *[data-href^='/manga/']")
    
    for card in cards:
        try:
            href = card.get("href") or card.get("data-href")
            manga_id = href.split("/")[-1]
            
            title_tag = card.select_one(".MuiTypography-root") or card.select_one("div") or card.select_one(".mg-manga-name")
            title_text = title_tag.get_text(strip=True) if title_tag else "Unknown"
            
            # Filter out duplicates or non-manga links if any
            if not manga_id or manga_id in [r['id'] for r in results]:
                continue
                
            eng_title = get_english_title(title_text)
            display_title = f"{eng_title} ({title_text})" if eng_title else title_text
            
            img_tag = card.find("img")
            cover_url = img_tag.get("src") or img_tag.get("data-src") if img_tag else ""
            
            results.append({
                "id": manga_id,
                "title": display_title,
                "status": "Unknown",
                "description": "Found on Happymh",
                "cover_filename": cover_url,
                "matched": True,
                "all_candidates": [title_text],
                "available_languages": ["zh"],
                "source": "happymh"
            })
        except:
            continue
            
    return results

def fetch_chapters_happymh(manga_id: str) -> List[dict]:
    url = f"{HAPPYMH_BASE}/manga/{manga_id}"
    html = fetch_happymh_html(url)
    
    if not html: return []
    
    soup = BeautifulSoup(html, "html.parser")
    chapters = []
    
    # 1. Try to find all chapter links in the HTML
    # The user says only 9 show by default, but maybe the rest are hidden in the DOM.
    links = soup.select("a[href*='/mangaread/'], *[data-href*='/mangaread/']")
    
    # 2. If we don't have many, look for a JSON blob in script tags.
    # Often Mui/React apps keep the full data in a script.
    if len(links) < 2:
        scripts = soup.find_all("script")
        for s in scripts:
            if not s.string: continue
            # Look for a pattern like {"id":..., "chapters": [...]}
            if '"chapters"' in s.string and '"id"' in s.string:
                try:
                    # Very rough extraction of chapter data
                    # We look for something that looks like an array of objects with id and name
                    matches = re.findall(r'\{"id":(\d+),"name":"([^"]+)"', s.string)
                    if matches:
                        for cid, name in matches:
                            href = f"/mangaread/{manga_id}/{cid}"
                            num_match = re.search(r'(\d+)', name)
                            chap_num = num_match.group(1) if num_match else "0"
                            chapters.append({
                                "id": href,
                                "chapter": chap_num,
                                "title": name,
                                "language": "zh",
                                "groups": [],
                                "publishAt": "",
                                "volume": "",
                                "source": "happymh"
                            })
                        if chapters: return chapters
                except:
                    pass

    seen_ids = set()
    for link in links:
        href = link.get("href") or link.get("data-href")
        if not href or href in seen_ids: continue
        seen_ids.add(href)
        
        # Extract title from the nested span
        title_tag = link.select_one(".MuiListItemText-primary") or link.select_one("span") or link.select_one(".mg-chapter-name")
        text = title_tag.get_text(strip=True) if title_tag else link.get_text(strip=True)
        
        num_match = re.search(r'(\d+)', text)
        chap_num = num_match.group(1) if num_match else "0"
        
        chapters.append({
            "id": href,
            "chapter": chap_num,
            "title": text,
            "language": "zh",
            "groups": [],
            "publishAt": "",
            "volume": "",
            "source": "happymh"
        })
    
    # Sort chapters numerically
    def chap_sort_key(c):
        try:
            return float(c['chapter'])
        except:
            return 0.0
            
    chapters.sort(key=chap_sort_key)
    return chapters

def get_happymh_images(chapter_url_path: str, manga_url: Optional[str] = None) -> List[str]:
    if chapter_url_path.startswith("/"):
        url = f"{HAPPYMH_BASE}{chapter_url_path}"
    else:
        url = chapter_url_path
        
    html = fetch_happymh_html(url, referer=manga_url)
    if not html: return []
    
    images = []
    soup = BeautifulSoup(html, "html.parser")
    
    # --- Method 1: Check for extra captured data from Playwright/SeleniumBase ---
    extra_data_div = soup.find("div", id="extra_captured_data")
    if extra_data_div:
        try:
            captured_raw = extra_data_div.get_text()
            captured = json.loads(json.loads(captured_raw))
            # 1. Images from network
            if captured.get("images"):
                images.extend(captured["images"])
            
            # 2. Images from JS variables
            js_vars = captured.get("js_variables", {})
            for var_name, var_val in js_vars.items():
                if var_name.startswith("canvas_"):
                    images.append("canvas_data:" + var_val)
                else:
                    found_urls = re.findall(r'\"(https?://[^\"]+\.(?:jpg|png|webp|jpeg)[^\"]*)\"', str(var_val))
                    images.extend([u.replace('\\/', '/') for u in found_urls])
            
            # 3. Images from JSON responses
            for resp in captured.get("json_responses", []):
                found_urls = re.findall(r'\"(https?://[^\"]+\.(?:jpg|png|webp|jpeg)[^\"]*)\"', resp["content"])
                images.extend([u.replace('\\/', '/') for u in found_urls])
        except Exception as e:
            logging.error(f"Error parsing captured data: {e}")

    # --- Method 2: Look for JSON data in script tags (Modern Happymh) ---
    scripts = re.findall(r'<script\b[^>]*>([\s\S]*?)<\/script>', html)
    for script_content in scripts:
        if "pages" in script_content and "url" in script_content:
            found = re.findall(r'\"url\":\s*\"(https?://[^\"]+)\"', script_content)
            if found:
                images.extend([u.replace('\\/', '/') for u in found])
        
        if "sc_p" in script_content:
            found = re.findall(r'\"(https?://[^\"]+\.(?:jpg|png|webp|jpeg)[^\"]*)\"', script_content)
            if found:
                images.extend([u.replace('\\/', '/') for u in found])

    # --- Method 3: DOM Selectors (Targeting user-provided structure) ---
    selectors = [
        "img[id^='scan']", # Specific ID pattern user found
        "div.css-1krjvn-imgContainer img", # Specific class user found
        ".mg-content img", 
        ".reader-content img", 
        "div[class*='-imgContainer'] img", 
        "div[id^='scan'] img",
        ".MuiBox-root img",
        "article img"
    ]
    
    for sel in selectors:
        img_tags = soup.select(sel)
        for img in img_tags:
            src = img.get("src") or img.get("data-src") or img.get("data-original")
            if src and (src.startswith("http") or src.startswith("canvas_data:")):
                if any(x in src.lower() for x in ["logo", "favicon", "static/js", "telegram"]):
                    continue
                images.append(src)

    # --- Method 4: Last Resort Raw Regex Scan ---
    patterns = [
        r'https?://ruicdn\.happymh\.com/[^\s\"\'<>)]+\.(?:jpg|png|webp|jpeg)[^\s\"\'<>)]*',
        r'https?://img\.happymh\.com/[^\s\"\'<>)]+\.(?:jpg|png|webp|jpeg)[^\s\"\'<>)]*'
    ]
    for pattern in patterns:
        found = re.findall(pattern, html)
        if found:
            images.extend(found)

    # --- Final Cleanup and Deduplication ---
    seen = set()
    final_images = []
    for img in images:
        if img.startswith("canvas_data:canvas_data:"):
            img = img[12:]
        if img not in seen:
            final_images.append(img)
            seen.add(img)
            
    if final_images:
        logging.info(f"Successfully extracted {len(final_images)} images for {url}")
    else:
        logging.warning(f"No images found for {url} after all extraction methods.")
            
    return final_images

def get_anilist_chinese_title(query: str) -> Optional[str]:
    url = 'https://graphql.anilist.co'
    query_graphql = '''
    query ($search: String) {
      Page(page: 1, perPage: 5) {
        media(search: $search, type: MANGA, sort: SEARCH_MATCH) {
          title {
            romaji
            english
            native
          }
          synonyms
        }
      }
    }
    '''
    variables = {'search': query}
    try:
        r = requests.post(url, json={'query': query_graphql, 'variables': variables}, timeout=5)
        if r.status_code == 200:
            data = r.json()
            media_list = data.get('data', {}).get('Page', {}).get('media', [])
            
            query_lower = query.lower()
            
            for media in media_list:
                titles = media.get('title', {})
                native = titles.get('native')
                if not native:
                    continue
                    
                # Check if query matches any title/synonym
                candidates = [
                    titles.get('english'),
                    titles.get('romaji'),
                    titles.get('native')
                ] + (media.get('synonyms') or [])
                
                matched = False
                for cand in candidates:
                    if cand and query_lower in cand.lower():
                        matched = True
                        break
                
                if matched:
                    return native
                    
    except Exception as e:
        logging.error(f"Error: {e}")
        pass
    return None

def get_anilist_english_title(query: str) -> Optional[str]:
    # Wrapper for AniList GraphQL query
    url = 'https://graphql.anilist.co'
    query_graphql = '''
    query ($search: String) {
      Page(page: 1, perPage: 5) {
        media(search: $search, type: MANGA, sort: SEARCH_MATCH) {
          title {
            english
            romaji
            native
          }
          format
          synonyms
        }
      }
    }
    '''
    variables = {'search': query}
    try:
        r = requests.post(url, json={'query': query_graphql, 'variables': variables}, timeout=3)
        if r.status_code == 200:
            data = r.json()
            media_list = data.get('data', {}).get('Page', {}).get('media', [])
            
            query_lower = query.lower()
            
            for media in media_list:
                fmt = media.get('format')
                if fmt == 'NOVEL':
                    continue
                    
                titles = media.get('title', {})
                eng = titles.get('english') or titles.get('romaji')
                if not eng:
                    continue

                # Verify match against Chinese title (query)
                # Since query is Chinese, we check if 'native' matches or if synonyms match
                # But typically we trust AniList's search for exact Chinese matches.
                # However, let's just take the first valid manga result as before, 
                # but maybe filtered by strictness if needed.
                # For now, just returning the first non-Novel result is better than nothing.
                
                logging.info(f"Found AniList title for '{query}': {eng}")
                return eng
                
    except Exception as e:
        logging.error(f"Error fetching AniList for {query}: {e}")
    return None

def get_english_title(chinese_title: str) -> Optional[str]:
    logging.debug(f"Getting English title for: {chinese_title}")
    
    # 1. Try original query on AniList
    res = get_anilist_english_title(chinese_title)
    if res: return res

    # 2. Try Simplified Chinese if available
    simplified = None
    if zhconv:
        try:
            simplified = zhconv.convert(chinese_title, 'zh-cn')
            if simplified != chinese_title:
                logging.debug(f"Trying Simplified Chinese: {simplified}")
                res = get_anilist_english_title(simplified)
                if res: return res
        except Exception as e:
            logging.error(f"Error converting to Simplified: {e}")

    return None

def search_baozimh(query: str) -> List[dict]:
    logging.debug(f"Searching Baozimh with query: {query}")
                    
    if "baozimh.com" in query:
                                                    
        manga_id = query.split("/")[-1]
        
                                   
        try:
            html = fetch_baozimh_html(query)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                title_tag = soup.select_one(".comics-detail__title") or soup.select_one("h1")
                title = title_tag.get_text(strip=True) if title_tag else manga_id
                
                                                             
                eng = get_english_title(title)
                if eng:
                    title = f"{eng} ({title})"
                
                cover_tag = soup.select_one("amp-img.comics-detail__poster") or soup.select_one(".comics-detail__poster amp-img")
                cover_url = cover_tag.get("src") or cover_tag.get("data-src") if cover_tag else ""
                
                return [{
                    "id": manga_id,
                    "title": title,
                    "status": "Ongoing",
                    "description": "Loaded from URL",
                    "cover_filename": cover_url,
                    "matched": True,
                    "all_candidates": [],
                    "available_languages": ["zh"],
                    "source": "baozimh"
                }]
        except Exception as e:
            logging.error(f"Error: {e}")
            pass
            
        return [{
            "id": manga_id,
            "title": "Direct URL Match",
            "status": "Unknown",
            "description": "Direct URL",
            "cover_filename": "",
            "matched": True,
            "all_candidates": [],
            "available_languages": ["zh"],
            "source": "baozimh"
        }]

                        
    alt_query = get_anilist_chinese_title(query)
    search_q = alt_query if alt_query else query
    
    url = f"{BAOZIMH_BASE}/search?q={search_q}"
    html = fetch_baozimh_html(url)
    if not html: return []
    
    soup = BeautifulSoup(html, "html.parser")
    results = []
    
                                           
    cards = soup.find_all("div", class_="comics-card")
    
                                                 
    for card in cards[:10]:
        try:
            a_tag = card.find("a", class_="comics-card__poster")
            if not a_tag: continue
            href = a_tag.get("href")
                                         
            manga_id = href.split("/")[-1]
            
            img_tag = a_tag.find("amp-img")
            cover_url = img_tag.get("src") if img_tag else ""
            
            title_tag = card.find("h3", class_="comics-card__title")
            title_text = title_tag.get_text(strip=True) if title_tag else "Unknown"
            
                                        
            eng_title = get_english_title(title_text)
            display_title = f"{eng_title} ({title_text})" if eng_title else title_text
            
            tags_div = card.find("div", class_="tags")
            status_text = tags_div.get_text(strip=True) if tags_div else ""
            
            results.append({
                "id": manga_id,
                "title": display_title,
                "status": status_text,
                "description": "No description available (Baozimh)",
                "cover_filename": cover_url,               
                "matched": True,
                "all_candidates": [title_text],
                "available_languages": ["zh"],
                "source": "baozimh"
            })
        except Exception as e:
            logging.error(f"Error: {e}")
            continue
    
    # Filter results if we used an AniList translation to be more precise
    if alt_query and results:
        filtered = []
        for r in results:
            title_check = r['title']
            query_check = alt_query
            if zhconv:
                try:
                    title_check = zhconv.convert(title_check, 'zh-cn')
                    query_check = zhconv.convert(query_check, 'zh-cn')
                except:
                    pass
            
            if query_check in title_check:
                filtered.append(r)
        
        if filtered:
            results = filtered
            
    return results

def fetch_chapters_baozimh(manga_id: str) -> List[dict]:
                                                   
    if manga_id.startswith("/comic/"):
        url = f"{BAOZIMH_BASE}{manga_id}"
    else:
        url = f"{BAOZIMH_BASE}/comic/{manga_id}"
        
    html = fetch_baozimh_html(url)
    if not html: return []
    
    soup = BeautifulSoup(html, "html.parser")
    chapters = []
    
    seen_ids = set()
    
                                   
    links = soup.select(".comics-chapters .comics-chapters__item")
    if not links:
                           
        links = soup.select("div#chapters_box a")
        
    for link in links:
        href = link.get("href")
        if not href or href in seen_ids: continue
        seen_ids.add(href)
        
                                   
        text = link.get_text(strip=True)
        
                                         
                                  
        num_match = re.search(r'\d+', text)
        chap_num = num_match.group(0) if num_match else "0"
        
        chapters.append({
            "id": href,                             
            "chapter": chap_num,                                   
            "title": text,                     
            "volume": "",
            "language": "zh",
            "publishAt": "",
            "groups": [],
            "attributes": {},
            "source": "baozimh"
        })
    
    return chapters

def get_baozimh_images(chapter_url_path: str) -> List[str]:
                                         
    if chapter_url_path.startswith("/"):
        base_url = f"{BAOZIMH_BASE}{chapter_url_path}"
    else:
        base_url = chapter_url_path
        
    r = fetch_baozimh_response(base_url)
    if not r: return []
    
    soup = BeautifulSoup(r.text, "html.parser")
    images = []
    seen = set()
    
                                              
                                                                   
    targets = soup.select(".comic-contain__item")
    
                                                                                         
    if not targets:
        container = soup.select_one(".comic-contain")
        if container:
            targets = container.select("amp-img, img")
            
                                                                               
    if not targets:
        for img in soup.find_all("amp-img"):
            if img.find_parent(class_="recommend--item"):
                continue
            targets.append(img)

                               
    for img in targets:
        src = img.get("src") or img.get("data-src")
        if src and src not in seen:
            images.append(src)
            seen.add(src)
            
    return images

                             

def _normalize_text(s: Optional[str]) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _all_title_candidates(attrs: dict) -> List[str]:
    titles = set()
    if not attrs:
        return []
    title_map = attrs.get("title") or {}
    for v in title_map.values():
        if v:
            titles.add(str(v))
    alt = attrs.get("altTitles") or []
    for entry in alt:
        if isinstance(entry, dict):
            for v in entry.values():
                if v:
                    titles.add(str(v))
        elif isinstance(entry, str):
            titles.add(entry)
    extra = attrs.get("otherNames") or attrs.get("other_titles")
    if extra and isinstance(extra, (list, tuple)):
        for v in extra:
            if v:
                titles.add(str(v))
    return list(titles)

def _matches_query(query_norm: str, title_norm: str) -> bool:
    if not query_norm or not title_norm:
        return False
    if query_norm in title_norm:
        return True
    q_tokens = query_norm.split()
    t_tokens = set(title_norm.split())
    if all(token in t_tokens for token in q_tokens):
        return True
    return False

def search_manga(title: str, limit: int = 100) -> List[dict]:
    title = (title or "").strip()
    if not title:
        return []
    query_norm = _normalize_text(title)
    collected_raw = []
    
                   
    url_match = re.search(r"mangadex\.org/title/([a-fA-F0-9\-]+)", title)
    if url_match:
        manga_id = url_match.group(1)
        try:
            resp = api_get(f"/manga/{manga_id}", params={"includes[]": ["cover_art"]})
            data = resp.get("data")
            if data:
                collected_raw.append(data)
        except Exception as e:
            logging.error(f"Error: {e}")

    if not collected_raw:
        try:
            params = {
                "title": title, 
                "limit": min(limit, 100),
                "includes[]": ["cover_art"]
            }
            resp = api_get("/manga", params=params)
            collected_raw.extend(resp.get("data", []))
        except Exception:
            collected_raw = []
    if not collected_raw or len(collected_raw) < 5:
        tokens = [t for t in re.split(r"[^A-Za-z0-9]+", title) if t]
        tries = []
        if len(tokens) > 1:
            tries.append(" ".join(tokens[:6]))
            tries.extend(tokens[:4])
            tries.extend(tokens[-2:])
        else:
            tries.append(title)
        for q in tries:
            try:
                params = {
                    "title": q, 
                    "limit": 100,
                    "includes[]": ["cover_art"]
                }
                resp = api_get("/manga", params=params)
                for r in resp.get("data", []):
                    if r not in collected_raw:
                        collected_raw.append(r)
            except Exception:
                continue
    if not collected_raw:
        try:
            params = {
                "limit": 100, 
                "order[followedCount]": "desc",
                "includes[]": ["cover_art"]
            }
            resp = api_get("/manga", params=params)
            collected_raw.extend(resp.get("data", []))
        except Exception:
            pass
    results = []
    seen_ids = set()
    for item in collected_raw:
        attrs = item.get("attributes", {}) or {}
        manga_id = item.get("id")
        if not manga_id or manga_id in seen_ids:
            continue
        cover_filename = None
        for rel in item.get("relationships", []) or []:
            if rel.get("type") == "cover_art":
                rel_attrs = rel.get("attributes") or {}
                cover_filename = rel_attrs.get("fileName")
                break
        candidates = _all_title_candidates(attrs)
        matched = False
        for cand in candidates:
            cand_norm = _normalize_text(cand)
            if _matches_query(query_norm, cand_norm):
                matched = True
                break
        display_title_map = attrs.get("title") or {}
        display_title = display_title_map.get("en") or next(iter(display_title_map.values()), None) or (candidates[0] if candidates else "Unknown")
        desc_dict = attrs.get("description") or {}
        description = desc_dict.get("en") or next(iter(desc_dict.values()), "") if desc_dict else "No description available."
        results.append({
            "id": manga_id,
            "title": display_title,
            "status": attrs.get("status"),
            "description": description,
            "cover_filename": cover_filename,
            "originalTitle": display_title_map,
            "matched": matched,
            "all_candidates": candidates,
            "available_languages": attrs.get("availableTranslatedLanguages", []),
            "source": "mangadex"
        })
        seen_ids.add(manga_id)
    results.sort(key=lambda r: (0 if r.get("matched") else 1, (r.get("title") or "").lower()))
    return results[:limit]

def get_cover_url(manga_id: str, filename: str, size: Optional[int] = None) -> str:
    base = f"https://uploads.mangadex.org/covers/{manga_id}/{filename}"
    if size in [256, 512]:
        return f"{base}.{size}.jpg"
    return base

def render_cover_to_terminal(manga_id: str, filename: str):
    if not filename:
        console.print("[yellow]No cover available for this manga.[/yellow]")
        return
    
    if filename.startswith("http"):
        url = filename
    else:
        url = get_cover_url(manga_id, filename, size=256)
        
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        img_data = io.BytesIO(r.content)
        img = PILImage.open(img_data)
        console.print(TerminalImage(img))
    except Exception as e:
        console.print(f"[red]Failed to render cover: {e}[/red]")

def fetch_chapters_for_manga(manga_id: str, langs: Optional[List[str]] = None) -> List[dict]:
    chapters = []
    limit = 100
    offset = 0
    while True:
        params = {
            "manga": manga_id,
            "limit": limit,
            "offset": offset,
            "order[chapter]": "asc",
            "includes[]": "scanlation_group"
        }
        if langs:
            params["translatedLanguage[]"] = langs
        try:
            resp = api_get("/chapter", params=params)
        except Exception as e:
            console.print(f"[red]Failed to fetch chapters page: {e}[/red]")
            break
        page_results = resp.get("data", [])
        if not page_results:
            break
        for r in page_results:
            attrs = r.get("attributes", {}) or {}
            chap_id = r.get("id")
            chap_num = attrs.get("chapter") or ""
            chap_title = attrs.get("title") or ""
            vol = attrs.get("volume") or ""
            lang_code = attrs.get("translatedLanguage") or ""
            groups = []
            for rel in r.get("relationships", []) or []:
                if rel.get("type") == "scanlation_group":
                    name = None
                    rel_attrs = rel.get("attributes") or {}
                    name = rel_attrs.get("name") or rel.get("id")
                    if name:
                        groups.append(name)
            groups = list(dict.fromkeys([g for g in groups if g]))
            chapters.append({
                "id": chap_id,
                "chapter": chap_num,
                "title": chap_title,
                "volume": vol,
                "language": lang_code,
                "publishAt": attrs.get("publishAt"),
                "groups": groups,
                "attributes": attrs
            })
        offset += len(page_results)
        if len(page_results) < limit:
            break
        if offset >= 5000:
            break
    return chapters

def get_chapter_info(chapter_id: str) -> dict:
    data = api_get(f"/chapter/{chapter_id}")
    return data.get("data") or {}

def get_at_home_base(chapter_id: str) -> Optional[dict]:
    data = api_get(f"/at-home/server/{chapter_id}")
    return data

def craft_image_urls(base_url: str, chapter_attrs: dict, use_data_saver: bool = True) -> List[str]:
    hash_ = chapter_attrs.get("hash")
    if use_data_saver:
        files = chapter_attrs.get("dataSaver") or []
        mode = "data-saver"
    else:
        files = chapter_attrs.get("data") or []
        mode = "data"
    if not hash_ or not files:
        return []
    base = base_url.rstrip("/")
    return [f"{base}/{mode}/{hash_}/{fname}" for fname in files]

def choose_from_list(prompt: str, choices: List[str]) -> Optional[str]:
    if not choices:
        console.print("[red]No choices available.[/red]")
        return None
    return questionary.select(prompt, choices=choices).ask()

def download_images(urls: List[str], out_dir: str, source: str = "mangadex", referer: Optional[str] = None):
    print(f"\nTarget folder is {out_dir}")
    out_dir = Path(out_dir)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        console.print(f"[red]Failed to create directory: {e}[/red]")
        return
    
    # Use curl_cffi for happymh images as they often block standard requests
    session = None
    if source == "happymh":
        session = get_happymh_session()
    else:
        session = requests.Session()
        
    for i, url in enumerate(urls, 1):
        ext = ".jpg"
        if "." in url:
            parts = url.split(".")
            potential_ext = parts[-1].split("?")[0]
            if len(potential_ext) <= 4:
                ext = f".{potential_ext}"
        fname = f"{i:03d}{ext}"
        dest = out_dir / fname
        if dest.exists():
            continue
            
        if url.startswith("canvas_data:"):
            try:
                import base64
                header, encoded = url.split(",", 1)
                data = base64.b64decode(encoded)
                with open(dest, "wb") as f:
                    f.write(data)
                console.print(f"[green]Saved canvas image {i}/{len(urls)}[/green]")
            except Exception as e:
                console.print(f"[red]Failed to save canvas image: {e}[/red]")
            continue

        try:
            get_kwargs = {"stream": True, "timeout": 30}
            if source == "happymh" and requests_cf:
                get_kwargs["impersonate"] = "chrome120"
                # Use provided referer (chapter URL) or fallback to base
                get_kwargs["headers"] = {"Referer": referer or HAPPYMH_BASE}
            
            with session.get(url, **get_kwargs) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0) or 0)
                desc = f"Page {i}/{len(urls)}"
                with tqdm(total=total, unit="B", unit_scale=True, desc=desc, leave=False, dynamic_ncols=True) as t:
                    with open(dest, "wb") as fh:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                fh.write(chunk)
                                t.update(len(chunk))
        except Exception as e:
            console.print(f"[red]Failed to download {url}: {e}[/red]")
    console.print(f"[bold green]Finished downloading {len(urls)} images to {out_dir}[/bold green]")

def truncate_title(title: str, max_len: int = 20) -> str:
    if len(title) > max_len:
        return title[:max_len-3] + "..."
    return title

def make_layout(selected_manga: Optional[dict] = None, manga_list: List[dict] = [], cursor: int = 0) -> Layout:
    layout = Layout()
    layout.split_row(
        Layout(name="left", ratio=1),
        Layout(name="right", ratio=3)
    )
    table = Table(show_header=True, header_style="bold magenta", expand=True, box=None)
    table.add_column("Search Results", no_wrap=True)
    for i, m in enumerate(manga_list):
        title = truncate_title(m['title'], 20)
        style = "reverse" if i == cursor else ""
        match_mark = "✓" if m.get("matched") else " "
        table.add_row(f"{match_mark} {title}", style=style)
    layout["left"].update(Panel(table, title="Manga", border_style="cyan"))
    if selected_manga:
        m_id = selected_manga["id"]
        fname = selected_manga["cover_filename"]
        img = fetch_cover_image(m_id, fname)
        content = []
        if img:
            content.append(Align.center(TerminalImage(img, width=60)))
        else:
            content.append(Align.center("[yellow]No cover available[/yellow]"))
        content.append(Text("\n"))
        content.append(Panel(selected_manga.get("description", "No description"), title="Description", border_style="green"))
        layout["right"].update(Panel(
            Align.center(Columns(content, align="center")),
            title=f"{selected_manga['title']} ({selected_manga['status']})",
            border_style="bold cyan"
        ))
    else:
        layout["right"].update(Panel(Align.center("\n\n[bold]Select a manga to see details[/bold]"), border_style="cyan"))
    return layout

def custom_manga_selector(results: List[dict]) -> Optional[dict]:
    if not results: return None
    cursor = 0
    done = False
    selected = None
    with Live(make_layout(results[cursor], results, cursor), screen=True, auto_refresh=False) as live:
        input_stream = create_input()
        def handle_key():
            nonlocal cursor, done, selected
            for key_press in input_stream.read_keys():
                if key_press.key == Keys.Up or key_press.key == "k":
                    cursor = (cursor - 1) % len(results)
                elif key_press.key == Keys.Down or key_press.key == "j":
                    cursor = (cursor + 1) % len(results)
                elif key_press.key == Keys.Enter:
                    selected = results[cursor]
                    done = True
                elif key_press.key == Keys.Escape or key_press.key == "q":
                    done = True
                live.update(make_layout(results[cursor], results, cursor), refresh=True)
        with input_stream.raw_mode():
            while not done:
                handle_key()
                time.sleep(0.01)
    return selected

def load_library() -> dict:
    if os.path.exists(LIBRARY_FILE):
        try:
            with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error: {e}")
            pass
    return {}

def save_library(library: dict):
    try:
        with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=4)
    except Exception as e:
        console.print(f"[red]Failed to save library: {e}[/red]")

def main():
    if os.name == 'nt':
        os.system('mode con: cols=150 lines=45')
    os.system('cls' if os.name == 'nt' else 'clear')
    console.print("[bold green]MangaDex TUI — Grid Layout Mode[/bold green]")
    
                          
    current_source = "MangaDex"
    
    while True:
        action = questionary.select(
            f"Choose action (Current: {current_source})", 
            choices=["Search manga", "Library", "Change Source", "Exit"]
        ).ask()
        
        if action == "Exit" or action is None:
            console.print("Goodbye.")
            sys.exit(0)
            
        if action == "Change Source":
            new_source = questionary.select(
                "Select Source",
                choices=["MangaDex", "Baozimh", "Happymh"]
            ).ask()
            if new_source:
                current_source = new_source
            continue
            
        selected = None

        if action == "Library":
            lib = load_library()
            if not lib:
                console.print("[yellow]Library is empty.[/yellow]")
                continue
            
            items = sorted(lib.items(), key=lambda x: x[1].get('title', '').lower())
            choices = []
            for mid, data in items:
                t = data.get('title', 'Unknown')
                s = data.get('source', 'MangaDex')
                choices.append(questionary.Choice(f"{t} [{s}]", value=(mid, data)))
            choices.append(questionary.Choice("Back", value="BACK_TO_MENU"))
            
            selection = questionary.select("Select from Library:", choices=choices).ask()
            if not selection or selection == "BACK_TO_MENU":
                continue
                
            if not isinstance(selection, tuple):
                continue
                
            mid, data = selection
            
            # Priority 1: Check the stored source field
            stored_source = data.get('source', '').lower()
            if stored_source == 'happymh':
                current_source = "Happymh"
            elif stored_source == 'baozimh':
                current_source = "Baozimh"
            elif stored_source == 'rawkuma':
                current_source = "Rawkuma"
            elif stored_source == 'mangadex':
                current_source = "MangaDex"
            else:
                # Priority 2: Heuristics for older library entries
                try:
                    uuid.UUID(mid)
                    current_source = "MangaDex"
                except ValueError:
                    if "/comic/" in mid or "baozimh" in str(data.get("cover_url", "")):
                        current_source = "Baozimh"
                    elif "happymh.com" in str(data.get("cover_url", "")) or "manga/" in mid:
                        current_source = "Happymh"
                    else:
                        current_source = "MangaDex" # Default fallback
            
            needs_update = False
            if data.get('source') != current_source.lower():
                data['source'] = current_source.lower()
                needs_update = True
                
                                                         
                current_title = data.get('title', '')
                                                                                        
                                                 
                if not current_title or (current_title and "(" not in current_title):
                    console.print("[cyan]Checking for English title...[/cyan]")
                    eng = get_english_title(current_title)
                    if eng:
                        new_title = f"{eng} ({current_title})"
                        data['title'] = new_title
                        needs_update = True
                        console.print(f"[green]Updated title: {new_title}[/green]")
                    elif not current_title:
                                                             
                        data['title'] = "Unknown Title"
                        needs_update = True

            if needs_update:
                lib[mid] = data
                save_library(lib)
                
            selected = {
                "id": mid,
                "title": data.get('title'),
                "status": "In Library",
                "description": "Loaded from Library",
                "cover_filename": data.get('cover_url'),
                "available_languages": [],
                "source": current_source
            }

        elif action == "Search manga":
            query = questionary.text("Enter manga title to search:").ask()
            if not query:
                continue
            os.system('cls' if os.name == 'nt' else 'clear')
            console.print(f"Searching for: [bold]{query}[/bold] on {current_source} ...")
            
            try:
                if current_source == "MangaDex":
                    results = search_manga(query, limit=40)
                elif current_source == "Baozimh":
                    results = search_baozimh(query)
                elif current_source == "Happymh":
                    results = search_happymh(query)
                    if not results:
                        console.print("[yellow]Happymh search returned no results. This might be due to Cloudflare protection.[/yellow]")
                        console.print("[cyan]Tip: Try pasting the direct manga URL instead of searching.[/cyan]")
                        console.print("[cyan]Tip: You can also place your browser cookies in 'happymh_cookies.json'.[/cyan]")
            except Exception as e:
                console.print(f"[red]Search failed: {e}[/red]")
                continue
                
            if not results:
                console.print("[yellow]No results.[/yellow]")
                continue
                
            selected = custom_manga_selector(results)
            
        if not selected:
            continue
            
        os.system('cls' if os.name == 'nt' else 'clear')
        console.print(Panel(f"Selected: [bold cyan]{selected['title']}[/bold cyan]", expand=False))
        is_correct = questionary.confirm("Proceed with this manga?", default=True).ask()
        if not is_correct:
            continue
            
        manga_id = selected["id"]
        console.print(f"Confirmed: [cyan]{selected['title']}[/cyan]")
        
                                 
        lib = load_library()
        is_in_lib = manga_id in lib
        
        menu_choices = ["View Chapters / Download"]
        if is_in_lib:
            menu_choices.append("Remove from Library")
        else:
            menu_choices.append("Add to Library")
        menu_choices.append("Back to Main Menu")
        
        user_action = questionary.select("Action:", choices=menu_choices).ask()
        
        if user_action == "Back to Main Menu":
            continue
            
        if user_action == "Add to Library":
            lib[manga_id] = {
                "title": selected['title'],
                "added_at": time.time(),
                "last_chapter": "",
                "has_update": False,
                "source": current_source,
                "cover_url": selected.get('cover_filename')
            }
            save_library(lib)
            console.print(f"[green]Added '{selected['title']}' to library![/green]")
            
        elif user_action == "Remove from Library":
            if manga_id in lib:
                del lib[manga_id]
                save_library(lib)
                console.print(f"[yellow]Removed '{selected['title']}' from library.[/yellow]")

                                                    
        selected_langs = None
        if current_source == "MangaDex":
            available_langs = sorted([str(l) for l in selected.get("available_languages", []) if l])
            if not available_langs:
                console.print("[yellow]No translated chapters found for this manga according to MangaDex.[/yellow]")
                is_continue = questionary.confirm("Try fetching chapters anyway?", default=False).ask()
                if not is_continue:
                    continue
            else:
                selected_langs = questionary.checkbox(
                    "Select languages for chapters (leave empty for all available):",
                    choices=available_langs
                ).ask()
        else:
                                     
            console.print("[dim]Source is Baozimh (Chinese only)[/dim]")
        
        lang_params = selected_langs if selected_langs else None
        console.print("Fetching chapters (this may take a moment for large series)...")
        
        try:
            if current_source == "MangaDex":
                chapters = fetch_chapters_for_manga(manga_id, langs=lang_params)
            elif current_source == "Baozimh":
                chapters = fetch_chapters_baozimh(manga_id)
            elif current_source == "Happymh":
                chapters = fetch_chapters_happymh(manga_id)
        except Exception as e:
            console.print(f"[red]Failed to fetch chapters: {e}[/red]")
            chapters = []
            
        if not chapters:
            console.print("[yellow]No chapters found for selected language / manga.[/yellow]")
            continue
            
                                                 
        filtered_chapters = chapters
        if current_source == "MangaDex":
            all_groups = set()
            for c in chapters:
                for g in c.get("groups", []):
                    all_groups.add(g)
            
            if all_groups:
                group_choices = sorted(list(all_groups))
                selected_groups = questionary.checkbox(
                    "Filter by scanlation groups (leave empty for all):",
                    choices=group_choices
                ).ask()
                if selected_groups:
                    filtered_chapters = [
                        c for c in chapters 
                        if any(g in selected_groups for g in c.get("groups", []))
                    ]
        
        if not filtered_chapters:
            console.print("[yellow]No chapters left after filtering.[/yellow]")
            continue
            
        def chap_key(c):
            val = c.get("chapter")
            if not val: return 999999.0
            try:
                return float(val)
            except ValueError:
                match = re.search(r"(\d+(\.\d+)?)", str(val))
                return float(match.group(1)) if match else 999999.0
                
                       
        filtered_chapters.sort(key=chap_key)
        
                                       
        selection_method = questionary.select(
            "How do you want to select chapters?",
            choices=["Interactive List", "Select by Range (e.g. 1-10, 15)", "Select All"]
        ).ask()
        
        pre_selected_ids = set()
        
        if selection_method == "Select All":
            pre_selected_ids = {c["id"] for c in filtered_chapters}
        elif selection_method == "Select by Range (e.g. 1-10, 15)":
            range_input = questionary.text("Enter chapter range (e.g. 1-5, 8, 10-12):").ask()
            if range_input:
                             
                target_chapters = set()
                parts = [p.strip() for p in range_input.split(",") if p.strip()]
                for part in parts:
                    if "-" in part:
                        try:
                            start, end = map(float, part.split("-"))
                            for c in filtered_chapters:
                                try:
                                    c_val = float(c.get("chapter") or 0)
                                    if start <= c_val <= end:
                                        target_chapters.add(c["id"])
                                except Exception as e:
                                    logging.error(f"Error: {e}")
                                    pass
                        except ValueError:
                            pass
                    else:
                        try:
                            val = float(part)
                            for c in filtered_chapters:
                                try:
                                    c_val = float(c.get("chapter") or 0)
                                    if c_val == val:
                                        target_chapters.add(c["id"])
                                except Exception as e:
                                    logging.error(f"Error: {e}")
                                    pass
                        except ValueError:
                            pass
                pre_selected_ids = target_chapters

        chapter_choices = []
        chapter_mapping = {}
        for c in filtered_chapters:
            ch_text = c.get("chapter") or "?"
            title_text = c.get("title") or ""
            vol = c.get("volume") or ""
            lang_code = c.get("language") or ""
            date_str = (c.get("publishAt") or "").split("T")[0]
            groups = ", ".join(c.get("groups") or []) or "-"
            
                                     
            clean_title = title_text[:30].replace("\n", " ").strip()
            
            label = f"c{ch_text} - {clean_title} [vol:{vol or '-'}] [{lang_code}] [{date_str}] [{groups}]"
            is_checked = c["id"] in pre_selected_ids
            chapter_choices.append(questionary.Choice(label, value=c["id"], checked=is_checked))
            chapter_mapping[c["id"]] = c
            
        console.print("\n[bold yellow]Controls:[/bold yellow]")
        console.print(" - Use [bold]Space[/bold] to mark/unmark a chapter")
        console.print(" - Use [bold]A[/bold] to toggle all")
        console.print(" - Use [bold]I[/bold] to invert selection")
        console.print(" - Press [bold]Enter[/bold] when finished to start download\n")
        
        selected_chapter_ids = questionary.checkbox(
            "Confirm selection (Space to mark, Enter to confirm):",
            choices=chapter_choices,
            validate=lambda x: True
        ).ask()
        
        if not selected_chapter_ids:
            console.print("[yellow]No chapters selected. Did you use 'Space' to mark them?[/yellow]")
            time.sleep(2)
            continue
            
                                           
        use_saver = True
        if current_source == "MangaDex":
            use_saver = questionary.confirm("Use data-saver images (smaller)?", default=True).ask()
            if use_saver is None: continue
        
        make_cbz = questionary.confirm("Save chapters as CBZ files?", default=False).ask()
        
        cwd = Path.cwd()
        title_map = selected.get('originalTitle') or {}
        en_title = title_map.get('en') or selected.get('title')
        safe_title = "".join([c if c.isalnum() or c in " .-_" else "_" for c in en_title])
        
        base_out_raw = questionary.text("Output folder name (or full path):", default=safe_title).ask()
        if base_out_raw is None: continue
        
        entered_path = Path(base_out_raw.strip() if base_out_raw.strip() else safe_title)
        if not entered_path.is_absolute():
            base_out_path = cwd / entered_path
        else:
            base_out_path = entered_path
            
                                      
        final_parts = []
        if base_out_path.anchor:
            final_parts.append(base_out_path.anchor)
        for part in base_out_path.parts[len(Path(base_out_path.anchor).parts):]:
            sanitized_part = "".join([c if c.isalnum() or c in " .-_" else "_" for c in part])
            final_parts.append(sanitized_part)
        base_out = str(Path(*final_parts))
        
        for chapter_id in selected_chapter_ids:
            chapter_entry = chapter_mapping[chapter_id]
            ch_num = chapter_entry.get('chapter') or '?'
            console.print(f"Processing Chapter {ch_num} (ID: {chapter_id})...")
            
            try:
                image_urls = []
                
                if current_source == "MangaDex":
                    chap_info = get_chapter_info(chapter_id)
                    athome_resp = get_at_home_base(chapter_id)
                    base = athome_resp.get("baseUrl")
                    athome_chapter = athome_resp.get("chapter", {})
                    attrs = chap_info.get("attributes", {})
                    if not attrs.get("data") and athome_chapter.get("data"):
                        attrs = athome_chapter
                    image_urls = craft_image_urls(base, attrs, use_data_saver=use_saver)
                elif current_source == "Baozimh":
                    image_urls = get_baozimh_images(chapter_id)
                elif current_source == "Happymh":
                    manga_url = f"{HAPPYMH_BASE}/manga/{manga_id}"
                    image_urls = get_happymh_images(chapter_id, manga_url=manga_url)
                else:
                    # Fallback
                    pass

                if not image_urls:
                    console.print(f"[red]No image URLs found for chapter {ch_num}.[/red]")
                    continue
                    
                                      
                safe_ch_id = "".join([c if c.isalnum() else "_" for c in str(chapter_id)])
                out_dir = Path(base_out) / f"chapter_{ch_num}_{safe_ch_id[:8]}"
                
                # Pass chapter URL as referer for images
                referer = None
                if current_source == "Happymh":
                    referer = f"{HAPPYMH_BASE}{chapter_id}" if chapter_id.startswith("/") else chapter_id
                
                download_images(image_urls, str(out_dir), source=current_source, referer=referer)
                
                meta_path = out_dir / "metadata.json"
                meta = {
                    "manga": selected,
                    "chapter_upload": chapter_entry,
                    "downloaded_at": int(time.time()),
                    "quality": "data-saver" if use_saver else "data",
                    "source": current_source
                }
                try:
                    with open(meta_path, "w", encoding="utf-8") as fh:
                        json.dump(meta, fh, indent=2, ensure_ascii=False)
                except Exception as e:
                    logging.error(f"Error: {e}")
                    pass
                
                if make_cbz:
                    cbz_path = Path(base_out) / f"chapter_{ch_num}_{safe_ch_id[:8]}.cbz"
                    console.print(f"Archiving to {cbz_path.name}...")
                    with zipfile.ZipFile(cbz_path, "w", zipfile.ZIP_DEFLATED) as zf:
                        for item in out_dir.glob("*"):
                            if item.is_file():
                                zf.write(item, arcname=item.name)
                    shutil.rmtree(out_dir)
                    console.print(f"[green]Saved CBZ to {cbz_path}[/green]")
                else:
                    console.print(f"[green]Downloaded to {out_dir}[/green]")

            except Exception as e:
                console.print(f"[red]Error downloading chapter {ch_num}: {e}[/red]")
                
        if not make_cbz:
            share_now = questionary.confirm("Make ZIP of downloaded folder?", default=False).ask()
            if share_now:
                if os.path.exists(base_out):
                    zip_name = f"{Path(base_out).name}.zip"
                console.print(f"Creating zip {zip_name} ...")
                shutil.make_archive(Path(base_out).stem, 'zip', base_out)
                console.print(f"[green]Created {zip_name}[/green]")
                console.print("Ways to share:")
                console.print("- Upload the zip to Google Drive / Dropbox and share link")
                console.print("- Start a simple HTTP server: `python -m http.server 8000` in the folder and let others download over LAN")
                console.print("- Build a single-file executable with PyInstaller and share that binary")
            else:
                console.print("[red]Folder not found, skipping zip.[/red]")
        console.print("[bold]Operation complete. Returning to main menu.[/bold]")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[red]Cancelled by user.[/red]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]An unexpected error occurred: {e}[/bold red]")
        import traceback
        traceback.print_exc()
        console.input("\n[yellow]Press Enter to exit...[/yellow]")
        sys.exit(1)