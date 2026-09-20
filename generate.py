"""Claudで記事の「文章部分だけ」を生成。URL・価格・画像はここでは扱わない"""
import json
import os
import re

import anthropic

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")

SYSTEM = """あなたは日本語のEC比較記事のライターです。
与えられた商品データ(JSON)だけを根拠に、比較記事の文章部分を書いてください。

厳守ルール:
- データに無いスペック・効果・成分・受賞歴・数値を創作しない。不明なことは書かない
- 医薬的な効能効果、「最安」「No.1」などの断定・根拠のない最上級表現を使わない
- 価格・URLは本文に書かない(システムが別途挿入する)
- 各商品の comment は60〜120字、point は「向いている人」を40字以内
- 出力は次の形式のJSONのみ。前置き・コードフェンス不要:
{"title": "...", "intro": "...(150〜250字)", "items": [{"idx": 0, "comment": "...", "point": "..."}], "outro": "...(80〜150字)"}
"""


def _parse_json(text):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    return json.loads(text)


def validate(data, n_items):
    for k in ("title", "intro", "items", "outro"):
        if not data.get(k):
            raise ValueError(f"missing key: {k}")
    idxs = sorted(i.get("idx") for i in data["items"])
    if idxs != list(range(n_items)):
        raise ValueError(f"item idx mismatch: {idxs}")
    for i in data["items"]:
        if not i.get("comment") or not i.get("point"):
            raise ValueError("empty comment/point")


def generate(keyword, items, retries=1):
    client = anthropic.Anthropic()
    payload = [
        {"idx": n, "name": i["name"], "shop": i["shop"], "review_avg": i["review_avg"],
         "review_count": i["review_count"], "caption": i["caption"]}
        for n, i in enumerate(items)
    ]
    user = f"キーワード: {keyword}\n商品データ:\n{json.dumps(payload, ensure_ascii=False)}"
    last = None
    for _ in range(retries + 1):
        msg = client.messages.create(
            model=MODEL, max_tokens=2500, system=SYSTEM,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        try:
            data = _parse_json(text)
            validate(data, len(items))
            return data
        except Exception as e:  # 形式不正なら1回だけ再試行
            last = e
    raise RuntimeError(f"記事生成に失敗: {last}")
