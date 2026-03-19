import asyncio
import sys
import re
import json
from playwright.async_api import async_playwright

async def fetch_html_playwright(url):
    async with async_playwright() as p:
        # Launch browser with stealth-like arguments
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 1600},
            extra_http_headers={
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
        )
        
        page = await context.new_page()
        
        captured_data = {
            "images": [],
            "json_responses": [],
            "js_variables": {}
        }
        
        # Intercept network requests
        async def handle_response(response):
            try:
                content_type = response.headers.get("content-type", "").lower()
                if "image" in content_type:
                    if "happymh.com" in response.url or "ruicdn" in response.url:
                        captured_data["images"].append(response.url)
                elif "json" in content_type:
                    # Look for chapter or manga data in JSON
                    if any(x in response.url for x in ["chapter", "manga", "reader"]):
                        try:
                            text = await response.text()
                            captured_data["json_responses"].append({
                                "url": response.url,
                                "content": text
                            })
                        except: pass
            except:
                pass
        
        page.on("response", handle_response)
        
        try:
            # Navigate and wait
            print(f"Playwright: Navigating to {url}...", file=sys.stderr)
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # Wait for potential challenges (Cloudflare)
            await asyncio.sleep(10)
            
            # Extract common Happymh JS variables
            js_script = """
            () => {
                const results = {};
                // Look for common data variables
                const vars = ['__NEXT_DATA__', '__INITIAL_STATE__', 'chapterData', 'mangaData', 'pages'];
                vars.forEach(v => {
                    if (window[v]) {
                        try {
                            results[v] = JSON.stringify(window[v]);
                        } catch(e) {}
                    }
                });
                
                // Also look for data in script tags
                const scripts = document.querySelectorAll('script');
                scripts.forEach((s, i) => {
                    if (s.textContent && (s.textContent.includes('pages') || s.textContent.includes('url'))) {
                        results['script_' + i] = s.textContent;
                    }
                });
                
                // Extract canvas data if present
                const canvases = document.querySelectorAll('canvas');
                canvases.forEach((c, i) => {
                    try {
                        results['canvas_' + i] = c.toDataURL('image/jpeg', 0.8);
                    } catch(e) {}
                });
                
                return results;
            }
            """
            captured_data["js_variables"] = await page.evaluate(js_script)
            
            # Scroll to trigger lazy loading
            for _ in range(15):
                await page.mouse.wheel(0, 3000)
                await asyncio.sleep(1.5)
            
            # Final capture of rendered content
            content = await page.content()
            
            # Embed all captured data in a hidden div
            embed_script = f"""
            const div = document.createElement('div');
            div.id = 'extra_captured_data';
            div.style.display = 'none';
            div.textContent = {json.dumps(json.dumps(captured_data))};
            document.body.appendChild(div);
            """
            await page.evaluate(embed_script)
            content = await page.content()
            
            return content
            
        except Exception as e:
            print(f"Playwright Error: {e}", file=sys.stderr)
            return None
        finally:
            await browser.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        url = sys.argv[1]
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(fetch_html_playwright(url))
            if result:
                # Print the entire result without filtering <html> tags
                print(result)
        except Exception as e:
            print(f"Error in main: {e}", file=sys.stderr)
