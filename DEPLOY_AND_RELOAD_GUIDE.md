# 🚀 デプロイ＆リロード管理ガイド

## 📋 概要

Kiroku Journal には以下の統合デプロイ・リロード機能が実装されています：

- **ローカルテスト**: Python 構文チェック
- **Git 管理**: コミット・プッシュ自動化
- **リモート同期**: PythonAnywhere への自動同期
- **WSGI リロード**: Webアプリケーション自動リロード
- **接続確認**: システムステータス API

---

## 🎯 クイック スタート

### 1️⃣ ローカル変更のデプロイ

```bash
cd /Users/nishiharakeita/kiroku-journal
./deploy_complete.sh
```

このコマンドが実行する処理：
1. Python ファイルの構文チェック
2. Git コミット・プッシュ
3. PythonAnywhere の自動同期
4. WSGI リロード
5. 接続確認

---

## 📡 システムステータス確認

### API エンドポイント一覧

#### 1. システムステータス
```bash
curl http://localhost:5000/api/system/status | jq .
```

**レスポンス例:**
```json
{
  "timestamp": "2026-02-25T20:57:00.000000",
  "app_name": "Kiroku Journal",
  "app_version": "1.0.0",
  "environment": "local",
  "database": {
    "connected": true,
    "path": "/path/to/notion.db",
    "size_mb": 12.34
  },
  "flask_app": "Running",
  "features": {
    "tts_enabled": true,
    "calorie_enabled": true,
    "auth_enabled": false
  }
}
```

#### 2. ヘルスチェック
```bash
curl http://localhost:5000/api/system/health-check
```

**レスポンス例:**
```json
{
  "status": "healthy",
  "timestamp": "2026-02-25T20:57:00.000000",
  "database_ok": true
}
```

#### 3. リロード トリガー（PythonAnywhere用）
```bash
curl -X POST http://localhost:5000/api/system/reload
```

**レスポンス例:**
```json
{
  "status": "success",
  "message": "App reload triggered",
  "timestamp": "2026-02-25T20:57:00.000000",
  "wsgi_path": "/path/to/wsgi.py"
}
```

---

## 🔧 詳細な使用方法

### デプロイスクリプト オプション

#### 通常のデプロイ（推奨）
```bash
./deploy_complete.sh
```
- ローカルテスト + Git + リモート同期 + リロード

#### 既存のスクリプト
```bash
./deploy.sh              # 基本的なデプロイ
./deploy_with_git_pull.sh  # Git pull含む
./sync_pythonanywhere.sh   # PythonAnywhere同期のみ
```

---

## 🎨 フォント設定

### 実装済みのフォント

すべてのテンプレートファイルで **Noto Serif JP**（明朝細字）に統一：

**対象ファイル:**
- `templates/index.html`
- `templates/setup.html`
- `templates/login.html`
- `templates/privacy.html`
- `templates/billing.html`
- `templates/reset.html`
- `templates/terms.html`
- `templates/tokusho.html`
- `templates/healthplanet.html`
- `templates/healthplanet_sync.html`
- `templates/forgot.html`

**使用フォント URL:**
```html
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+JP:wght@400;700&display=swap" rel="stylesheet">
```

**CSS 適用:**
```css
font-family: 'Noto Serif JP', serif;
```

---

## 🔍 トラブルシューティング

### 問題: SSH接続失敗

**原因**: PythonAnywhere の SSH キーが未設定

**解決方法**:
1. PythonAnywhere ダッシュボードにログイン
2. Account → SSH Keys で公開鍵を登録
3. `config/.env` で `PYTHONANYWHERE_USER` を確認

### 問題: API トークンエラー

**原因**: `PYTHONANYWHERE_API_TOKEN` が未設定

**解決方法**:
1. `config/.env` ファイルを編集
2. トークンを追加:
   ```bash
   PYTHONANYWHERE_API_TOKEN=your_token_here
   ```

### 問題: リロードが反映されない

**解決方法**:
1. ブラウザキャッシュをクリア (Ctrl+Shift+Delete)
2. 手動リロード API を実行:
   ```bash
   curl -X POST https://your.pythonanywhere.com/api/system/reload
   ```
3. PythonAnywhere ダッシュボードからも確認

---

## 📊 監視コマンド

### リアルタイム接続確認
```bash
while true; do
  curl -s http://localhost:5000/api/system/health-check | jq .status
  sleep 5
done
```

### データベースサイズモニタリング
```bash
watch -n 1 'ls -lh notion.db | awk "{print \"DB Size: \" \$5}"'
```

### Git 状態確認
```bash
git status
git log --oneline -5
```

---

## 📝 ログファイル位置

- **アプリケーションログ**: コンソール出力（ターミナル）
- **バックアップログ**: `backups/` フォルダ
- **デプロイログ**: `.git/logs/` フォルダ

---

## 🔐 セキュリティチェック

デプロイ前の確認リスト：

- [ ] `.env` ファイルの機密情報を確認
- [ ] API トークンが public repository に含まれていない
- [ ] SSH キーが安全に保管されている
- [ ] ローカルテスト成功を確認

---

## 📞 サポート情報

**環境情報:**
- OS: macOS
- Python: 3.8+
- Flask: Latest
- Database: SQLite

**参照ドキュメント:**
- [DEPLOYMENT.md](DEPLOYMENT.md) - デプロイ詳細ガイド
- [DEPLOY_INSTRUCTIONS.md](DEPLOY_INSTRUCTIONS.md) - 初期セットアップ
- [PYTHONANYWHERE_SYNC_GUIDE.md](PYTHONANYWHERE_SYNC_GUIDE.md) - PythonAnywhere 連携

---

**最終更新:** 2026-02-25  
**バージョン:** 1.0.0
