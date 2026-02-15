# PythonAnywhere タスクスケジューラー設定（バックアップ自動実行）

Kiroku Journal には自動バックアップ機能がありますが、PythonAnywhere の無料プランではスケジューラー実行が制限されています。以下の手順を参考にセットアップしてください。

---

## PythonAnywhere有料プランの場合（推奨）

### 1. PythonAnywhere の「Tasks」タブを開く

1. PythonAnywhere ダッシュボードの「Web」タブから、Web アプリを選択
2. 「Tasks」セクションを見つける

### 2. 毎日のバックアップタスクを追加

「Add a new task」をクリック：

**タスク内容**：

```
/home/<your_username>/.virtualenvs/kiroku-journal/bin/python /home/<your_username>/kiroku-journal/scripts/daily_backup.py
```

**実行時刻**：毎日 03:00 AM など、トラフィックが少ない時間帯を選択

---

## 無料プランの場合

### 方法1：手動バックアップ（推奨）

PythonAnywhere のコンソールで定期的に以下を実行：

```bash
cd /home/<your_username>/kiroku-journal
source /home/<your_username>/.virtualenvs/kiroku-journal/bin/activate
python scripts/daily_backup.py
```

### 方法2：外部施設サービスを使用

IFTTT や HTTP リクエストで定期実行をトリガー：

1. Zapier や IFTTT でスケジュール設定
2. 以下の HTTP リクエストを定期実行（1日1回）：

```
POST https://your_username.pythonanywhere.com/api/backup
```

---

## バックアップファイルの確認

PythonAnywhere のコンソールで：

```bash
ls -lh /home/<your_username>/kiroku-journal/backups/
```

バックアップは `backups/` フォルダに自動保存されます（JSON形式）

---

## バックアップからの復元

緊急時に復元が必要な場合：

```bash
cd /home/<your_username>/kiroku-journal
source /home/<your_username>/.virtualenvs/kiroku-journal/bin/activate
python scripts/restore_full_db.py backups/backup_20260215_100000.json
```

---

## 本番運用のベストプラクティス

1. **定期的なモニタリング**
   - 週に1回は PythonAnywhere コンソールからバックアップを確認

2. **外部ストレージへのバックアップ**
   - `backups/latest.json` を Google Drive や S3 にアップロード

3. **メール通知の設定**
   - バックアップ完了をメール通知する（スクリプト側で実装可能）

---

## トラブルシューティング

**バックアップが実行されない場合**

1. Virtual environment が正しくロードされているか確認
2. スクリプトの実行権限を確認：

```bash
chmod +x /home/<your_username>/kiroku-journal/scripts/daily_backup.py
```

3. エラーログを確認：

```bash
cd /home/<your_username>/kiroku-journal
source /home/<your_username>/.virtualenvs/kiroku-journal/bin/activate
python scripts/daily_backup.py
```
