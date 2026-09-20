import datetime as dt, json, pathlib, sys, tempfile
from unittest import mock
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import refresh, build_site, rakuten

def mk_items():
    return [{"code": c, "name": c, "price": 1000, "url": f"https://aff/{c}", "image": "", "shop": "S",
             "review_avg": 4.5, "review_count": 10, "caption": ""} for c in ("a:1", "b:2", "c:3")]

art = {"title": "T", "intro": "i", "outro": "o", "items": [{"idx": i, "comment": "c", "point": "p"} for i in range(3)]}

with tempfile.TemporaryDirectory() as td:
    td = pathlib.Path(td)
    refresh.DRAFTS = build_site.DRAFTS = td / "drafts"; build_site.OUT = td / "docs"
    refresh.DRAFTS.mkdir()
    def save(name, approved):
        (refresh.DRAFTS / name).write_text(json.dumps(
            {"keyword": "k", "created": "2026-09-01", "approved": approved, "items": mk_items(), "article": art}, ensure_ascii=False))
    save("pub.json", True); save("draft.json", False)

    def fetch(code):
        if code == "a:1": return {"price": 1200, "available": True}     # 価格変更
        if code == "b:2": return None                                    # 削除
        raise RuntimeError("network")                                    # c:3 は通信エラー

    today = dt.date(2026, 9, 21)
    checked, changed = refresh.run(fetch=fetch, today=today)
    assert (checked, changed) == (3, 2), (checked, changed)
    d = json.loads((refresh.DRAFTS / "pub.json").read_text())
    a, b, c = d["items"]
    assert a["price"] == 1200 and a["checked"] == "2026-09-21"
    assert b["available"] is False
    assert c["price"] == 1000 and "available" not in c and "checked" not in c, "通信エラーで値を変えてはいけない"
    # 未承認は触らない
    assert "checked" not in json.loads((refresh.DRAFTS / "draft.json").read_text())["items"][0]
    # 同日再実行: 成功済みの2件はスキップ、失敗した1件のみ再試行
    checked2, _ = refresh.run(fetch=fetch, today=today)
    assert checked2 == 1, checked2
    # 予算超過なら記事単位で打ち切り
    assert refresh.run(fetch=fetch, today=dt.date(2026, 9, 22), max_items=2)[0] == 0
    # 表示
    pub = build_site.build()
    h = (td / "docs" / pub[0][0]).read_text()
    assert "1,200円" in h and "2026-09-21時点" in h
    assert "在庫切れまたは取扱終了の可能性" in h and "楽天市場で在庫を確認" in h

# fetch_by_code: コード不一致は None、一致なら正規化
resp = [{"itemCode": "x:9", "itemName": "N", "itemPrice": 500, "itemUrl": "u", "availability": 0}]
with mock.patch.object(rakuten, "_get", return_value=resp):
    r = rakuten.fetch_by_code("x:9"); assert r["price"] == 500 and r["available"] is False
    assert rakuten.fetch_by_code("other:1") is None
print("REFRESH OK")
