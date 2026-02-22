# セットアップ手順: PythonAnywhere 環境変数設定

## 問題

サーバーで `HEALTHPLANET_CLIENT_ID/REDIRECT_URI is not set` というエラーが出ている

## 原因

`config/.env` ファイルが PythonAnywhere サーバーに存在していません（`.env` は `.gitignore` で除外されており Git では管理されていない）

## 解決方法

PythonAnywhere の Bash コンソールで以下のコマンドを実行してください：

### ステップ 1: PythonAnywhere Bash コンソールを開く

1. https://www.pythonanywhere.com にログイン
2. 「Consoles」タブをクリック
3. 「Bash console」で新しいコンソールを開く

### ステップ 2: 以下のコマンドを実行

```bash
# config ディレクトリに移動
cd /home/nnnkeita/kiroku-journal/config

# .env ファイルを作成
cat > .env << 'EOF'
# .env file for production (PythonAnywhere)

APP_SECRET=dev_secret_key_change_this_in_production
APP_BASE_URL=https://nnnkeita.pythonanywhere.com
AUTH_ENABLED=0

# --- PythonAnywhere API（デプロイ自動化） ---
# https://www.pythonanywhere.com/user/nnnkeita/account/#api_token から取得
PYTHONANYWHERE_API_TOKEN=

# --- Health Planet API（タニタ連携） ---
HEALTHPLANET_CLIENT_ID=39349.Z1fqIos8Qg.apps.healthplanet.jp
HEALTHPLANET_CLIENT_SECRET=1770513240597-fBgbT6q6NexGMsxjGZ6Ec0oNSLs5V9JHaWOvPlv6
HEALTHPLANET_REDIRECT_URI=https://nnnkeita.pythonanywhere.com/api/healthplanet/callback
HEALTHPLANET_SCOPE=innerscan
EOF

# 確認
echo "✅ 作成完了。確認："
cat .env | grep HEALTHPLANET
```

### ステップ 3: サーバーを再起動

1. https://www.pythonanywhere.com にアクセス
2. 「Web」タブをクリック
3. サイトの設定行で「Reload」ボタン（緑色）をクリック

### ステップ 4: 動作確認

https://nnnkeita.pythonanywhere.com にアクセスして、メインページが正常に表示されることを確認

---

**トラブルシューティング:**

- コマンドが長い場合は「Copy & Paste」してください
- コンソールでエラーが出た場合は、各行を個別に実行してみてください
- 「permission denied」が出た場合は、`sudo` をつけてみてください：`sudo cat > /home/nnnkeita/kiroku-journal/config/.env << 'EOF'`
