# デプロイメント ガイド

## 概要

このプロジェクトは Flask ベースの Kiroku Journal アプリケーションです。デプロイメントは自動化スクリプトを使用して、PythonAnywhere サーバーへの完全自動デプロイを実現します。

## デプロイメント方法

### ステップ 1: コード変更を確認

変更を Git に追加してコミットします：

```bash
git add .
git commit -m "Your commit message"
```

### ステップ 2: デプロイを実行

以下のコマンドで **ワンステップデプロイ** を実行します：

```bash
bash deploy.sh
```

### ステップ 3: 自動デプロイが完了

スクリプトは自動的に以下を実行します：

1. ✅ `wsgi.py` にタイムスタンプを追加
2. ✅ Git にコミット
3. ✅ GitHub にプッシュ
4. ✅ **PythonAnywhere SSH 経由で自動サーバーリロード**
   - コードを自動でプル
   - WSGI ファイルを更新してサーバーをリロード
   - **PythonAnywhere "Reload" ボタンは不要**

## デプロイメント状態の確認

デプロイ完了後の出力例：

```
✓ WSGIファイルを更新しました
✅ GitHub にプッシュしました
✅ SSH 経由でサーバーをリロードしました
```

## トラブルシューティング

### デプロイ後に変更が反映されない場合

1. **ブラウザのキャッシュをクリア**
   - Chrome: Cmd + Shift + Delete
   - Safari: Preferences > Advanced > "Develop" > Delete All Website Data

2. **再度デプロイを実行**
   ```bash
   bash deploy.sh
   ```

3. **PythonAnywhere Web Console で確認**
   - https://www.pythonanywhere.com にログイン
   - "Web" タブで手動リロード（緊急時のみ）

### SSH 接続エラーの場合

- SSH キーが正しく設定されているか確認
- `ssh nnnkeita@bash.pythonanywhere.com` でテスト接続
- パスワード入力が必要な場合、キーベース認証を PythonAnywhere で設定

## オプション: PythonAnywhere API トークン

より高い信頼性を求める場合 API トークンを使用できます：

1. https://www.pythonanywhere.com/user/nnnkeita/account/#api_token から API トークンを取得
2. `config/.env`（存在しない場合は作成）に追加：
   ```
   PYTHONANYWHERE_API_TOKEN=your_token_here
   ```
3. デプロイスクリプトが SSH の失敗時に API メソッドにフォールバック

## アーキテクチャ

```
GitHub Push
    ↓
deploy.sh (SSH method)
    ├─ SSH into PythonAnywhere
    ├─ git pull latest code
    └─ touch WSGI file to reload
         ↓
    [Automatic server reload]
    
    (Fallback if available)
    └─ API method via PYTHONANYWHERE_API_TOKEN
```

## 重要な環境変数

- `PYTHONANYWHERE_API_TOKEN`: オプション（API ベースリロード用）
- その他の設定は `config/.env` に記載

## サポートされるファイル

- **テンプレート**: `templates/` 以下の HTML ファイル
  - index.html
  - login.html
  - billing.html
  - その他全テンプレート
  
- **Python コード**: `kiroku.py` および `utils.py`
- **フロントエンド**: CSS および JavaScript

## フォント設定

すべてのテンプレートで **BIZ UDPゴシック** フォント（400, 700 Weight）が使用されています。
レスポンシブデザイン対応済みで、iPhone などモバイルデバイスでも最適化されています。

---

最後の更新: デプロイ自動化により、"Reload" ボタン クリックが不要になりました ✨
