import json
import time
import random
import pandas as pd
from playwright.sync_api import sync_playwright

COOKIES_FILE = "www.facebook.com_cookies.json"
PAGE_NAME = "ETClub.UEH"
LINK_OUTPUT = "facebook_links_desktop.csv"
MAX_SCROLL = 1000
HEADLESS_MODE = False

def load_cookies(context):
    with open(COOKIES_FILE, "r") as f:
        cookies = json.load(f)
    for c in cookies:
        if c.get("sameSite") not in ["Strict", "Lax", "None"]:
            c["sameSite"] = "Lax"
    context.add_cookies(cookies)

def scroll_and_collect_links(page, max_scrolls=MAX_SCROLL):
    links = set()
    prev_count = 0
    idle_rounds = 0
    for i in range(1, max_scrolls + 1):
        page.mouse.wheel(0, random.randint(3000, 4000))
        time.sleep(random.uniform(3, 4))
        anchors = page.query_selector_all("a[href*='/posts/']")
        new_links = [a.get_attribute("href") for a in anchors if a.get_attribute("href")]
        full_links = ["https://www.facebook.com" + link if link.startswith("/") else link for link in new_links]
        links.update(full_links)
        print(f"📥 Lần {i}, đã thấy {len(links)} link")
        if len(links) == prev_count:
            idle_rounds += 1
        else:
            idle_rounds = 0
        prev_count = len(links)
        if idle_rounds >= 5:
            print("🛑 Không còn bài mới, dừng cuộn.")
            break
    return list(links)

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS_MODE, slow_mo=100)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="en-US"
        )
        context.route("**/*", lambda r: r.abort() if r.request.resource_type in ["image", "media", "font"] else r.continue_())
        load_cookies(context)

        page = context.new_page()
        page_url = f"https://www.facebook.com/{PAGE_NAME}/posts"
        print(f"🌐 Truy cập page: {page_url}")
        page.goto(page_url, timeout=30000)
        time.sleep(5)

        links = scroll_and_collect_links(page, MAX_SCROLL)

        if links:
            pd.DataFrame({"post_links": links}).to_csv(LINK_OUTPUT, index=False)
            print(f"✅ Đã lưu {len(links)} link vào {LINK_OUTPUT}")
        else:
            print("⚠️ Không thu được link nào!")

        browser.close()

if __name__ == "__main__":
    run()
