"""楽天市場商品検索API クライアント(2026年の新エンドポイント対応)"""
import os
import re
import time
import unicodedata
from urllib.parse import urlparse

import requests

ENDPOINT = os.getenv("RAKUTEN_ENDPOINT") or (
    "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
)


# 宣伝文句の除去: ＼…／と★…★は常に削除、【】[]は販促語を含むものだけ削除(商品の特徴は残す)
_PROMO = re.compile(
    r"クーポン|OFF|オフ|マラソン|セール|SALE|ポイント|P\d+倍|送料無料|限定|最大|円|%|％|割引|特典|予約|期間"
    r"|SS|スーパー|\d+位|受賞|冠|ランキング|NO\.?\s?1|新発売|新登場|新作|新モデル|激安|最安|特価"
    r"|訳あり|訳アリ|在庫|早い者勝ち|公式|楽天", re.I)
_ALWAYS = re.compile(r"＼[^／]*／|★[^★]*★")
_BRACKETS = re.compile(r"【[^】]*】|\[[^\]]*\]|［[^］]*］")


def clean_name(name):
    def drop(m):
        return "" if _PROMO.search(m.group(0)) else m.group(0)
    s = _BRACKETS.sub(drop, _ALWAYS.sub("", name))
    cleaned = re.sub(r"\s+", " ", s).strip()
    return cleaned or name  # 全部消えたら元の名前を使う


def dedupe(items):
    """同じ店・同じ画像(=色違い・サイズ違い)の重複を除く。先に出たもの(レビュー数が多い方)を残す"""
    seen, out = set(), []
    for i in items:
        key = (i["shop"], i["image"] or i["name"])
        if key not in seen:
            seen.add(key)
            out.append(i)
    return out


def _norm(text):
    return unicodedata.normalize("NFKC", text).lower()


def name_matches(name, keyword):
    """キーワードの各単語がすべて商品名に含まれるか(全角半角・大文字小文字は無視)"""
    n = _norm(name)
    return all(_norm(t) in n for t in keyword.split())


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
        "name": clean_name(_clean(it.get("itemName"), 400))[:120],
        "price": int(it.get("itemPrice") or 0),
        "url": it.get("affiliateUrl") or it.get("itemUrl") or "",
        "image": _first_image(it),
        "shop": it.get("shopName", ""),
        "review_avg": float(it.get("reviewAverage") or 0),
        "review_count": int(it.get("reviewCount") or 0),
        "caption": _clean(it.get("itemCaption")),
        "available": str(it.get("availability", 1)) == "1",
    }


def _origin_headers():
    """楽天の新APIは Referer ではなく Origin を見る(RAKUTEN_REFERER から作る)"""
    ref = os.getenv("RAKUTEN_REFERER") or "https://example.com"
    if "://" not in ref:
        ref = "https://" + ref
    p = urlparse(ref)
    return {"Origin": f"{p.scheme}://{p.netloc}", "Referer": ref}


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
    headers = _origin_headers()

    r = requests.get(ENDPOINT, params=full, headers=headers, timeout=15)
    time.sleep(1.1)  # 1リクエスト/秒の制限。失敗時も必ず待つ(429の連鎖を防ぐ)
    if r.status_code in (401, 403):
        raise RuntimeError(
            f"楽天API認証エラー({r.status_code}) 楽天の返答: {r.text[:300]} "
            "/ 確認点: アプリID・アクセスキー・許可ドメイン・RAKUTEN_REFERER"
        )
    if r.status_code == 429:
        raise RuntimeError("楽天API 429: リクエスト過多。しばらく待って再実行してください")
    if not r.ok:  # 400等: 楽天が返した理由(どの項目がだめか)を必ず表示する
        raise RuntimeError(f"楽天API エラー({r.status_code}) 楽天の返答: {r.text[:400]}")
    return r.json().get("Items", [])


def search_items(keyword, top=8, min_review=4.0, min_count=10, hits=30, strict=True):
    raw = _get({"keyword": keyword, "hits": hits, "sort": "-reviewCount",
                "availability": 1, "imageFlag": 1})
    items = [normalize(x) for x in raw]
    items = [
        i for i in items
        if i["url"] and i["price"] > 0
        and i["review_avg"] >= min_review and i["review_count"] >= min_count
    ]
    if strict:  # 商品名にキーワードが無い商品(説明文だけ一致)を除外
        before = len(items)
        items = [i for i in items if name_matches(i["name"], keyword)]
        if before != len(items):
            print(f"[info] {keyword}: 商品名が一致しない{before - len(items)}件を除外")
    return dedupe(items)[:top]


def fetch_by_code(item_code):
    """商品コードで最新情報を取得。API成功で0件なら None(=削除/取扱終了)。
    通信エラーは例外を投げる(呼び出し側で「変更なし」として扱う)"""
    raw = _get({"itemCode": item_code, "hits": 1, "availability": 0})
    for x in raw:
        n = normalize(x)
        if n["code"] == item_code:
            return n
    return None
