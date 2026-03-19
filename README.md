# MangaDex Scraper & GUI

A feature-rich, dual-interface (GUI & TUI) application to search, view, and download manga chapters from **MangaDex**, **Baozimh**, and **Happymh**.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)

## Features

- **Dual Interface**:
  - **GUI**: Modern, scalable Qt-based interface with dark mode, cover previews, and advanced filtering.
  - **TUI**: Keyboard-centric terminal interface for fast, lightweight usage.
- **Multi-Site Support**:
  - **MangaDex**: Default provider with full metadata and search.
  - **Baozimh**: Specialized for Chinese manga with smart image extraction.
  - **Happymh**: Advanced Cloudflare bypass and multi-fallback image extraction.
- **Advanced Scraping & Bypassing**:
  - **Cloudflare Bypass**: Multi-layered fallback system using `curl_cffi`, `nodriver`, `SeleniumBase UC Mode`, and `Playwright`.
  - **Image Extraction**: Supports standard tags, JSON metadata, network interception, and direct `<canvas>` decoding.
  - **Referer Spoofing**: Automatically handles site-specific referer requirements for image servers.
- **Library & Tracking**:
  - **Library**: Save your favorite manga to a local library.
  - **Update Checker**: Quickly see if new chapters are available.
  - **Settings**: Persistent preferences for download path, data saver, and more.
- **Smart Search**: 
  - Search by title (English/Romaji support).
  - **URL Import**: Paste a URL from any supported site to instantly load a manga.
  - **AniList Bridge**: Automatic English-to-Chinese title lookup for accurate searching on Chinese sites.
- **Flexible Downloading**:
  - **CBZ Archiving**: Option to save chapters as `.cbz` files.
  - **Data Saver**: Option to use compressed images to save bandwidth.
  - **Interactive Selection**: Pick specific chapters manually or by range.
  - **Group Filtering**: Filter chapters by Scanlation Group.
- **Resilient**:
  - Threaded downloads to keep the UI responsive.
  - Automatic retry on failed pages.
  - Rate limit handling.

## Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/DFlow69/MangaDex-Scraper.git
    cd MangaDex-Scraper
    ```

2.  **Install Dependencies**:
    You can run the provided PowerShell script:
    ```powershell
    ./install_requirements.ps1
    ```
    Or install manually via pip:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Setup Browsers (for Happymh bypass)**:
    ```bash
    playwright install chromium
    ```

## Usage

> [!TIP]
> **Best Practice**: For maximum reliability (especially with **Happymh**), it is highly recommended to paste the **exact series URL** directly into the search bar instead of searching by title. This bypasses search result obfuscation and goes straight to the chapter list.

### Graphical User Interface (GUI)
- **Python**:
  ```bash
  python md_gui.py
  ```

### Terminal User Interface (TUI)
- **Batch**: Double-click `run_tui.bat`
- **Python**:
  ```bash
  python md.py
  ```

## Building from Source

To create a standalone executable:

```bash
pip install pyinstaller
pyinstaller --clean --onefile --noconsole --name MangaDexGUI md_gui.py
```

## Disclaimer

This tool is for educational purposes and personal use only. Please respect the copyrights of the manga creators and publishers.
