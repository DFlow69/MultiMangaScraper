import shutil
import zipfile
import sys
import os
import io
import re
import json
import base64
import time
import requests
import threading
import unicodedata
import traceback
from bs4 import BeautifulSoup
try:
    from curl_cffi import requests as requests_cf
except ImportError:
    requests_cf = None
from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLineEdit, QPushButton, QLabel, 
                               QTreeWidget, QTreeWidgetItem, QSplitter, QTextEdit, 
                               QCheckBox, QProgressBar, QMessageBox, QFileDialog,
                               QListWidget, QAbstractItemView, QFrame, QSizePolicy,
                               QHeaderView, QMenu, QDialog, QDialogButtonBox, QListWidgetItem,
                               QComboBox)
from PySide6.QtCore import Qt, QThread, Signal, QObject, QEvent, QSize
from PySide6.QtGui import QPixmap, QImage, QFont, QIcon, QAction, QColor, QPalette, QActionGroup

try:
    import zhconv
except ImportError:
    zhconv = None

                        

class ScalableImageLabel(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_pixmap = None
        self._last_resize_time = 0
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(150, 225)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("border: 1px solid #444; background-color: #1a1a1a; border-radius: 4px;")

    def set_pixmap(self, pixmap):
        self._original_pixmap = pixmap
        self.update_display()

    def resizeEvent(self, event):
                                                                    
        current_time = time.time()
        if current_time - self._last_resize_time > 0.05:                
            self.update_display()
            self._last_resize_time = current_time
        super().resizeEvent(event)

    def update_display(self):
        if not self.isVisible(): return
        if self._original_pixmap and not self._original_pixmap.isNull():
                                              
            try:
                scaled = self._original_pixmap.scaled(
                    self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                super().setPixmap(scaled)
            except:
                pass                                   
        else:
            super().setText("No Cover")

class GroupFilterDialog(QDialog):
    def __init__(self, groups, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Filter Groups")
        self.resize(300, 400)
        self.layout = QVBoxLayout(self)
        
        self.list_widget = QListWidget()
        self.layout.addWidget(self.list_widget)
        
        self.groups = sorted(list(groups))
        
                                           
        btn_layout = QHBoxLayout()
        btn_all = QPushButton("All")
        btn_all.clicked.connect(self.select_all)
        btn_none = QPushButton("None")
        btn_none.clicked.connect(self.select_none)
        btn_layout.addWidget(btn_all)
        btn_layout.addWidget(btn_none)
        self.layout.addLayout(btn_layout)

                   
        for g in self.groups:
            item = QListWidgetItem(g)
            item.setCheckState(Qt.Checked)
            self.list_widget.addItem(item)
            
                        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)
        
        self.setStyleSheet("""
            QDialog { background-color: #2d2d2d; color: #fff; }
            QListWidget { background-color: #252526; color: #fff; border: 1px solid #444; }
            QListWidget::item:hover { background-color: #3e3e42; }
        """)

    def select_all(self):
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(Qt.Checked)

    def select_none(self):
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(Qt.Unchecked)

    def get_selected_groups(self):
        selected = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(item.text())
        return selected

class LibraryDialog(QDialog):
    def __init__(self, library_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Library")
        self.resize(500, 600)
        self.layout = QVBoxLayout(self)
        self.library_data = library_data
        
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.load_selected)
        self.layout.addWidget(self.list_widget)
        
        self.refresh_list()
        
        btn_layout = QHBoxLayout()
        self.btn_load = QPushButton("Load")
        self.btn_load.clicked.connect(self.load_selected)
        self.btn_remove = QPushButton("Remove")
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_load)
        btn_layout.addWidget(self.btn_remove)
        btn_layout.addWidget(self.btn_close)
        self.layout.addLayout(btn_layout)
        
        self.setStyleSheet("""
            QDialog { background-color: #2d2d2d; color: #fff; }
            QListWidget { background-color: #252526; color: #fff; border: 1px solid #444; }
            QListWidget::item:hover { background-color: #3e3e42; }
            QListWidget::item:selected { background-color: #007acc; }
        """)

    def refresh_list(self):
        self.list_widget.clear()
        for mid, data in self.library_data.items():
            title = data.get('title', 'Unknown')
                                                
            suffix = ""
            if data.get('has_update'):
                suffix = " [UPDATE!]"
            item = QListWidgetItem(f"{title}{suffix}")
            item.setData(Qt.UserRole, mid)
            self.list_widget.addItem(item)

    def load_selected(self):
        item = self.list_widget.currentItem()
        if item:
            mid = item.data(Qt.UserRole)
            self.parent().load_manga_from_library(mid)
            self.accept()

    def remove_selected(self):
        item = self.list_widget.currentItem()
        if item:
            mid = item.data(Qt.UserRole)
            if mid in self.library_data:
                del self.library_data[mid]
                self.refresh_list()

                                  
def excepthook(exc_type, exc_value, exc_traceback):
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print("CRITICAL ERROR:", tb)
                                                      
    if QApplication.instance():
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setText("An unexpected error occurred.")
        msg.setInformativeText(str(exc_value))
        msg.setDetailedText(tb)
        msg.setWindowTitle("Error")
        msg.exec()

sys.excepthook = excepthook

                       

API = "https://api.mangadex.org"
BAOZIMH_BASE = "https://www.baozimh.com"
HAPPYMH_BASE = "https://m.happymh.com"
RAWKUMA_BASE = "https://rawkuma.net"
SETTINGS_FILE = "settings.json"
LIBRARY_FILE = "library.json"

def api_get(path: str, params: dict | None = None) -> dict:
    url = API.rstrip("/") + "/" + path.lstrip("/")
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"API Error: {e}")
        return {}

def _normalize_text(s: Optional[str]) -> str:
    if not s: return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def _all_title_candidates(attrs: dict) -> List[str]:
    titles = set()
    if not attrs: return []
    title_map = attrs.get("title") or {}
    for v in title_map.values():
        if v: titles.add(str(v))
    alt = attrs.get("altTitles") or []
    for entry in alt:
        if isinstance(entry, dict):
            for v in entry.values():
                if v: titles.add(str(v))
        elif isinstance(entry, str):
            titles.add(entry)
    return list(titles)

def _matches_query(query_norm: str, title_norm: str) -> bool:
    if not query_norm or not title_norm: return False
    if query_norm in title_norm: return True
    q_tokens = query_norm.split()
    t_tokens = set(title_norm.split())
    return all(token in t_tokens for token in q_tokens)

def search_manga(title: str, limit: int = 100) -> List[dict]:
    title = (title or "").strip()
    if not title: return []
    query_norm = _normalize_text(title)
    collected_raw = []
    direct_id = None
    
                                     
    url_match = re.search(r"mangadex\.org/title/([a-fA-F0-9\-]+)", title)
    if url_match:
        direct_id = url_match.group(1)
        try:
            resp = api_get(f"/manga/{direct_id}", params={"includes[]": ["cover_art"]})
            data = resp.get("data")
            if data:
                collected_raw = [data]
        except: pass
    else:
        try:
            params = {"title": title, "limit": min(limit, 100), "includes[]": ["cover_art"]}
            resp = api_get("/manga", params=params)
            collected_raw.extend(resp.get("data", []))
        except: pass

                                      
    if not collected_raw or len(collected_raw) < 5:
        tokens = [t for t in re.split(r"[^A-Za-z0-9]+", title) if t]
        if tokens:
            try:
                params = {"title": " ".join(tokens[:4]), "limit": 100, "includes[]": ["cover_art"]}
                resp = api_get("/manga", params=params)
                for r in resp.get("data", []):
                                      
                    if not any(existing['id'] == r['id'] for existing in collected_raw):
                        collected_raw.append(r)
            except: pass

    results = []
    seen_ids = set()
    for item in collected_raw:
        manga_id = item.get("id")
        if not manga_id or manga_id in seen_ids: continue
        attrs = item.get("attributes", {}) or {}
        
        candidates = _all_title_candidates(attrs)
        matched = False
        if direct_id and direct_id == manga_id:
            matched = True
        else:
            for cand in candidates:
                if _matches_query(query_norm, _normalize_text(cand)):
                    matched = True
                    break
        
        display_title_map = attrs.get("title") or {}
                                                          
        default_title = display_title_map.get("en") or next(iter(display_title_map.values()), None) or (candidates[0] if candidates else "Unknown")
        
        cover_filename = None
        for rel in item.get("relationships", []) or []:
            if rel.get("type") == "cover_art":
                cover_filename = rel.get("attributes", {}).get("fileName")
                break

        results.append({
            "id": manga_id,
            "title": default_title,                 
            "attributes": attrs,                                              
            "status": attrs.get("status"),
            "description": (attrs.get("description") or {}).get("en", "No description"),
            "cover_filename": cover_filename,
            "matched": matched,
            "available_languages": attrs.get("availableTranslatedLanguages", [])
        })
        seen_ids.add(manga_id)
    
                                            
    results.sort(key=lambda r: (0 if r.get("matched") else 1, (r.get("title") or "").lower()))
    return results[:limit]

