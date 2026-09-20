"""キーワード → 商品取得 → 下書き生成(approved=false で保存)"""
import datetime as dt
import hashlib
import json
import os
import pathlib
import sys

import generate as gen_mod
import rakuten

ROOT = pathlib.Path(__file__).parent
DRAFTS = ROOT / "drafts"
STATE = ROOT / "state.json"
STATE_VERSION = "v2"  # 判定ロジックを変えたら上げる(同じ月でも作り直せる)
MIN_MAIN = 3          # 本体商品がこの数に満たなければ記事にしない
MAX_ITEMS = 5         # 記事に載せる最大数


def load_keywords():
    lines = (ROOT / "keywords.txt").read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lines if l.strip() and not l.startswith("#")]


def slug(kw):
    return hashlib.sha1(kw.encode("utf-8")).hexdigest()[:8]


def select_main(items, article):
    """AIが is_main=true と判定した商品だけ残し、idxを振り直す。除外した商品名も返す"""
    by_idx = {a["idx"]: a for a in article["items"]}
    keep, excluded = [], []
    for n, it in enumerate(items):
        (keep if by_idx[n]["is_main"] else excluded).append((it, by_idx[n]))
    keep = keep[:MAX_ITEMS]
    new_article = dict(article)
    new_article["items"] = [
        {"idx": k, "comment": a["comment"], "point": a["point"]} for k, (_, a) in enumerate(keep)
    ]
    return [it for it, _ in keep], new_article, [it["name"] for it, _ in excluded]


def run(max_articles=None, search=None, gen=None, today=None):
    search = search or rakuten.search_items
    gen = gen or gen_mod.generate
    today = today or dt.date.today()
    max_articles = max_articles or int(os.getenv("MAX_ARTICLES", "3"))

    DRAFTS.mkdir(exist_ok=True)
    state = set(json.loads(STATE.read_text())) if STATE.exists() else set()
    made, failed = 0, 0

    for kw in load_keywords():
        if made >= max_articles:
            break
        key = f"{kw}|{today:%Y-%m}|{STATE_VERSION}"
        if key in state:
            continue
        try:
            items = search(kw, top=8)
            if len(items) < MIN_MAIN:
                print(f"[skip] {kw}: 条件を満たす商品が{len(items)}件のみ")
                continue
            article = gen(kw, items)
            items, article, excluded = select_main(items, article)
            if len(items) < MIN_MAIN:
                print(f"[skip] {kw}: 本体商品と判定されたのが{len(items)}件のみ(付属品などを除外)")
                continue
        except Exception as e:
            failed += 1
            print(f"[error] {kw}: {e}", file=sys.stderr)
            continue
        draft = {
            "keyword": kw, "created": today.isoformat(), "approved": False,
            "items": items, "article": article, "excluded_items": excluded,
        }
        path = DRAFTS / f"{today:%Y-%m-%d}_{slug(kw)}.json"
        path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
        state.add(key)
        made += 1
        print(f"[draft] {path.name}: {article['title']}")

    STATE.write_text(json.dumps(sorted(state), ensure_ascii=False, indent=2))
    print(f"完了: 生成{made} / 失敗{failed}")
    return made, failed


if __name__ == "__main__":
    made, failed = run()
    sys.exit(1 if failed and not made else 0)
