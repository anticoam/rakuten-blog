import json, pathlib, sys, tempfile, datetime as dt
from unittest import mock
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import rakuten, pipeline, build_site, generate

# 1) normalize: v1/v2 両形式
v1 = {"Item": {"itemName": "<b>A</b> 商品", "itemPrice": 1980, "itemUrl": "https://i", "affiliateUrl": "https://aff",
               "mediumImageUrls": [{"imageUrl": "https://img1"}], "reviewAverage": "4.5", "reviewCount": 20, "shopName": "S"}}
v2 = {"itemName": "B", "itemPrice": "2500", "itemUrl": "https://i2", "mediumImageUrls": ["https://img2"], "reviewAverage": 4.2, "reviewCount": 5}
n1, n2 = rakuten.normalize(v1), rakuten.normalize(v2)
assert n1["url"] == "https://aff" and n1["image"] == "https://img1" and n1["name"] == "A 商品"
assert n2["url"] == "https://i2" and n2["image"] == "https://img2" and n2["price"] == 2500

# 2) search_items: フィルタ(レビュー低/件数少/価格0は除外)
resp = mock.Mock(status_code=200); resp.raise_for_status = lambda: None
resp.json.return_value = {"Items": [
    {"itemName": "ok1", "itemPrice": 100, "itemUrl": "u1", "reviewAverage": 4.6, "reviewCount": 99},
    {"itemName": "lowrate", "itemPrice": 100, "itemUrl": "u2", "reviewAverage": 3.0, "reviewCount": 99},
    {"itemName": "fewrev", "itemPrice": 100, "itemUrl": "u3", "reviewAverage": 4.9, "reviewCount": 1},
    {"itemName": "noprice", "itemPrice": 0, "itemUrl": "u4", "reviewAverage": 4.9, "reviewCount": 99}]}
with mock.patch("requests.get", return_value=resp), mock.patch("time.sleep"), \
     mock.patch.dict("os.environ", {"RAKUTEN_APP_ID": "a", "RAKUTEN_ACCESS_KEY": "k"}):
    got = rakuten.search_items("x")
assert [g["name"] for g in got] == ["ok1"], got

# 3) validate
good = {"title": "t", "intro": "i", "outro": "o", "items": [{"idx": 0, "comment": "c", "point": "p"}, {"idx": 1, "comment": "c", "point": "p"}]}
generate.validate(good, 2)
try:
    generate.validate(good, 3); raise SystemExit("validate should fail")
except ValueError:
    pass
assert generate._parse_json('```json\n{"a":1}\n```') == {"a": 1}

# 4) pipeline → 承認 → build(一時ディレクトリで実行)
with tempfile.TemporaryDirectory() as td:
    td = pathlib.Path(td)
    pipeline.DRAFTS, pipeline.STATE = td / "drafts", td / "state.json"
    build_site.DRAFTS, build_site.OUT = td / "drafts", td / "docs"
    fake_items = [dict(rakuten.normalize({"itemName": f"P{i}<script>", "itemPrice": 1000 + i, "affiliateUrl": f"https://aff/{i}",
                  "reviewAverage": 4.5, "reviewCount": 10 + i, "shopName": "S"})) for i in range(3)]
    for it in fake_items:
        it["name"] += "<script>"  # 正規化後に生の危険文字列を注入し、出力側のエスケープを検証
    fake_art = {"title": "T&T", "intro": "i", "outro": "o",
                "items": [{"idx": i, "comment": f"c{i}", "point": "p"} for i in range(3)]}
    today = dt.date(2026, 9, 20)
    m, f = pipeline.run(max_articles=5, search=lambda k: fake_items, gen=lambda k, it: fake_art, today=today)
    assert m == 2 and f == 0, (m, f)
    m2, _ = pipeline.run(max_articles=5, search=lambda k: fake_items, gen=lambda k, it: fake_art, today=today)
    assert m2 == 0, "同月の重複生成を防げていない"
    assert build_site.build() == [], "未承認が公開されている"
    p = sorted((td / "drafts").glob("*.json"))[0]
    d = json.loads(p.read_text()); d["approved"] = True; p.write_text(json.dumps(d, ensure_ascii=False))
    pub = build_site.build(); assert len(pub) == 1
    h = (td / "docs" / pub[0][0]).read_text()
    assert "PR｜" in h and "https://aff/0" in h and "&lt;script&gt;" in h and "<script>" not in h
    assert "sponsored" in h and "Supported by Rakuten Developers" in h
print("ALL OK")
