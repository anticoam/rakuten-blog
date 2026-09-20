"""approved=true の下書きだけを静的HTMLにして docs/ に出力"""
import html
import json
import pathlib

ROOT = pathlib.Path(__file__).parent
DRAFTS, OUT = ROOT / "drafts", ROOT / "docs"

CSS = """body{font-family:system-ui,sans-serif;max-width:720px;margin:0 auto;padding:16px;line-height:1.8;color:#222}
.pr{background:#f3f3f3;padding:8px 12px;font-size:.85em;border-radius:6px}
.item{border:1px solid #ddd;border-radius:10px;padding:14px;margin:20px 0}
.item img{max-width:160px;float:right;margin:0 0 8px 12px}
.btn{display:inline-block;background:#bf0000;color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none}
.price{font-weight:bold}.note{font-size:.8em;color:#666}footer{margin-top:40px;font-size:.8em;color:#666}"""

DISCLOSURE = "本記事は広告(アフィリエイトプログラム)を含みます。リンク経由で購入された場合、当サイトが報酬を受け取ることがあります。"


def e(s):
    return html.escape(str(s), quote=True)


def page(title, body):
    return (f"<!doctype html><html lang='ja'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{e(title)}</title><style>{CSS}</style></head><body>{body}"
            f"<footer>Supported by Rakuten Developers</footer></body></html>")


def price_html(it, d):
    when = e(it.get("checked") or d["created"])
    if it.get("available") is False:
        return f"<span class='note'>現在、在庫切れまたは取扱終了の可能性があります({when}確認)</span>"
    return f"{it['price']:,}円 <span class='note'>({when}時点)</span>"


def render_article(d):
    a, items = d["article"], d["items"]
    by_idx = {i["idx"]: i for i in a["items"]}
    parts = [f"<p class='pr'>PR｜{e(DISCLOSURE)}</p>", f"<h1>{e(a['title'])}</h1>", f"<p>{e(a['intro'])}</p>"]
    for n, it in enumerate(items):
        txt = by_idx[n]
        img = f"<img src='{e(it['image'])}' alt='{e(it['name'])}'>" if it["image"] else ""
        parts.append(
            f"<div class='item'>{img}<h2>{n + 1}. {e(it['name'])}</h2>"
            f"<p class='price'>{price_html(it, d)}</p>"
            f"<p>★{it['review_avg']:.2f}({it['review_count']:,}件)／{e(it['shop'])}</p>"
            f"<p>{e(txt['comment'])}</p><p><b>向いている人:</b>{e(txt['point'])}</p>"
            f"<p><a class='btn' href='{e(it['url'])}' rel='sponsored nofollow noopener' target='_blank'>{'楽天市場で在庫を確認' if it.get('available') is False else '楽天市場で見る'}</a></p></div>")
    parts.append(f"<p>{e(a['outro'])}</p>")
    parts.append("<p class='note'>価格・在庫は変動します。最新情報は必ずリンク先でご確認ください。</p>")
    return page(a["title"], "".join(parts))


def build():
    OUT.mkdir(exist_ok=True)
    published = []
    for f in sorted(DRAFTS.glob("*.json"), reverse=True):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("approved") is not True:
            continue
        name = f"{f.stem}.html"
        (OUT / name).write_text(render_article(d), encoding="utf-8")
        published.append((name, d["article"]["title"]))
    li = "".join(f"<li><a href='{e(n)}'>{e(t)}</a></li>" for n, t in published)
    (OUT / "index.html").write_text(
        page("記事一覧", f"<p class='pr'>PR｜{e(DISCLOSURE)}</p><h1>記事一覧</h1><ul>{li}</ul>"),
        encoding="utf-8")
    print(f"公開: {len(published)}件")
    return published


if __name__ == "__main__":
    build()
