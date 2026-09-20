# 楽天アフィリエイト半自動パイプライン

キーワード → 楽天API取得 → Claudeで文章生成 → **下書き保存(未承認)** → 承認した記事のみ静的サイト化(docs/)

## セットアップ
1. 楽天ウェブサービスでアプリ登録 → アプリID・アクセスキー取得(許可URLに公開サイトのURLを登録)
2. 楽天アフィリエイトのアフィリエイトIDを取得
3. GitHubリポジトリに置き、Secretsを登録:
   `RAKUTEN_APP_ID` `RAKUTEN_ACCESS_KEY` `RAKUTEN_AFFILIATE_ID` `RAKUTEN_REFERER`(許可URLと同じ) `ANTHROPIC_API_KEY`
4. Settings > Pages で `main` の `/docs` を公開
5. `keywords.txt` を編集 → Actions から `daily` を手動実行

## 運用
- 毎朝 `drafts/*.json` に下書きが増える(1日最大 `MAX_ARTICLES`=3本、同一キーワードは月1回)
- 内容を確認し、問題なければ `"approved": true` に書き換えて保存 → 自動で公開
- 公開済み記事の価格・在庫は毎朝 `refresh.py` が更新(1日最大 `REFRESH_MAX_ITEMS`=150商品。古い記事から優先)
  - 取扱終了・在庫切れは記事内に注意書きを表示。通信エラー時は既存の値を保持(誤って在庫切れにしない)
- 手元実行: `pip install -r requirements.txt && python pipeline.py && python refresh.py && python build_site.py`
- テスト: `python tests/test_smoke.py && python tests/test_refresh.py`

## 設計上の安全策
- AIは文章のみ生成。URL・価格・画像はAPI値をコードが挿入(改変・幻覚を防止)
- 全記事に「PR」表記と広告開示を自動付与、リンクは `rel="sponsored"`
- 楽天API仕様が変わった場合は環境変数 `RAKUTEN_ENDPOINT` で差し替え可

## 未実装(次の拡張候補)
- 検索順位・クリック計測(Search Console / 楽天レポート連携)
- キーワード自動提案
