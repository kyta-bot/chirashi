"""
scraper.py
トクバイから3店舗の特売情報を取得してSupabaseに保存する
"""

import re
import time
from datetime import date

import requests
from bs4 import BeautifulSoup

# ──────────────────────────────────────────
# Supabase設定
# ──────────────────────────────────────────
SUPABASE_URL = "https://wydjiqortlsvbtwswckd.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind5ZGppcW9ydGxzdmJ0d3N3Y2tkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ2NzYxOTIsImV4cCI6MjA5MDI1MjE5Mn0.8PLeUVhuUzMMTySqfinhr6Ne1UJpp_SqvSDATmAck1k"

HEADERS_SUPA = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=ignore-duplicates",
}

# ──────────────────────────────────────────
# 店舗リスト
# ──────────────────────────────────────────
STORES = {
    "タイヨー学園の森店": "https://tokubai.co.jp/%E3%82%BF%E3%82%A4%E3%83%A8%E3%83%BC/58365",
    "ブランデ研究学園店": "https://tokubai.co.jp/%E3%83%96%E3%83%A9%E3%83%B3%E3%83%87/227498",
    "カスミ学園の森店":   "https://tokubai.co.jp/%E3%82%AB%E3%82%B9%E3%83%9F/14342",
}

HEADERS_WEB = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
}

# ──────────────────────────────────────────
# スクレイプ
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
# Supabaseに保存
# ──────────────────────────────────────────
def save_to_supabase(products):
    if not products:
        return 0
    res = requests.post(
        f"{SUPABASE_URL}/rest/v1/prices",
        headers=HEADERS_SUPA,
        json=products,
        timeout=15,
    )
    if res.status_code in (200, 201):
        print(f"  → Supabase保存: {len(products)} 件")
        return len(products)
    else:
        print(f"  [ERROR] Supabase保存失敗: {res.status_code} {res.text[:200]}")
        return 0

# ──────────────────────────────────────────
# メイン
# ──────────────────────────────────────────
def run():
    today = date.today().isoformat()
    print(f"\n=== {today} 収集開始 ===")

    total = 0
    for store_name, url in STORES.items():
        print(f"\n▶ {store_name}")
        products = fetch_products(store_name, url)
        saved = save_to_supabase(products)
        total += saved
        time.sleep(2)

    print(f"\n=== 完了: 合計 {total} 件 ===\n")


if __name__ == "__main__":
    run()
