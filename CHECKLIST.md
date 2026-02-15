# PythonAnywhere デプロイ チェックリスト

デプロイ前とデプロイ後に以下を確認してください。

---

## デプロイ前のチェック

- [ ] GitHub にコードをプッシュ済み
- [ ] `.gitignore` に以下が含まれている：
  - [ ] `notion.db`
  - [ ] `config/.env`
  - [ ] `__pycache__/`
  - [ ] `.DS_Store`
- [ ] `requirements.txt` が最新版のすべてのパッケージを含む
- [ ] ローカルで `python run.py` が正常に動作する
- [ ] `.env.example` が作成済み

---

## PythonAnywhere セットアップ時のチェック

- [ ] PythonAnywhere アカウントを作成
- [ ] リポジトリを `git clone` で取得
- [ ] Virtual environment を作成: `mkvirtualenv --python=/usr/bin/python3.11 kiroku-journal`
- [ ] 依存関係をインストール: `pip install -r requirements.txt`
- [ ] `config/.env` ファイルを作成・設定
- [ ] `config/` フォルダが `/home/<username>/kiroku-journal/config/` に存在
- [ ] 環境変数を確認：
  ```bash
  cat /home/<username>/kiroku-journal/config/.env
  ```

---

## Web アプリ設定時のチェック

### WSGI Configuration

- [ ] WSGI ファイルのパス: `/home/<username>/kiroku-journal/wsgi.py`
- [ ] WSGI ファイルが読み込み可能
- [ ] `import app.flask_app` でエラーがないか確認

### Virtual Environment

- [ ] パス: `/home/<username>/.virtualenvs/kiroku-journal`
- [ ] パスが正しいか確認：
  ```bash
  ls /home/<username>/.virtualenvs/kiroku-journal/bin/python
  ```

### Static Files

- [ ] URL: `/static/` → Directory: `/home/<username>/kiroku-journal/static`
- [ ] URL: `/uploads/` → Directory: `/home/<username>/kiroku-journal/uploads`
- [ ] `static/` フォルダが存在するか確認

### Source Code

- [ ] Source code: `/home/<username>/kiroku-journal`
- [ ] Working directory: `/home/<username>/kiroku-journal`

---

## デプロイ後のチェック

### 初期アクセス

- [ ] `https://your_username.pythonanywhere.com` にアクセス可能
- [ ] ページが読み込まれる（CSS/JS が正しく読み込まれている）
- [ ] エラーページが表示されていない

### 機能テスト

- [ ] ログインページが表示される
- [ ] 初期設定ページが表示される（ユーザー0の場合）
- [ ] エントリーを作成できる
- [ ] エントリーが保存される
- [ ] ページを再読込してデータが保持されている

### エラーログの確認

- [ ] Web アプリ設定の「Error log」を確認
- [ ] サーバーエラーがないか確認
- [ ] 警告メッセージをチェック

---

## 日常運用時のチェック

### 毎日

- [ ] パフォーマンスが正常か確認
- [ ] エラーログに異常がないか確認

### 毎週

- [ ] バックアップが作成されているか確認：
  ```bash
  ls -l /home/<username>/kiroku-journal/backups/
  ```
- [ ] ディスク使用量を確認
- [ ] データベースサイズを確認：
  ```bash
  du -h /home/<username>/kiroku-journal/notion.db
  ```

### 毎月

- [ ] 古いバックアップを削除
- [ ] ログファイルをローテーション
- [ ] セキュリティアップデートを確認：
  ```bash
  pip list --outdated
  ```

---

## トラブルシューティング流れ図

```
エラーが発生した？
  ├─ HTTP 500 エラー
  │  └─ Error log を確認
  │     ├─ ModuleNotFoundError
  │     │  └─ Virtual Environment を確認
  │     ├─ FileNotFoundError
  │     │  └─ ファイルパスを確認
  │     └─ その他の Python エラー
  │        └─ スタックトレースの最後の行を読む
  │
  ├─ HTTP 404 エラー
  │  └─ ルートが存在するか確認
  │
  ├─ 静的ファイルが読み込まれない
  │  └─ Static files 設定を確認
  ├─ データベースエラー
  │  └─ データベース初期化を再実行
  │
  └─ それでも解決しない
     └─ PythonAnywhere サポートに連絡
```

---

## サポートリンク

- [PythonAnywhere Help](https://help.pythonanywhere.com/)
- [Flask ドキュメント](https://flask.palletsprojects.com/)
- [SQLite リファレンス](https://www.sqlite.org/docs.html)
