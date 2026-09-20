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


def load_keywords():
    lines = (ROOT / "keywords.txt").read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lines if l.strip() and not l.startswith("#")]


def slug(kw):
    return hashlib.sha1(kw.encode("utf-8")).hexdigest()[:8]


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
        key = f"{kw}|{today:%Y-%m}"
        if key in state:
            continue
        try:
            items = search(kw)
            if len(items) < 3:
                print(f"[skip] {kw}: 条件を満たす商品が{len(items)}件のみ")
                continue
            article = gen(kw, items)
        except Exception as e:
            failed += 1
            print(f"[error] {kw}: {e}", file=sys.stderr)
            continue
        draft = {
            "keyword": kw, "created": today.isoformat(), "approved": False,
            "items": items, "article": article,
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