def fetch_chapters_for_manga(manga_id: str, langs: Optional[List[str]] = None) -> List[dict]:
    chapters = []
    limit = 100
    offset = 0
    while True:
        params = {
            "manga": manga_id, "limit": limit, "offset": offset,
            "order[chapter]": "asc", "includes[]": "scanlation_group"
        }
        if langs: params["translatedLanguage[]"] = langs
        
        resp = api_get("/chapter", params=params)
        page_results = resp.get("data", [])
        if not page_results: break
        
        for r in page_results:
            attrs = r.get("attributes", {}) or {}
            groups = []
            for rel in r.get("relationships", []) or []:
                if rel.get("type") == "scanlation_group":
                    name = rel.get("attributes", {}).get("name")
                    if name: groups.append(name)
            
            chapters.append({
                "id": r.get("id"),
                "chapter": attrs.get("chapter", ""),
                "title": attrs.get("title", ""),
                "volume": attrs.get("volume", ""),
                "language": attrs.get("translatedLanguage", ""),
                "publishAt": attrs.get("publishAt", ""),
                "groups": list(set(groups)),
                "attributes": attrs
            })
        
        offset += len(page_results)
        if len(page_results) < limit or offset >= 5000: break
    return chapters

def format_date(iso_str):
    if not iso_str: return ""
    try:
                                       
        return iso_str.split("T")[0]
    except:
        return iso_str

def get_chapter_info(chapter_id: str) -> dict:
    return api_get(f"/chapter/{chapter_id}").get("data", {})

def get_at_home_base(chapter_id: str) -> dict:
    return api_get(f"/at-home/server/{chapter_id}")

def craft_image_urls(base_url: str, chapter_attrs: dict, use_data_saver: bool = True) -> List[str]:
    hash_ = chapter_attrs.get("hash")
    if use_data_saver:
        files = chapter_attrs.get("dataSaver") or []
        mode = "data-saver"
    else:
        files = chapter_attrs.get("data") or []
        mode = "data"
    if not hash_ or not files: return []
    base = base_url.rstrip("/")
    return [f"{base}/{mode}/{hash_}/{fname}" for fname in files]

                               

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
        print(f"Error: {e}")
        pass
    return None

def fetch_baozimh_response(url: str, params: dict | None = None) -> requests.Response | None:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10, allow_redirects=True)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"Baozimh Error {url}: {e}")
        return None

def fetch_baozimh_html(url: str, params: dict | None = None) -> str | None:
    r = fetch_baozimh_response(url, params)
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
            print(f"Happymh CF Error: {e}")
            
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
        print(f"Happymh Standard Error: {e}")
        return None

def fetch_happymh_html(url: str, referer: Optional[str] = None) -> Optional[str]:
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
        print(f"Trying nodriver fallback for {url}")
        res = subprocess.run([sys.executable, "fetch_nodriver.py", url], 
                           capture_output=True, text=True, timeout=60)
        if res.returncode == 0 and res.stdout:
            cleaned = extract_html(res.stdout)
            # Check if nodriver actually bypassed it
            if cleaned and "嗨皮漫画" in cleaned and "人机验证" not in cleaned:
                return cleaned
    except Exception as e:
        print(f"Nodriver fallback failed: {e}")
        
    # Fallback 2: SeleniumBase UC Mode (Most robust)
    try:
        import subprocess
        print(f"Trying SeleniumBase fallback for {url}")
        res = subprocess.run([sys.executable, "fetch_sb.py", url], 
                           capture_output=True, text=True, timeout=120)
        if res.returncode == 0 and res.stdout:
            cleaned = extract_html(res.stdout)
            if cleaned and "嗨皮漫画" in cleaned and "人机验证" not in cleaned:
                return cleaned
    except Exception as e:
        print(f"SeleniumBase fallback failed: {e}")
        
    # Fallback 3: Playwright (Advanced network interception)
    try:
        import subprocess
        print(f"Trying Playwright fallback for {url}")
        res = subprocess.run([sys.executable, "fetch_playwright.py", url], 
                           capture_output=True, text=True, timeout=120)
        if res.returncode == 0 and res.stdout:
            cleaned = extract_html(res.stdout)
            if cleaned and "嗨皮漫画" in cleaned and "人机验证" not in cleaned:
                return cleaned
    except Exception as e:
        print(f"Playwright fallback failed: {e}")
        
    return None

def search_happymh(query: str) -> List[dict]:
    query = (query or "").strip()
    if not query: return []
    
    # 1. Direct URL Match
    if "happymh.com/manga/" in query:
        manga_id = query.split("/")[-1]
        try:
            html = fetch_happymh_html(query)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                title_tag = soup.select_one(".mg-title") or soup.select_one("h1")
                title = title_tag.get_text(strip=True) if title_tag else manga_id
                
                cover_tag = soup.select_one(".mg-banner img") or soup.select_one(".mg-poster img")
                cover_url = cover_tag.get("src") if cover_tag else ""
                
                return [{
                    "id": manga_id,
                    "title": title,
                    "attributes": {"title": {"en": title, "zh": title}},
                    "status": "Ongoing",
                    "description": "Loaded from URL (Happymh)",
                    "cover_filename": None,
                    "cover_url": cover_url,
                    "available_languages": ["zh"],
                    "source": "happymh"
                }]
        except:
            pass
            
        return [{
            "id": manga_id,
            "title": "Direct URL Match (Happymh)",
            "attributes": {"title": {"en": "Direct URL Match", "zh": "Direct URL Match"}},
            "status": "Unknown",
            "description": "Direct URL",
            "cover_filename": None,
            "cover_url": None,
            "available_languages": ["zh"],
            "source": "happymh"
        }]

    # 2. Search logic
    alt_query = get_anilist_chinese_title(query)
    search_q = alt_query if alt_query else query
    
    url = f"{HAPPYMH_BASE}/sssearch?v={search_q}"
    html = fetch_happymh_html(url)
    if not html: return []
    
    soup = BeautifulSoup(html, "html.parser")
    results = []
    
    cards = soup.select("a[href^='/manga/']")
    for card in cards:
        try:
            href = card.get("href")
            manga_id = href.split("/")[-1]
            if not manga_id or manga_id in [r['id'] for r in results]:
                continue
                
            title_tag = card.select_one(".MuiTypography-root") or card.select_one("div")
            title_text = title_tag.get_text(strip=True) if title_tag else "Unknown"
            
            img_tag = card.find("img")
            cover_url = img_tag.get("src") if img_tag else ""
            
            results.append({
                "id": manga_id,
                "title": title_text,
                "attributes": {"title": {"en": title_text, "zh": title_text}},
                "status": "Unknown",
                "description": "Found on Happymh",
                "cover_filename": None,
                "cover_url": cover_url,
                "available_languages": ["zh"],
                "source": "happymh"
            })
        except:
            continue
            
    return results

