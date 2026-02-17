# PythonAnywhere 自動同期トラブルシューティング

## 現状
- ✅ GitHub には最新コードが push されています
- ⏳ PythonAnywhere への自動反映がうまく機能していません

## 原因の可能性
1. wsgi.py の git sync が実行されていない
2. PythonAnywhere WSGI module のキャッシュ
3. WSGI entry point が正確に更新されていない

## 解決手順（優先順）

### 手順1: PythonAnywhere Web UI で Reload（推奨）
```
1. https://www.pythonanywhere.com にアクセス
2. "Web" タブをクリック
3. "nnnkeita.pythonanywhere.com" をクリック
4. 右上の大きな青い "Reload" ボタンをクリック
5. ブラウザで https://nnnkeita.pythonanywhere.com をリロード（Cmd+Shift+R）
```

### 手順2: SSH で手動同期（確実な方法）
```bash
# ターミナルで実行
ssh nnnkeita@bash.pythonanywhere.com

# PythonAnywhere コンソール内で実行
cd /home/nnnkeita/kiroku-journal

# 最新コードを取得
git pull origin main

# WSGI entry point を更新
cp wsgi.py /var/www/nnnkeita_pythonanywhere_com_wsgi.py

# ファイルをタッチして reload をトリガー
touch /var/www/nnnkeita_pythonanywhere_com_wsgi.py

# 確認
git log --oneline -3
```

### 手順3: ログで同期状況を確認
```bash
# SSH コンソール内で実行
tail -50 /home/nnnkeita/kiroku-journal/.wsgi_debug.log
cat /home/nnnkeita/kiroku-journal/.wsgi_sync_status

# エラーログを確認
tail -100 /var/log/nnnkeita.pythonanywhere.com.error.log
```

## GitHub Actions による自動化（将来の改善）
当面は上記の手順 1 か 2 を使用してください。将来的には GitHub Actions を設定して、push されたら自動的に PythonAnywhere に反映するようにできます。
