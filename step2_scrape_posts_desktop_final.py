import json
import re
import time
import random
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from playwright.sync_api import sync_playwright

COOKIES_FILE = "www.facebook.com_cookies.json"
LINK_INPUT = "facebook_links_desktop.csv"
CSV_OUTPUT = "facebook_activities_desktop.csv"
HEADLESS_MODE = False
MAX_RETRY = 2

def load_cookies(context):
    with open(COOKIES_FILE, "r") as f:
        cookies = json.load(f)
    for c in cookies:
        if c.get("sameSite") not in ["Strict", "Lax", "None"]:3
        c["sameSite"] = "Lax"
    context.add_cookies(cookies)

def extract_title_and_category(content):
    matches = re.findall(r"\[(.*?)\]", content)
    activity_category = matches[0].strip() if len(matches) > 0 else "Không xác định"
    title = matches[1].strip() if len(matches) > 1 else content[:60]
    return activity_category, title

def extract_dates_and_money(content):
    date_pattern = r"(\d{1,2}/\d{1,2}/\d{4})"
    money_pattern = r"([0-9.,]+(?:đ|vnđ|VND))"
    dates = re.findall(date_pattern, content)
    money = re.findall(money_pattern, content)
    start_date = dates[0] if len(dates) > 0 else None
    end_date = dates[1] if len(dates) > 1 else None
    expense = money[0] if money else None
    return start_date, end_date, expense

def parse_post(html, index, url):
    soup = BeautifulSoup(html, "html.parser")
    content_div = soup.select_one("div[data-ad-comet-preview='message']") or soup.select_one("div[role='article']")
    content = content_div.get_text(strip=True) if content_div else ""

    img = soup.find("img", {"referrerpolicy": "origin-when-cross-origin"})
    image_url = img["src"] if img else ""

    time_text = ""
    time_tag = soup.find("a", href=re.compile("/posts/"))
    if time_tag:
        time_text = time_tag.get("aria-label", "")

    try:
        created_on = datetime.strptime(time_text, "%A, %B %d, %Y at %I:%M %p").isoformat()
    except:
        created_on = datetime.now().isoformat()

    activity_category, title = extract_title_and_category(content)
    start_date, end_date, expense_money = extract_dates_and_money(content)

    return {
        "activity_id": f"FB{str(index+1).zfill(5)}",
        "title": title,
        "activity_category": activity_category,
        "meta_description": content[:160],
        "thumbnail_image_url": image_url,
        "start_date": start_date,
        "end_date": end_date,
        "register_number": None,
        "participated_number": None,
        "expense_money": expense_money,
        "visible": True,
        "content": content,
        "viewCount": None,
        "created_on": created_on,
        "last_modified_on": created_on,
        "permalink_url": url
    }

def wait_until_correct_post_loaded(page, expected_url, max_wait=20):
    for _ in range(max_wait * 2):
        current_url = page.url
        if expected_url.split('?')[0] in current_url:
            return True
        time.sleep(0.5)
    return False

def run():
    links_df = pd.read_csv(LINK_INPUT)
    links = links_df["post_links"].tolist()

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
        results = []

        for i, link in enumerate(links):
            print(f"\n📥 Bài {i+1}/{len(links)}: {link}")
            for retry in range(1, MAX_RETRY + 1):
                try:
                    page.goto(link, timeout=40000)
                    print(f"➡️ Đã vào URL: {page.url}")
                    if not wait_until_correct_post_loaded(page, link):
                        raise Exception("⛔ Sai bài viết (redirect hoặc fail)")
                    page.wait_for_selector("div[data-ad-comet-preview='message'], div[role='article']", timeout=15000)
                    time.sleep(random.uniform(3, 5))
                    html = page.content()
                    act = parse_post(html, i, link)
                    results.append(act)
                    print(f"✅ Thành công ở lần thử {retry}")
                    break
                except Exception as e:
                    print(f"⚠️ Lỗi lần {retry}: {e}")
            else:
                print(f"❌ Bỏ qua bài {i+1}")

        pd.DataFrame(results).to_csv(CSV_OUTPUT, index=False)
        print(f"\n🎯 Hoàn tất: Đã lưu {len(results)} bài viết vào {CSV_OUTPUT}")
        browser.close()

if __name__ == "__main__":
    run()