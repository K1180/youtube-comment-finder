# YouTube Comment Finder

チャンネルURLを指定して、キーワードを含むコメントがある動画だけを抽出するツールです。

---

## 必要なもの

- Python 3.8以上
- YouTube Data API v3 のAPIキー

---

## セットアップ手順

### 1. 必要なライブラリをインストール

```bash
pip install -r requirements.txt
```

### 2. アプリを起動

```bash
python app.py
```

### 3. ブラウザでアクセス

```
http://localhost:5000
```

---

## 使い方

1. **APIキー** を入力（画面内にGoogleCloudからの取得手順あり）
2. **チャンネルURL** を入力（以下の形式に対応）
   - `https://www.youtube.com/@channelname`
   - `https://www.youtube.com/channel/UCxxxxxxxxxx`
   - `https://www.youtube.com/c/channelname`
   - `https://www.youtube.com/user/username`
3. **キーワード** を入力
4. 必要に応じて **検索期間**（開始日・終了日）を設定
5. **検索開始** ボタンをクリック

---

## 出力

- ✅ **コメント一致**: キーワードを含むコメントがある動画（一致コメントも展開表示可能）
- ✗ **一致なし**: 該当なしの動画（折りたたみで表示）

---

## 注意事項

- YouTube Data API v3 の無料枠は **1日10,000ユニット**
- 動画1件あたり概算：動画取得0.1〜1ユニット + コメント取得1〜5ユニット
- 50件の動画を全件コメント検索すると約250〜300ユニット消費
- コメントが無効になっている動画はスキップされます

---

## ファイル構成

```
youtube_comment_search/
├── app.py              # Flaskサーバー（APIロジック）
├── requirements.txt    # 依存ライブラリ
├── README.md
└── templates/
    └── index.html      # フロントエンドUI
```
