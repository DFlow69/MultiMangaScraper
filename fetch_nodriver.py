import nodriver as uc
import asyncio
import sys
import re

async def fetch_html_nodriver(url):
    try:
        browser = await uc.start()
        try:
            page = await browser.get(url)
            # Wait for content
            await page.wait(8) 
            
            try:
                await page.wait_for("a[href*='/mangaread/'], .mg-content img, .reader-content img, div[class*='-imgContainer'] img, img[id^='scan'], .mg-title, h1", timeout=20)
            except:
                pass
                
            # Scroll for reader pages
            if "/mangaread/" in url:
                for _ in range(5):
                    await page.evaluate("window.scrollBy(0, 2000);")
                    await page.wait(1.5)
            
            content = await page.get_content()
            return content
        finally:
            await browser.stop()
    except Exception as e:
        print(f"Nodriver Error: {e}", file=sys.stderr)
        return None

if __name__ == "__main__":
    if len(sys.argv) > 1:
        url = sys.argv[1]
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(fetch_html_nodriver(url))
            if result:
                # Print the entire result without filtering <html> tags
                print(result)
        except Exception as e:
            print(f"Error in main: {e}", file=sys.stderr)
