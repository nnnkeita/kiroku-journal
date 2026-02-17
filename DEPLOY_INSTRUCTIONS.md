# PythonAnywhere デプロイ手順

デプロイが完了しました。以下のいずれかの方法で反映してください：

## 方法1: PythonAnywhere Webコンソール（自動方法は現在不可）
1. https://www.pythonanywhere.com にアクセス
2. "Web" > "nnnkeita.pythonanywhere.com" > "Reload"ボタンを押す

## 方法2: SSH 手動実行（オプション）
```bash
ssh nnnkeita@bash.pythonanywhere.com
cd /home/nnnkeita/kiroku-journal
git pull origin main
cp wsgi.py /var/www/nnnkeita_pythonanywhere_com_wsgi.py
touch /var/www/nnnkeita_pythonanywhere_com_wsgi.py
```
