"""公開済み(approved)記事の価格・在庫を更新。文章とアフィリエイトURLは触らない"""
import datetime as dt
import json
import os
import pathlib
import sys

import rakuten

ROOT = pathlib.Path(__file__).parent
DRAFTS = ROOT / "drafts"


def refresh_item(it, fetch, today):
    """1商品を更新して変更有無を返す。通信エラー時は既存値を保持"""
    if not it.get("code"):
        return False
    try:
        latest = fetch(it["code"])
    except Exception as e:
        print(f"[warn] {it['code']}: {e}", file=sys.stderr)
        return False
    if latest is None:                      # 取扱終了・削除
        changed = it.get("available", True) is not False
        it["available"] = False
    else:
        changed = (it["price"], it.get("available", True)) != (latest["price"], latest["available"])
        it["price"], it["available"] = latest["price"], latest["available"]
    it["checked"] = today.isoformat()
    return changed


def run(fetch=None, today=None, max_items=None):
    fetch = fetch or rakuten.fetch_by_code
    today = today or dt.date.today()
    budget = max_items or int(os.getenv("REFRESH_MAX_ITEMS", "150"))
    targets = []
    for f in DRAFTS.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("approved") is True:
            targets.append((f, d))
    # 最後に確認してから最も古い記事から優先(予算内で全体を回す)
    targets.sort(key=lambda t: min(i.get("checked") or t[1]["created"] for i in t[1]["items"]))

    changed_items = checked = 0
    for f, d in targets:
        if checked + len(d["items"]) > budget:
            break
        dirty = False
        for it in d["items"]:
            if it.get("checked") == today.isoformat():
                continue
            checked += 1
            if refresh_item(it, fetch, today):
                changed_items += 1
            dirty = True
        if dirty:
            f.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"価格・在庫更新: 確認{checked}件 / 変更{changed_items}件")
    return checked, changed_items


if __name__ == "__main__":
    run()
