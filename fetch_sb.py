from seleniumbase import SB
from selenium_stealth import stealth
import sys
import time
import re
import json

def fetch_html_sb(url):
    try:
        with SB(uc=True, headless=True, timeout=120) as sb:
            # Apply stealth
            stealth(sb.driver,
                languages=["zh-CN", "zh", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
            )
            
            sb.uc_open_with_reconnect(url, 15)
            
            # Wait for content
            try:
                sb.wait_for_element_present("a[href*='/mangaread/'], .mg-content img, .reader-content img, div[class*='-imgContainer'] img, img[id^='scan'], .mg-title, h1, canvas", timeout=40)
            except:
                pass
            
            captured_data = {
                "images": [],
                "json_responses": [],
                "js_variables": {}
            }

            if "/mangaread/" in url:
                # Scroll to trigger lazy loading
                last_height = sb.execute_script("return document.body.scrollHeight")
                for _ in range(15):
                    sb.execute_script("window.scrollBy(0, 3500);")
                    sb.sleep(2)
                    new_height = sb.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        sb.execute_script("window.scrollBy(0, 1500);")
                        sb.sleep(1.5)
                        if sb.execute_script("return document.body.scrollHeight") == new_height:
                            break
                    last_height = new_height
                
                # Extract data via JS
                script = """
                () => {
                    const results = {};
                    const vars = ['__NEXT_DATA__', '__INITIAL_STATE__', 'chapterData', 'mangaData', 'pages'];
                    vars.forEach(v => {
                        if (window[v]) {
                            try {
                                results[v] = JSON.stringify(window[v]);
                            } catch(e) {}
                        }
                    });
                    
                    const imgs = document.querySelectorAll('img');
                    const imgUrls = [];
                    imgs.forEach(img => {
                        const src = img.src || img.dataset.src || img.dataset.original;
                        if (src && src.startsWith('http')) imgUrls.push(src);
                    });
                    results['_imgs'] = imgUrls;

                    const canvases = document.querySelectorAll('canvas');
                    canvases.forEach((c, i) => {
                        try {
                            results['canvas_' + i] = c.toDataURL('image/jpeg', 0.8);
                        } catch(e) {}
                    });
                    return results;
                }
                """
                res = sb.execute_script(script)
                captured_data["js_variables"] = res
                captured_data["images"] = res.get('_imgs', [])

            sb.sleep(3)
            content = sb.get_page_source()
            
            # Embed captured data
            if captured_data:
                sb.execute_script(f"""
                    const div = document.createElement('div');
                    div.id = 'extra_captured_data';
                    div.style.display = 'none';
                    div.textContent = {json.dumps(json.dumps(captured_data))};
                    document.body.appendChild(div);
                """)
                content = sb.get_page_source()

            return content
            
    except Exception as e:
        print(f"SeleniumBase Error: {e}", file=sys.stderr)
        return None

if __name__ == "__main__":
    if len(sys.argv) > 1:
        url = sys.argv[1]
        result = fetch_html_sb(url)
        if result:
            # Print the entire result without filtering <html> tags
            print(result)
