"""楽天市場商品検索API クライアント(2026年の新エンドポイント対応)"""
import os
import re
import time

import requests

ENDPOINT = os.getenv(
    "RAKUTEN_ENDPOINT",
    "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20220601",
)


def _first_image(item):
    imgs = item.get("mediumImageUrls") or []
    if not imgs:
        return ""
    first = imgs[0]
    return first.get("imageUrl", "") if isinstance(first, dict) else str(first)


def _clean(text, n=300):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()[:n]


def normalize(raw):
    """formatVersion 1({"Item": {...}})と2(フラット)の両方を吸収"""
    it = raw.get("Item", raw)
    return {
        "code": it.get("itemCode", ""),
        "name": _clean(it.get("itemName"), 120),
        "price": int(it.get("itemPrice") or 0),
        "url": it.get("affiliateUrl") or it.get("itemUrl") or "",
        "image": _first_image(it),
        "shop": it.get("shopName", ""),
        "review_avg": float(it.get("reviewAverage") or 0),
        "review_count": int(it.get("reviewCount") or 0),
        "caption": _clean(it.get("itemCaption")),
        "available": str(it.get("availability", 1)) == "1",
    }


def _get(params):
    full = {
        "format": "json",
        "formatVersion": 2,
        "applicationId": os.environ["RAKUTEN_APP_ID"],
        "accessKey": os.environ["RAKUTEN_ACCESS_KEY"],
        **params,
    }
    if os.getenv("RAKUTEN_AFFILIATE_ID"):
        full["affiliateId"] = os.environ["RAKUTEN_AFFILIATE_ID"]
    headers = {"Referer": os.getenv("RAKUTEN_REFERER", "https://example.com")}

    r = requests.get(ENDPOINT, params=full, headers=headers, timeout=15)
    if r.status_code in (401, 403):
        raise RuntimeError(
            f"楽天API認証エラー({r.status_code}): アプリID/アクセスキー、および "
            "アプリ登録時の許可URLと RAKUTEN_REFERER の一致を確認してください"
        )
    r.raise_for_status()
    time.sleep(1.1)  # 1リクエスト/秒の制限に配慮
    return r.json().get("Items", [])


def search_items(keyword, top=5, min_review=4.0, min_count=10, hits=30):
    raw = _get({"keyword": keyword, "hits": hits, "sort": "-reviewCount",
                "availability": 1, "imageFlag": 1})
    items = [normalize(x) for x in raw]
    items = [
        i for i in items
        if i["url"] and i["price"] > 0
        and i["review_avg"] >= min_review and i["review_count"] >= min_count
    ]
    return items[:top]


def fetch_by_code(item_code):
    """商品コードで最新情報を取得。API成功で0件なら None(=削除/取扱終了)。
    通信エラーは例外を投げる(呼び出し側で「変更なし」として扱う)"""
    raw = _get({"itemCode": item_code, "hits": 1, "availability": 0})
    for x in raw:
        n = normalize(x)
        if n["code"] == item_code:
            return n
    return None