def fetch_chapters_happymh(manga_id: str) -> List[dict]:
    url = f"{HAPPYMH_BASE}/manga/{manga_id}"
    html = fetch_happymh_html(url)
    
    # Fallback: check if user provided a research file
    if not html:
        research_file = Path("baozimh_research/happymh.txt")
        if research_file.exists():
            try:
                with open(research_file, "r", encoding="utf-8") as f:
                    html = f.read()
            except:
                pass

    if not html: return []
    
    soup = BeautifulSoup(html, "html.parser")
    chapters = []
    
    # 1. Try standard a tags
    links = soup.select("a[href*='/mangaread/']")
    
    # 2. Try JSON in scripts if too few links
    if len(links) < 10:
        scripts = soup.find_all("script")
        for s in scripts:
            if not s.string: continue
            if '"chapters"' in s.string and '"id"' in s.string:
                try:
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
        href = link.get("href")
        if not href or href in seen_ids: continue
        seen_ids.add(href)
        
        title_tag = link.select_one(".MuiListItemText-primary") or link.select_one("span")
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
    
    # --- Method 1: Check for extra captured data ---
    extra_data_div = soup.find("div", id="extra_captured_data")
    if extra_data_div:
        try:
            captured_raw = extra_data_div.get_text()
            captured = json.loads(json.loads(captured_raw))
            if captured.get("images"):
                images.extend(captured["images"])
            
            js_vars = captured.get("js_variables", {})
            for var_name, var_val in js_vars.items():
                if var_name.startswith("canvas_"):
                    images.append("canvas_data:" + var_val)
                else:
                    found_urls = re.findall(r'\"(https?://[^\"]+\.(?:jpg|png|webp|jpeg)[^\"]*)\"', str(var_val))
                    images.extend([u.replace('\\/', '/') for u in found_urls])
            
            for resp in captured.get("json_responses", []):
                found_urls = re.findall(r'\"(https?://[^\"]+\.(?:jpg|png|webp|jpeg)[^\"]*)\"', resp["content"])
                images.extend([u.replace('\\/', '/') for u in found_urls])
        except:
            pass

    # --- Method 2: JSON data in scripts ---
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

    # --- Method 3: DOM Selectors ---
    selectors = [
        "img[id^='scan']",
        "div.css-1krjvn-imgContainer img",
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

    # --- Method 4: Raw Regex Scan ---
    patterns = [
        r'https?://ruicdn\.happymh\.com/[^\s\"\'<>)]+\.(?:jpg|png|webp|jpeg)[^\s\"\'<>)]*',
        r'https?://img\.happymh\.com/[^\s\"\'<>)]+\.(?:jpg|png|webp|jpeg)[^\s\"\'<>)]*'
    ]
    for pattern in patterns:
        found = re.findall(pattern, html)
        if found:
            images.extend(found)

    # deduplication
    seen = set()
    final_images = []
    for img in images:
        if img.startswith("canvas_data:canvas_data:"):
            img = img[12:]
        if img not in seen:
            final_images.append(img)
            seen.add(img)
            
    return final_images

def search_baozimh(query: str) -> List[dict]:
    query = (query or "").strip()
    if not query: return []
    
                              
    if "baozimh.com" in query:
                             
                                                    
        manga_id = query.split("/")[-1]
        
                                                       
        try:
            html = fetch_baozimh_html(query)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                
                                                                  
                title_tag = soup.select_one(".comics-detail__title") or soup.select_one("h1")
                title = title_tag.get_text(strip=True) if title_tag else manga_id
                
                                               
                cover_tag = soup.select_one("amp-img.comics-detail__poster") or soup.select_one(".comics-detail__poster amp-img")
                cover_url = None
                if cover_tag:
                    cover_url = cover_tag.get("src") or cover_tag.get("data-src")
                    
                return [{
                    "id": manga_id,
                    "title": title,
                    "attributes": {"title": {"en": title, "zh": title}},
                    "status": "Ongoing",
                    "description": "Loaded from URL",
                    "cover_filename": None,
                    "cover_url": cover_url,
                    "available_languages": ["zh"],
                    "source": "baozimh"
                }]
        except:
            pass

        return [{
            "id": manga_id,
            "title": "Direct URL Match",
            "attributes": {"title": {"en": "Direct URL Match", "zh": "Direct URL Match"}},
            "status": "Unknown",
            "description": "Direct URL Match",
            "cover_filename": None,
            "cover_url": None,
            "available_languages": ["zh"],
            "source": "baozimh"
        }]
    
                                                  
                                                                         
    translated_query = None
    if all(ord(c) < 128 for c in query):
        translated_query = get_anilist_chinese_title(query)
        if translated_query:
            print(f"AniList Bridge: {query} -> {translated_query}")
                                              
                                                                         
                                                                                       
                                                      
            query = translated_query

    html = fetch_baozimh_html(f"{BAOZIMH_BASE}/search", params={"q": query})
    if not html: return []
    
    soup = BeautifulSoup(html, "html.parser")

    results = []
    
                          
    for card in soup.select("div.comics-card"):
        link = card.select_one("a.comics-card__poster")
        if not link: continue
        
        href = link.get("href")
        title = link.get("title")
        if not href or not title: continue
        
                                                         
        manga_id = href.split("/")[-1]
        
                     
        img_tag = link.select_one("amp-img, img")
        cover_url = None
        if img_tag:
            cover_url = img_tag.get("src") or img_tag.get("data-src")
            
        results.append({
            "id": manga_id,
            "title": title,
            "attributes": {"title": {"en": title, "zh": title}},
            "status": "Ongoing",          
            "description": "From Baozimh",
            "cover_filename": None,
            "cover_url": cover_url,
            "available_languages": ["zh"],
            "source": "baozimh"
        })
        
    # Filter results if we used an AniList translation to be more precise
    if translated_query and results:
        filtered = []
        for r in results:
            title_check = r['title']
            query_check = translated_query
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
    url = f"{BAOZIMH_BASE}/comic/{manga_id}"
    html = fetch_baozimh_html(url)
    if not html: return []
    
    soup = BeautifulSoup(html, "html.parser")
    chapters = []
    
                                           
                                               
                                          
    latest_date = ""
    date_regex = re.compile(r"(\d{4}年\d{2}月\d{2}日)")
    
                                                   
                                         
                                                                                       
                                                                 
    body_text = soup.get_text()
    date_match = date_regex.search(body_text)
    if date_match:
                                           
        d_str = date_match.group(1)
        latest_date = d_str.replace("年", "-").replace("月", "-").replace("日", "")
    
                      
                                                           
                                                           
                                                                       
                                               
                                                                             
                                                                          
    
                                                                                               
                                              
    seen_ids = set()

    for link in soup.select("div.comics-chapters a.comics-chapters__item"):
        href = link.get("href")
        if not href or href in seen_ids: continue
        seen_ids.add(href)
        
        text = link.get_text().strip()
        
                                                                                            
                                                                      
                                                    
                                                                                         
                                                               
                                                                                    
                                               
                                                          
                                                                           
                                           
                                                                                      
                                                                      
                                                               
                                                         
                                                                               
                                                    
        
        publish_at = ""
        if latest_date and len(chapters) == 0:                                                           
             publish_at = latest_date

        chapters.append({
            "id": href, 
            "chapter": text, 
            "title": text,
            "language": "zh",
            "groups": [],
            "publishAt": publish_at,
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


def slugify_rawkuma(text: str) -> str:
    # Basic slugify: lowercase, remove special chars, spaces to hyphens
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s]+', '-', text)
    return text.strip('-')

def search_rawkuma(query: str) -> List[dict]:
    print(f"Searching Rawkuma with query: {query}")
    
    # 0. Check if query is already a Rawkuma URL
    if "rawkuma.net/manga/" in query:
        return [{
            "id": query,
            "title": "Direct URL",
            "status": "Unknown",
            "description": "Direct Link",
            "cover_filename": None,
            "cover_url": "",
            "matched": True,
            "all_candidates": [],
            "available_languages": ["raw"],
            "source": "rawkuma"
        }]

    # 1. Use Anilist to find candidates
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
          coverImage {
            large
          }
        }
      }
    }
    '''
    variables = {'search': query}
    
    candidates = []
    try:
        r = requests.post(url, json={'query': query_graphql, 'variables': variables}, timeout=5)
        if r.status_code == 200:
            data = r.json()
            media_list = data.get('data', {}).get('Page', {}).get('media', [])
            for media in media_list:
                titles = media.get('title', {})
                t_romaji = titles.get('romaji')
                t_english = titles.get('english')
                syns = media.get('synonyms', [])
                
                slug_candidates = []
                if t_romaji: slug_candidates.append((t_romaji, "Romaji"))
                if t_english: slug_candidates.append((t_english, "English"))
                for s in syns: slug_candidates.append((s, "Synonym"))
                
                display_title = t_english or t_romaji or "Unknown"
                cover = media.get('coverImage', {}).get('large', "")
                
                candidates.append({
                    "display_title": display_title,
                    "cover": cover,
                    "slugs": slug_candidates
                })
    except Exception as e:
        print(f"Anilist search failed: {e}")
        # Fallback: try query as slug
        candidates.append({
            "display_title": query,
            "cover": "",
            "slugs": [(query, "Query")]
        })

    results = []
    seen_ids = set()
    
    # 2. Validate candidates against Rawkuma
    for cand in candidates:
        found_for_cand = False
        for title_text, source_type in cand['slugs']:
            if found_for_cand: break # Only need one valid URL per manga
            
            slug = slugify_rawkuma(title_text)
            if not slug: continue
            
            check_url = f"{RAWKUMA_BASE}/manga/{slug}/"
            if check_url in seen_ids: continue
            
            print(f"Checking Rawkuma URL: {check_url}")
            try:
                # Use HEAD to check existence
                resp = requests.head(check_url, timeout=5, allow_redirects=True)
                
                if resp.status_code == 200:
                    results.append({
                        "id": check_url,
                        "title": cand['display_title'],
                        "status": "Unknown",
                        "description": f"Found via {source_type}: {title_text}",
                        "cover_filename": None,
                        "cover_url": cand['cover'],
                        "matched": True,
                        "all_candidates": [title_text],
                        "available_languages": ["raw"],
                        "source": "rawkuma"
                    })
                    seen_ids.add(check_url)
                    found_for_cand = True
            except Exception as e:
                pass
                
    return results

def fetch_chapters_rawkuma(manga_id: str) -> List[dict]:
    # manga_id is the full URL
    url = manga_id if manga_id.startswith("http") else f"{RAWKUMA_BASE}/manga/{manga_id}/"
    print(f"Fetching Rawkuma chapters from: {url}")
    
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        html = r.text
        soup = BeautifulSoup(html, "html.parser")
        
        # Check for HTMX chapter list
        chapter_list_div = soup.find("div", id="chapter-list")
        if chapter_list_div and chapter_list_div.get("hx-get"):
            hx_url = chapter_list_div.get("hx-get").strip()
            if not hx_url.startswith("http"):
                hx_url = f"{RAWKUMA_BASE}{hx_url}" if hx_url.startswith("/") else f"{RAWKUMA_BASE}/{hx_url}"
            
            print(f"Fetching HTMX chapter list from: {hx_url}")
            r2 = requests.get(hx_url, timeout=15)
            r2.raise_for_status()
            soup = BeautifulSoup(r2.text, "html.parser")
        
        chapters = []
        seen_ids = set()
        
        # Look for Google Drive links: drive.google.com/uc?id=...
        # These are usually in 'a' tags with 'export=download' or similar
        
        # Find all 'a' tags with href containing "drive.google.com"
        gdrive_links = soup.select('a[href*="drive.google.com"]')
        
        # Try to parse using data-chapter-number attribute (HTMX structure)
        chapter_items = soup.find_all("div", attrs={"data-chapter-number": True})
        
        if chapter_items:
            for item in chapter_items:
                glink = item.find("a", href=lambda h: h and "drive.google.com" in h)
                if not glink: continue
                
                href = glink.get("href")
                if href in seen_ids: continue
                seen_ids.add(href)
                
                title = f"Chapter {item.get('data-chapter-number')}"
                
                # Try to get more specific title
                chap_link = item.find("a", href=lambda h: h and "/chapter-" in h)
                if chap_link:
                    ctext = chap_link.get_text(" ", strip=True)
                    m = re.search(r'(Chapter\s+\d+(\.\d+)?)', ctext, re.IGNORECASE)
                    if m:
                        title = m.group(1)
                    elif ctext:
                        title = ctext
                
                chapters.append({
                    "id": href,
                    "chapter": title,
                    "title": title,
                    "language": "raw",
                    "scanlator": "Rawkuma",
                    "date": "",
                    "source": "rawkuma"
                })
        else:
            # Fallback
            gdrive_links = soup.select('a[href*="drive.google.com"]')
            for link in gdrive_links:
                href = link.get("href")
                if not href or href in seen_ids: continue
                
                title = "Chapter (Unknown)"
                container = link.find_parent("li") or link.find_parent("div", class_="flex") or link.find_parent("div")
                if container:
                    text = container.get_text(" ", strip=True)
                    m = re.search(r'(Chapter\s+\d+(\.\d+)?)', text, re.IGNORECASE)
                    if m:
                        title = m.group(1)
                    else:
                        text = text.replace("Download", "").strip()
                        if text: title = text
                
                seen_ids.add(href)
                chapters.append({
                    "id": href,
                    "chapter": title,
                    "title": title,
                    "language": "raw",
                    "scanlator": "Rawkuma",
                    "date": "",
                    "source": "rawkuma"
                })
            
        return chapters
        
    except Exception as e:
        print(f"Error fetching Rawkuma chapters: {e}")
        return []


class SearchWorker(QThread):
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, query, site="mangadex"):
        super().__init__()
        self.query = query
        self.site = site

    def run(self):
        try:
            if self.isInterruptionRequested(): return
            
            if self.site == "baozimh":
                results = search_baozimh(self.query)
            elif self.site == "happymh":
                results = search_happymh(self.query)
            elif self.site == "rawkuma":
                results = search_rawkuma(self.query)
            else:
                results = search_manga(self.query)
            
            if self.isInterruptionRequested(): return
            self.finished.emit(results)
        except Exception as e:
            if not self.isInterruptionRequested():
                self.error.emit(str(e))

class ChapterWorker(QThread):
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, manga_id, langs=None, site="mangadex"):
        super().__init__()
        self.manga_id = manga_id
        self.langs = langs
        self.site = site

    def run(self):
        try:
            if self.isInterruptionRequested(): return

            if self.site == "baozimh":
                chapters = fetch_chapters_baozimh(self.manga_id)
            elif self.site == "happymh":
                chapters = fetch_chapters_happymh(self.manga_id)
                if not chapters:
                    self.error.emit("Happymh returned 0 chapters. This might be due to Cloudflare protection. Try pasting the direct URL or providing cookies in 'happymh_cookies.json'.")
                    return
            elif self.site == "rawkuma":
                chapters = fetch_chapters_rawkuma(self.manga_id)
            else:
                chapters = fetch_chapters_for_manga(self.manga_id, self.langs)
            
            if self.isInterruptionRequested(): return
            
            def chap_key(c):
                val = c.get("chapter")
                if not val: return 999999.0
                try: return float(val)
                except ValueError:
                    match = re.search(r"(\d+(\.\d+)?)", str(val))
                    return float(match.group(1)) if match else 999999.0
            chapters.sort(key=chap_key)
            
            if not self.isInterruptionRequested():
                self.finished.emit(chapters)
        except Exception as e:
            if not self.isInterruptionRequested():
                self.error.emit(str(e))

class DownloadWorker(QThread):
    progress = Signal(str)
    percent = Signal(int)
    finished = Signal()
    error = Signal(str)

    def __init__(self, chapters, base_dir, use_saver, manga_id=None, make_cbz=False, site="mangadex"):
        super().__init__()
        self.chapters = chapters
        self.base_dir = base_dir
        self.use_saver = use_saver
        self.manga_id = manga_id
        self.make_cbz = make_cbz
        self.site = site
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        total_chaps = len(self.chapters)
        for i, chap in enumerate(self.chapters):
            if not self._is_running: break
            
            ch_num = chap.get("chapter") or "?"
            self.progress.emit(f"Processing Chapter {ch_num}...")
            
            try:
                if self.site == "rawkuma":
                    safe_title = "".join(c for c in (chap.get('title') or "") if c.isalnum() or c in (' ', '-', '_')).strip()
                    self.progress.emit(f"Downloading Ch {ch_num} from GDrive...")
                    
                    session = requests.Session()
                    response = session.get(chap['id'], stream=True, timeout=60)
                    response.raise_for_status()
                    
                    # Check for GDrive confirmation warning
                    token = None
                    for key, value in response.cookies.items():
                        if key.startswith('download_warning'):
                            token = value
                            break
                            
                    if token:
                         params = {'confirm': token}
                         response = session.get(chap['id'], params=params, stream=True, timeout=60)
                         response.raise_for_status()

                    if "Content-Disposition" in response.headers:
                        cd = response.headers["Content-Disposition"]
                        fname_match = re.search(r'filename="?([^"]+)"?', cd)
                        if fname_match:
                            fname = fname_match.group(1)
                        else:
                            fname = f"Chapter {ch_num}"
                            if safe_title: fname += f" - {safe_title}"
                            fname += ".zip"
                    else:
                        fname = f"Chapter {ch_num}"
                        if safe_title: fname += f" - {safe_title}"
                        fname += ".zip" # Default extension
                    
                    dest = Path(self.base_dir) / fname
                    
                    with open(dest, "wb") as f:
                        for chunk in response.iter_content(8192):
                            if not self._is_running: break
                            f.write(chunk)
                    
                    if not self._is_running:
                        if dest.exists(): dest.unlink()
                        break
                        
                    self.percent.emit(int(((i + 1) / total_chaps) * 100))
                    continue

                urls = []
                if self.site == "baozimh":
                    urls = get_baozimh_images(chap['id'])
                elif self.site == "happymh":
                    manga_url = f"{HAPPYMH_BASE}/manga/{self.manga_id}"
                    urls = get_happymh_images(chap['id'], manga_url=manga_url)
                else:
                    chap_info = get_chapter_info(chap['id'])
                    athome = get_at_home_base(chap['id'])
                    base = athome.get("baseUrl")
                    
                    attrs = chap_info.get("attributes", {})
                    athome_chap = athome.get("chapter", {})
                    if not attrs.get("data") and athome_chap.get("data"):
                        attrs = athome_chap
                    
                    urls = craft_image_urls(base, attrs, use_data_saver=self.use_saver)

                if not urls:
                    self.progress.emit(f"No images for Ch {ch_num}")
                    continue
                
                                      
                safe_title = "".join(c for c in (chap.get('title') or "") if c.isalnum() or c in (' ', '-', '_')).strip()
                folder_name = f"Chapter {ch_num}"
                if safe_title:
                    folder_name += f" - {safe_title}"
                
                out_path = Path(self.base_dir) / folder_name
                out_path.mkdir(parents=True, exist_ok=True)
                
                # Use curl_cffi for happymh images
                session = None
                referer_url = HAPPYMH_BASE
                if self.site == "happymh":
                    session = get_happymh_session()
                    referer_url = f"{HAPPYMH_BASE}{chap['id']}" if chap['id'].startswith("/") else chap['id']
                else:
                    session = requests.Session()

                for j, url in enumerate(urls, 1):
                    if not self._is_running: break
                    fname = f"{j:03d}.jpg"
                    if "." in url:
                        parts = url.split(".")
                        ext = parts[-1].split("?")[0]
                        if len(ext) <= 4: fname = f"{j:03d}.{ext}"
                    
                    dest = out_path / fname
                    if not dest.exists():
                        if url.startswith("canvas_data:"):
                            try:
                                import base64
                                header, encoded = url.split(",", 1)
                                data = base64.b64decode(encoded)
                                with open(dest, "wb") as f:
                                    f.write(data)
                            except Exception as e:
                                self.progress.emit(f"Error saving canvas: {e}")
                            continue

                        try:
                            get_kwargs = {"stream": True, "timeout": 30}
                            if self.site == "happymh" and requests_cf:
                                get_kwargs["impersonate"] = "chrome120"
                                get_kwargs["headers"] = {"Referer": referer_url}
                            
                            with session.get(url, **get_kwargs) as r:
                                r.raise_for_status()
                                with open(dest, "wb") as f:
                                    for chunk in r.iter_content(8192):
                                        f.write(chunk)
                        except Exception as e:
                            self.progress.emit(f"Error page {j}: {e}")
                
                meta = {
                    "chapter": chap,
                    "downloaded_at": int(time.time())
                }
                with open(out_path / "metadata.json", "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2)
                
                              
                if self.make_cbz:
                    cbz_path = Path(self.base_dir) / f"{folder_name}.cbz"
                    self.progress.emit(f"Creating CBZ: {cbz_path.name}")
                    with zipfile.ZipFile(cbz_path, "w", zipfile.ZIP_DEFLATED) as zf:
                        for item in out_path.glob("*"):
                            if item.is_file():
                                zf.write(item, arcname=item.name)
                                    
                    shutil.rmtree(out_path)

            except Exception as e:
                self.error.emit(f"Error Ch {ch_num}: {e}")
            
            self.percent.emit(int(((i + 1) / total_chaps) * 100))
        
        self.finished.emit()

class ImageLoader(QThread):
    loaded = Signal(QImage)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            r = requests.get(self.url, timeout=10)
            r.raise_for_status()
            img = QImage.fromData(r.content)
            self.loaded.emit(img)
        except:
            pass

                     

class ModernMangaDexGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = self.load_settings()
        self.library = self.load_library()
        self._old_workers = []
        self.setWindowTitle("MangaDex Scraper (Modern Qt)")
        self.resize(1200, 800)
        
                                   
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; color: #f0f0f0; }
            QWidget { background-color: #1e1e1e; color: #f0f0f0; font-family: 'Segoe UI', sans-serif; font-size: 14px; }
            
            QLineEdit { 
                padding: 10px; 
                border: 1px solid #333; 
                border-radius: 6px; 
                background-color: #2d2d2d; 
                color: #fff;
                selection-background-color: #007acc;
            }
            QLineEdit:focus { border: 1px solid #007acc; }
            
            QPushButton { 
                padding: 8px 16px; 
                border: none; 
                border-radius: 6px; 
                background-color: #007acc; 
                color: white; 
                font-weight: 600; 
            }
            QPushButton:hover { background-color: #0098ff; }
            QPushButton:pressed { background-color: #005c99; }
            QPushButton:disabled { background-color: #333; color: #666; }
            
            QTreeWidget, QListWidget, QTextEdit { 
                border: 1px solid #333; 
                border-radius: 6px; 
                background-color: #252526; 
                alternate-background-color: #2d2d2d;
                color: #eee;
            }
            QTreeWidget::item { padding: 4px; }
            QTreeWidget::item:selected { background-color: #37373d; }
            QHeaderView::section { 
                background-color: #333; 
                padding: 6px; 
                border: none; 
                font-weight: bold; 
                color: #ccc;
            }
            
            QProgressBar { 
                border: 1px solid #333; 
                border-radius: 6px; 
                text-align: center; 
                background-color: #252526;
            }
            QProgressBar::chunk { background-color: #007acc; border-radius: 5px; }
            
            QSplitter::handle { background-color: #333; }
            QLabel { color: #ddd; }
            QCheckBox { spacing: 8px; color: #ddd; }
            QCheckBox::indicator { width: 18px; height: 18px; }
        """)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(15)

                                
        self.top_bar = QHBoxLayout()
        
        self.site_combo = QComboBox()
        self.site_combo.addItems(["MangaDex", "Baozimh", "Happymh", "Rawkuma"])
        self.site_combo.setToolTip("Select source site")
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search manga by title...")
        self.search_input.returnPressed.connect(self.start_search)
        
        self.search_btn = QPushButton("Search")
        self.search_btn.setIcon(QIcon.fromTheme("system-search"))
        self.search_btn.clicked.connect(self.start_search)
        
        self.romaji_chk = QCheckBox("Show Romaji Titles")
        self.romaji_chk.setToolTip("Toggle between English and Romaji titles")
        self.romaji_chk.stateChanged.connect(self.refresh_titles)
        
        self.top_bar.addWidget(self.site_combo)
        self.top_bar.addWidget(self.search_input, stretch=1)
        self.top_bar.addWidget(self.romaji_chk)
        self.top_bar.addWidget(self.search_btn)
        
        self.lib_btn = QPushButton("Library")
        self.lib_btn.setIcon(QIcon.fromTheme("system-file-manager"))
        self.lib_btn.clicked.connect(self.open_library)
        self.top_bar.addWidget(self.lib_btn)
        
        self.layout.addLayout(self.top_bar)

                                
        self.splitter = QSplitter(Qt.Horizontal)
        self.layout.addWidget(self.splitter)

                              
        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        
                                                            
        self.results_header = QHBoxLayout()
        self.results_label = QLabel("Search Results")
        self.results_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        
        self.loaded_label = QLabel("")
        self.loaded_label.setStyleSheet("color: #aaa; font-style: italic;")

        self.results_header.addWidget(self.results_label)
        self.results_header.addStretch()
        self.results_header.addWidget(self.loaded_label)
        
        self.left_layout.addLayout(self.results_header)
        
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(["Title", "Status"])
        self.results_tree.setColumnWidth(0, 300)
        self.results_tree.setAlternatingRowColors(True)
        self.results_tree.itemSelectionChanged.connect(self.on_manga_selected)
        self.left_layout.addWidget(self.results_tree)
        
        self.splitter.addWidget(self.left_panel)

                                   
        self.right_widget = QWidget()
        self.right_layout = QVBoxLayout(self.right_widget)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.splitter.addWidget(self.right_widget)
        
                                                                           
                                                         
                                 
        self.splitter.setSizes([250, 950])
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)

                                                   
        self.info_frame = QFrame()
        self.info_frame.setStyleSheet("QFrame { background-color: #252526; border-radius: 8px; padding: 10px; }")
                                                        
        self.info_layout = QHBoxLayout(self.info_frame)
        
        self.cover_label = ScalableImageLabel()
        self.cover_label.setText("No Cover")
        self.cover_label.setMaximumWidth(450)                    
        self.cover_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)                                                           

                                                
        self.details_layout = QVBoxLayout()
        self.details_layout.setSpacing(5)                  
        self.details_layout.setContentsMargins(0, 0, 0, 0)
        
        self.title_label = QLabel("Select a manga")
        self.title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #fff;")
        self.title_label.setWordWrap(True)
        self.title_label.setMaximumHeight(60)                     
        
        self.desc_text = QTextEdit()
        self.desc_text.setReadOnly(True)
        self.desc_text.setPlaceholderText("Description...")
        self.desc_text.setStyleSheet("border: none; background-color: transparent;")
        self.desc_text.setMaximumHeight(100)                           
        
        self.lang_label = QLabel("Available Languages:")
        self.lang_label.setStyleSheet("color: #aaa; font-size: 12px; margin-top: 5px;")
        
                                 
        self.lang_list = QListWidget()
        self.lang_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.lang_list.setFlow(QListWidget.LeftToRight)                  
        self.lang_list.setWrapping(True)                    
        self.lang_list.setResizeMode(QListWidget.Adjust)                   
        self.lang_list.setSpacing(4)
        self.lang_list.setMaximumHeight(80)                                               
        self.lang_list.setStyleSheet("""
            QListWidget { background-color: transparent; border: none; }
            QListWidget::item { 
                background-color: #333; 
                border-radius: 4px; 
                padding: 4px 8px; 
                color: #ddd;
                margin: 2px;
            }
            QListWidget::item:selected { 
                background-color: #007acc; 
                color: white;
            }
            QListWidget::item:hover {
                background-color: #444;
            }
        """)
        self.lang_list.itemSelectionChanged.connect(self.on_lang_changed)

        self.details_layout.addWidget(self.title_label)
        self.details_layout.addWidget(self.desc_text)
        self.details_layout.addWidget(self.lang_label)
        self.details_layout.addWidget(self.lang_list)
        
        self.btn_add_lib = QPushButton("Add to Library")
        self.btn_add_lib.clicked.connect(self.add_current_to_library)
        self.details_layout.addWidget(self.btn_add_lib)

        self.details_layout.addStretch()                                   
        
        self.info_layout.addWidget(self.cover_label)                                                   
        self.info_layout.addLayout(self.details_layout, stretch=1)
        
                                                            
        self.right_layout.addWidget(self.info_frame, stretch=0)

                          
        self.chap_ctrl_layout = QHBoxLayout()
        self.btn_select_all = QPushButton("Select All")
        self.btn_select_all.clicked.connect(self.select_all_chapters)
        self.btn_deselect_all = QPushButton("Deselect All")
        self.btn_deselect_all.clicked.connect(self.deselect_all_chapters)
        self.btn_invert = QPushButton("Invert")
        self.btn_invert.clicked.connect(self.invert_chapters)
        
        self.btn_filter_group = QPushButton("Filter Groups")
        self.btn_filter_group.clicked.connect(self.open_group_filter)

                         
        self.range_start = QLineEdit()
        self.range_start.setPlaceholderText("Start")
        self.range_start.setFixedWidth(50)
        self.range_end = QLineEdit()
        self.range_end.setPlaceholderText("End")
        self.range_end.setFixedWidth(50)
        self.btn_range = QPushButton("Select Range")
        self.btn_range.clicked.connect(self.select_chapter_range)
        
                                               
        self.cbz_chk = QCheckBox("Save as CBZ")
        self.cbz_chk.setToolTip("Save chapters as .cbz files instead of folders")
        
        self.data_saver_chk = QCheckBox("Data Saver")
        self.data_saver_chk.setToolTip("Use compressed images (saves bandwidth)")
        self.data_saver_chk.setChecked(True)
        
        self.download_btn = QPushButton("Download Selected")
        self.download_btn.clicked.connect(self.start_download)
                                                                                           
        
        self.chap_ctrl_layout.addWidget(self.btn_select_all)
        self.chap_ctrl_layout.addWidget(self.btn_deselect_all)
        self.chap_ctrl_layout.addWidget(self.btn_invert)
        self.chap_ctrl_layout.addWidget(self.btn_filter_group)
        
                   
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        self.chap_ctrl_layout.addWidget(line)
        
                      
        self.chap_ctrl_layout.addWidget(QLabel("Range:"))
        self.chap_ctrl_layout.addWidget(self.range_start)
        self.chap_ctrl_layout.addWidget(QLabel("-"))
        self.chap_ctrl_layout.addWidget(self.range_end)
        self.chap_ctrl_layout.addWidget(self.btn_range)
        
                     
        line2 = QFrame()
        line2.setFrameShape(QFrame.VLine)
        line2.setFrameShadow(QFrame.Sunken)
        self.chap_ctrl_layout.addWidget(line2)

                                 
        self.chap_ctrl_layout.addWidget(self.data_saver_chk)
        self.chap_ctrl_layout.addWidget(self.cbz_chk)
        self.chap_ctrl_layout.addStretch()                                    
        self.chap_ctrl_layout.addWidget(self.download_btn)
        
        self.right_layout.addLayout(self.chap_ctrl_layout)

                                                        
        self.chapter_tree = QTreeWidget()
        self.chapter_tree.setHeaderLabels(["Ch", "Title", "Lang", "Group", "Release Date"])
        self.chapter_tree.setAlternatingRowColors(True)
        self.chapter_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
                                      
        header = self.chapter_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)     
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)       
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)               
        header.setSectionResizeMode(1, QHeaderView.Stretch)                             
        header.setSectionResizeMode(3, QHeaderView.Interactive)                           

        self.right_layout.addWidget(self.chapter_tree, stretch=1)

                                                           
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(10)                    
        self.layout.addWidget(self.progress_bar)
        
        self.log_text = QLabel("Ready")
        self.log_text.setVisible(False)                                             
        self.layout.addWidget(self.log_text)

               
        self.search_results = []
        self.selected_manga = None
        self.chapters = []
        self.download_worker = None
        self.current_search_query = ""
        self.all_chapter_groups = set()

                          
        if self.settings.get("romaji_titles"): self.romaji_chk.setChecked(True)
        if self.settings.get("data_saver") is False: self.data_saver_chk.setChecked(False)
        if self.settings.get("cbz_mode"): self.cbz_chk.setChecked(True)

    def log(self, msg):
        self.log_text.setText(msg)
        print(msg)

    def get_preferred_title(self, manga_data):
                                           
        use_romaji = self.romaji_chk.isChecked()
        attrs = manga_data.get('attributes', {})
        titles = attrs.get('title', {})
        alt_titles = attrs.get('altTitles', [])
        
        en_title = titles.get('en')
        jp_ro_title = titles.get('ja-ro')
        
                                                                
        if not en_title:
             for alt in alt_titles:
                if 'en' in alt:
                    en_title = alt['en']
                    break

        if not jp_ro_title:
            for alt in alt_titles:
                if 'ja-ro' in alt:
                    jp_ro_title = alt['ja-ro']
                    break
        
                         
                                                                      
                                                                        
        
        if use_romaji:
            if jp_ro_title: return jp_ro_title
            if en_title: return en_title
        else:
            if en_title: return en_title
            if jp_ro_title: return jp_ro_title
        
                                            
        return manga_data.get('title') or "Unknown Title"

    def refresh_titles(self):
                                                    
        if not self.search_results: return
        
                        
        selected_id = self.selected_manga['id'] if self.selected_manga else None
        
        self.results_tree.clear()
        for r in self.search_results:
            display_title = self.get_preferred_title(r)
            item = QTreeWidgetItem([display_title, r['status'] or "N/A"])
            item.setData(0, Qt.UserRole, r['id'])           
            self.results_tree.addTopLevelItem(item)
            
            if selected_id and r['id'] == selected_id:
                item.setSelected(True)
                                              
                self.title_label.setText(f"{display_title} ({r['status']})")

    def cleanup_worker(self, worker):
        if worker in self._old_workers:
            self._old_workers.remove(worker)
        worker.deleteLater()

    def start_search(self):
        query = self.search_input.text()
        if not query: return
        
        site = self.site_combo.currentText()
        if site == "MangaDex":
            site_key = "mangadex"
        elif site == "Baozimh":
            site_key = "baozimh"
        elif site == "Happymh":
            site_key = "happymh"
        elif site == "Rawkuma":
            site_key = "rawkuma"
        else:
            QMessageBox.information(self, "Not Implemented", f"Support for {site} is coming soon!")
            return

        self.log(f"Searching for: {query} on {site}...")
        
                                     
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            try: self.worker.finished.disconnect()
            except: pass
            try: self.worker.error.disconnect()
            except: pass
            
                                                            
            old_worker = self.worker
            self._old_workers.append(old_worker)
            old_worker.finished.connect(lambda: self.cleanup_worker(old_worker))
            self.worker = None

        self.results_tree.clear()
        self.search_btn.setEnabled(False)
        self.current_search_query = query
        
        self.worker = SearchWorker(query, site=site_key)
        self.worker.finished.connect(self.on_search_finished)
        self.worker.error.connect(lambda e: self.log(f"Search Error: {e}"))
        self.worker.start()

    def on_search_finished(self, results):
        self.search_btn.setEnabled(True)
        self.search_results = results
        self.log(f"Found {len(results)} results.")
        self.results_label.setText(f"Search Results ({len(results)})")
        self.refresh_titles()

    def on_manga_selected(self):
        selected_items = self.results_tree.selectedItems()
        if not selected_items: return
        
                                               
        if hasattr(self, 'img_loader') and self.img_loader and self.img_loader.isRunning():
            self.img_loader.requestInterruption()
            try: self.img_loader.loaded.disconnect()
            except: pass
            
            old_loader = self.img_loader
            self._old_workers.append(old_loader)
            old_loader.finished.connect(lambda: self.cleanup_worker(old_loader))
            self.img_loader = None
            
                                                  
        if hasattr(self, 'chap_worker') and self.chap_worker and self.chap_worker.isRunning():
            self.chap_worker.requestInterruption()
            try: self.chap_worker.finished.disconnect()
            except: pass
            try: self.chap_worker.error.disconnect()
            except: pass
            
            old_chap = self.chap_worker
            self._old_workers.append(old_chap)
            old_chap.finished.connect(lambda: self.cleanup_worker(old_chap))
            self.chap_worker = None

                                
        idx = self.results_tree.indexOfTopLevelItem(selected_items[0])
        if idx < 0 or idx >= len(self.search_results): return
        
        self.selected_manga = self.search_results[idx]
        display_title = self.get_preferred_title(self.selected_manga)
        
        self.title_label.setText(f"{display_title} ({self.selected_manga['status']})")
        self.desc_text.setText(self.selected_manga['description'])
        
               
        self.cover_label.setText("Loading...")
                                                               
        self.cover_label.setPixmap(QPixmap()) 
        
        if self.selected_manga.get('cover_url'):
             url = self.selected_manga['cover_url']
             self.img_loader = ImageLoader(url)
             self.img_loader.loaded.connect(self.set_cover_image)
             self.img_loader.start()
        elif self.selected_manga.get('cover_filename'):
            url = f"https://uploads.mangadex.org/covers/{self.selected_manga['id']}/{self.selected_manga['cover_filename']}.256.jpg"
            self.img_loader = ImageLoader(url)
            self.img_loader.loaded.connect(self.set_cover_image)
            self.img_loader.start()
        else:
            self.cover_label.setText("No Cover")

                   
        self.lang_list.blockSignals(True)                                            
        self.lang_list.clear()
        langs = sorted([l for l in self.selected_manga.get("available_languages", []) if l])
        if not langs:
            self.lang_list.addItem("No specific langs listed")
        else:
            self.lang_list.addItems(langs)
        self.lang_list.blockSignals(False)
        
                        
        self.chapter_tree.clear()
        self.chapters = []
        self.all_chapter_groups = set()
        self.loaded_label.setText("")                               
        
                                
        if not langs:
            self.fetch_chapters()

    def select_chapter_range(self):
        start_str = self.range_start.text().strip()
        end_str = self.range_end.text().strip()
        
        if not start_str or not end_str:
            return
            
        try:
            start_num = float(start_str)
            end_num = float(end_str)
            
                                  
            if start_num > end_num:
                start_num, end_num = end_num, start_num
                
            count = 0
            for i in range(self.chapter_tree.topLevelItemCount()):
                item = self.chapter_tree.topLevelItem(i)
                                                           
                try:
                    chap_val = float(item.text(0))
                    if start_num <= chap_val <= end_num:
                        item.setCheckState(0, Qt.Checked)
                        count += 1
                except ValueError:
                                                                           
                    pass
            
            self.log(f"Selected {count} chapters in range {start_num}-{end_num}")
            
        except ValueError:
            QMessageBox.warning(self, "Invalid Range", "Please enter valid numbers for the range.")


    def set_cover_image(self, image):
        self.cover_label.set_pixmap(QPixmap.fromImage(image))

    def on_lang_changed(self):
        selected_langs = [item.text() for item in self.lang_list.selectedItems()]
        if "No specific langs listed" in selected_langs: selected_langs = None
        self.fetch_chapters(selected_langs)

    def fetch_chapters(self, langs=None):
        if not self.selected_manga: return
        self.log(f"Fetching chapters...")
        self.loaded_label.setText("Fetching chapters...")
        self.chapter_tree.clear()
        
        site = self.selected_manga.get("source", "mangadex")
        self.chap_worker = ChapterWorker(self.selected_manga['id'], langs, site=site)
        self.chap_worker.finished.connect(self.on_chapters_fetched)
        self.chap_worker.error.connect(lambda e: self.log(f"Chapter Error: {e}"))
        self.chap_worker.start()

    def on_chapters_fetched(self, chapters):
        self.chapters = chapters
        self.log(f"Loaded {len(chapters)} chapters.")
        self.loaded_label.setText(f"Loaded {len(chapters)} chapters")
        self.all_chapter_groups = set()
        
        for c in chapters:
            groups = c.get('groups', [])
            if not groups:
                self.all_chapter_groups.add("No Group")
            else:
                for g in groups:
                    self.all_chapter_groups.add(g)

            item = QTreeWidgetItem([
                str(c.get('chapter') or "Oneshot"),
                c.get('title') or "",
                c.get('language', '??'),
                ", ".join(groups) if groups else "No Group",
                format_date(c.get('publishAt'))
            ])
            item.setData(0, Qt.UserRole, c)                          
                                              
            item.setCheckState(0, Qt.Unchecked)
            self.chapter_tree.addTopLevelItem(item)

    def open_group_filter(self):
        if not self.all_chapter_groups:
            QMessageBox.information(self, "No Groups", "No groups found in current chapter list.")
            return
            
        dlg = GroupFilterDialog(self.all_chapter_groups, self)
        if dlg.exec() == QDialog.Accepted:
            selected = dlg.get_selected_groups()
            self.apply_group_filter(selected)

    def apply_group_filter(self, selected_groups):
        root = self.chapter_tree.invisibleRootItem()
        selected_set = set(selected_groups)
        
        for i in range(root.childCount()):
            item = root.child(i)
            chapter_data = item.data(0, Qt.UserRole)
            c_groups = chapter_data.get('groups', [])
            
            match = False
            if not c_groups:
                if "No Group" in selected_set:
                    match = True
            else:
                                                     
                if set(c_groups).intersection(selected_set):
                    match = True
            
            item.setHidden(not match)


    def select_all_chapters(self):
        for i in range(self.chapter_tree.topLevelItemCount()):
            self.chapter_tree.topLevelItem(i).setCheckState(0, Qt.Checked)

    def deselect_all_chapters(self):
        for i in range(self.chapter_tree.topLevelItemCount()):
            self.chapter_tree.topLevelItem(i).setCheckState(0, Qt.Unchecked)

    def invert_chapters(self):
        for i in range(self.chapter_tree.topLevelItemCount()):
            item = self.chapter_tree.topLevelItem(i)
            state = item.checkState(0)
            item.setCheckState(0, Qt.Unchecked if state == Qt.Checked else Qt.Checked)

    def start_download(self):
        selected_chapters = []
        for i in range(self.chapter_tree.topLevelItemCount()):
            item = self.chapter_tree.topLevelItem(i)
            if item.checkState(0) == Qt.Checked:
                selected_chapters.append(item.data(0, Qt.UserRole))
        
        if not selected_chapters:
            QMessageBox.warning(self, "No Selection", "Please select chapters to download.")
            return

        default_dir = self.settings.get("last_dir", "")
        base_dir = QFileDialog.getExistingDirectory(self, "Select Download Directory", default_dir)
        if not base_dir: return
        self.settings["last_dir"] = base_dir
        
                                      
        display_title = self.get_preferred_title(self.selected_manga)
        safe_title = "".join(c for c in display_title if c.isalnum() or c in (' ', '-', '_')).strip()
        manga_dir = Path(base_dir) / safe_title
        manga_dir.mkdir(parents=True, exist_ok=True)

        self.download_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.log_text.setVisible(True)                           
        self.progress_bar.setValue(0)
        
        site = self.selected_manga.get("source", "mangadex")
        self.download_worker = DownloadWorker(
            selected_chapters, 
            str(manga_dir), 
            self.data_saver_chk.isChecked(),
            manga_id=self.selected_manga['id'],
            make_cbz=self.cbz_chk.isChecked(),
            site=site
        )
        self.download_worker.progress.connect(self.log)
        self.download_worker.percent.connect(self.progress_bar.setValue)
        self.download_worker.finished.connect(self.on_download_finished)
        self.download_worker.error.connect(lambda e: self.log(f"Download Error: {e}"))
        self.download_worker.start()

    def on_download_finished(self):
        self.download_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.log_text.setVisible(False)
        self.log("Download complete!")
        QMessageBox.information(self, "Success", "All selected chapters have been downloaded.")

                                

    def load_settings(self):
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r") as f: return json.load(f)
        except: pass
        return {}

    def save_settings(self):
        self.settings["romaji_titles"] = self.romaji_chk.isChecked()
        self.settings["data_saver"] = self.data_saver_chk.isChecked()
        self.settings["cbz_mode"] = self.cbz_chk.isChecked()
        try:
            with open(SETTINGS_FILE, "w") as f: json.dump(self.settings, f)
        except: pass

    def load_library(self):
        try:
            if os.path.exists(LIBRARY_FILE):
                with open(LIBRARY_FILE, "r") as f: return json.load(f)
        except: pass
        return {}

    def save_library(self):
        try:
            with open(LIBRARY_FILE, "w") as f: json.dump(self.library, f)
        except: pass

    def closeEvent(self, event):
                                         
        workers = [
            getattr(self, 'worker', None),
            getattr(self, 'img_loader', None),
            getattr(self, 'chap_worker', None)
        ]
        for w in workers:
            if w and w.isRunning():
                w.requestInterruption()
                w.wait(50)

        if hasattr(self, 'download_worker') and self.download_worker and self.download_worker.isRunning():
            self.download_worker.stop()
            self.download_worker.wait(100)

        self.save_settings()
        self.save_library()
        event.accept()

    def open_library(self):
        dlg = LibraryDialog(self.library, self)
        dlg.exec()
        self.save_library()

    def add_current_to_library(self):
        if not self.selected_manga: 
            QMessageBox.warning(self, "No Manga", "Please select a manga first.")
            return
        
        mid = self.selected_manga['id']
        title = self.get_preferred_title(self.selected_manga)
        source = self.selected_manga.get('source', 'mangadex')
        cover_url = self.selected_manga.get('cover_url') or self.selected_manga.get('cover_filename')
        
        self.library[mid] = {
            "title": title,
            "added_at": time.time(),
            "last_chapter": "", 
            "has_update": False,
            "source": source,
            "cover_url": cover_url
        }
        self.save_library()
        QMessageBox.information(self, "Library", f"Added '{title}' to library.")

    def load_manga_from_library(self, mid):
        data = self.library.get(mid, {})
        source = data.get('source', 'mangadex').lower()
        
        if source == 'baozimh':
            self.site_combo.setCurrentText("Baozimh")
            fake_url = f"https://www.baozimh.com/comic/{mid}"
            self.search_input.setText(fake_url)
        elif source == 'happymh':
            self.site_combo.setCurrentText("Happymh")
            fake_url = f"https://m.happymh.com/manga/{mid}"
            self.search_input.setText(fake_url)
        elif source == 'rawkuma':
            self.site_combo.setCurrentText("Rawkuma")
            self.search_input.setText(mid) # mid is the full URL for Rawkuma
        else:
            self.site_combo.setCurrentText("MangaDex")
            fake_url = f"https://mangadex.org/title/{mid}"
            self.search_input.setText(fake_url)
            
        self.start_search()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ModernMangaDexGUI()
    window.show()
    sys.exit(app.exec())