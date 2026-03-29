"""
scraper.py
トクバイから特売テキスト＋チラシ画像URLを取得してSupabaseに保存する
"""

import os
import re
import time
from datetime import date

import requests
from bs4 import BeautifulSoup

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

HEADERS_SUPA = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=ignore-duplicates",
}

HEADERS_WEB = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
}

# ── 特売テキスト取得対象（3店舗）──
TEXT_STORES = {
    "タイヨー学園の森店": "https://tokubai.co.jp/%E3%82%BF%E3%82%A4%E3%83%A8%E3%83%BC/58365",
    "ブランデ研究学園店": "https://tokubai.co.jp/%E3%83%96%E3%83%A9%E3%83%B3%E3%83%87/227498",
    "カスミ学園の森店":   "https://tokubai.co.jp/%E3%82%AB%E3%82%B9%E3%83%9F/14342",
}

# ── チラシ画像取得対象（6店舗）──
FLYER_STORES = {
    "タイヨー学園の森店":       "https://tokubai.co.jp/%E3%82%BF%E3%82%A4%E3%83%A8%E3%83%BC/58365",
    "ブランデ研究学園店":       "https://tokubai.co.jp/%E3%83%96%E3%83%A9%E3%83%B3%E3%83%87/227498",
    "カスミ学園の森店":         "https://tokubai.co.jp/%E3%82%AB%E3%82%B9%E3%83%9F/14342",
    "カスミイーアスつくば店":   "https://tokubai.co.jp/%E3%82%AB%E3%82%B9%E3%83%9F/8190",
    "ロピアトナリエクレオ店":   "https://tokubai.co.jp/%E3%83%AD%E3%83%94%E3%82%A2/255387",
    "タイラヤつくば大穂店":     "https://tokubai.co.jp/TAIRAYA/16895",
}

# ──────────────────────────────────────────
# 特売テキスト取得
# ──────────────────────────────────────────
def fetch_products(store_name, url):
    try:
        res = requests.get(url, headers=HEADERS_WEB, timeout=15)
        res.raise_for_status()
    except Exception as e:
        print(f"  [ERROR] {store_name} 取得失敗: {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    products = []

    for a in soup.select("a[href*='/products/office_featured_product_']"):
        item = _first_text(a)
        if not item:
            continue
        price_texts = [s.get_text(strip=True) for s in a.select("span, p")
                       if re.search(r"\d+円", s.get_text())]
        price_tax, price_notax = _parse_prices(price_texts)
        unit = _extract_unit(a)
        note = _extract_note(a)
        products.append({
            "store":       store_name,
            "item":        item.strip(),
            "price_tax":   price_tax,
            "price_notax": price_notax,
            "unit":        unit,
            "note":        note,
            "date":        date.today().isoformat(),
        })

    print(f"  [{store_name}] {len(products)} 品取得")
    return products


def _first_text(tag):
    for s in tag.strings:
        t = s.strip()
        if t and not re.search(r"\d+円|税込|税抜|当日|限り|イチオシ", t):
            return t
    return ""


def _parse_prices(texts):
    tax_in = tax_out = None
    for t in texts:
        nums = re.findall(r"[\d,]+(?=円)", t)
        if not nums:
            continue
        val = int(nums[0].replace(",", ""))
        if "税込" in t:
            tax_in = val
        else:
            tax_out = val
    return tax_in, tax_out


def _extract_unit(tag):
    for s in tag.stripped_strings:
        if re.search(r"[ｇgkKlL個コ本袋パック枚入当り]", s) and len(s) < 30:
            return s.strip()
    return ""


def _extract_note(tag):
    keywords = ["当日限り", "イチオシ", "お一人様", "数量限定", "先着"]
    for s in tag.stripped_strings:
        for kw in keywords:
            if kw in s:
                return kw
    return ""

# ──────────────────────────────────────────
# チラシ画像URL取得
# ──────────────────────────────────────────
def fetch_flyers(store_name, url):
    try:
        res = requests.get(url, headers=HEADERS_WEB, timeout=15)
        res.raise_for_status()
    except Exception as e:
        print(f"  [ERROR] {store_name} チラシ取得失敗: {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    flyers = []
    today = date.today().isoformat()

    # チラシページへのリンクを取得
    leaflet_links = []
    for a in soup.select("a[href*='/leaflets/']"):
        href = a.get("href", "")
        if "/leaflets/" in href and href not in leaflet_links:
            leaflet_links.append(href)

    # 各チラシページから画像URLを取得
    for i, link in enumerate(leaflet_links[:3]):  # 最大3チラシ
        full_url = f"https://tokubai.co.jp{link}" if link.startswith("/") else link
        try:
            r2 = requests.get(full_url, headers=HEADERS_WEB, timeout=15)
            soup2 = BeautifulSoup(r2.text, "html.parser")

            # メイン画像を取得
            for img in soup2.select("img[src*='bargain_office_leaflets'], img[src*='bargain_leaflets']"):
                src = img.get("src", "")
                if "o=true" in src or "/o=true/" in src:
                    # 有効期間テキストを取得
                    valid_text = ""
                    for alt in [img.get("alt", ""), soup2.title.text if soup2.title else ""]:
                        if "まで" in alt or "〜" in alt:
                            valid_text = alt
                            break

                    flyers.append({
                        "store":        store_name,
                        "image_url":    src,
                        "page_num":     i + 1,
                        "valid_from":   "",
                        "valid_to":     valid_text,
                        "fetched_date": today,
                    })
                    break
            time.sleep(1)
        except Exception as e:
            print(f"  [WARN] チラシページ取得失敗: {e}")

    print(f"  [{store_name}] チラシ {len(flyers)} 枚取得")
    return flyers

# ──────────────────────────────────────────
# Supabaseに保存
# ──────────────────────────────────────────
def save_to_supabase(table, records):
    if not records:
        return 0
    res = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=HEADERS_SUPA,
        json=records,
        timeout=15,
    )
    if res.status_code in (200, 201):
        print(f"  → {table} 保存: {len(records)} 件")
        return len(records)
    else:
        print(f"  [ERROR] {table} 保存失敗: {res.status_code} {res.text[:200]}")
        return 0

# ──────────────────────────────────────────
# メイン
# ──────────────────────────────────────────
def run():
    today = date.today().isoformat()
    print(f"\n=== {today} 収集開始 ===")

    # 特売テキスト取得
    print("\n--- 特売テキスト取得 ---")
    for store_name, url in TEXT_STORES.items():
        print(f"\n▶ {store_name}")
        products = fetch_products(store_name, url)
        save_to_supabase("prices", products)
        time.sleep(2)

    # チラシ画像取得
    print("\n--- チラシ画像取得 ---")
    for store_name, url in FLYER_STORES.items():
        print(f"\n▶ {store_name}")
        flyers = fetch_flyers(store_name, url)
        save_to_supabase("flyers", flyers)
        time.sleep(2)

    print(f"\n=== 完了 ===\n")


if __name__ == "__main__":
    run()
