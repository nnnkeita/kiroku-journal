# Kiroku Journal システム仕様書

**作成日**: 2026年2月15日  
**アプリケーション**: 日記・記録アプリ（Notion風ブロックエディタ）  
**技術スタック**: Flask + SQLite + JavaScript（Tailwind, Sortable）

---

## 📋 ドキュメント体系

このプロジェクトには複数の仕様ドキュメントがあります。必要に応じて参照してください。

| ドキュメント | 用途 | 対象者 |
|---------|------|-------|
| **SYSTEM_OVERVIEW.md** (本ファイル) | システム全体の構造と役割を把握 | 全員 |
| [README.md](README.md) | アプリケーション概要と簡単な導入手順 | 開発者・ユーザー |
| [MODULARIZATION_GUIDE.md](MODULARIZATION_GUIDE.md) | コードの分割構成と詳細設計 | 開発者 |
| [MODULE_GUIDE.md](MODULE_GUIDE.md) | 各Pythonモジュールの役割と関数 | 開発者 |
| [DEPLOY.md](DEPLOY.md) | 本番環境へのデプロイ手順 | DevOps・開発者 |
| [SAAS_SETUP.md](SAAS_SETUP.md) | SaaS機能（認証・課金）の設定 | DevOps・開発者 |
| [WEBHOOK_SETUP.md](WEBHOOK_SETUP.md) | Stripe Webhook設定と連携 | DevOps |
| [SALES_CHECKLIST.md](SALES_CHECKLIST.md) | 顧客対応チェックリスト | 営業・サポート |

---

## 🏗️ システムアーキテクチャ

### 層別構成

```
┌─────────────────────────────────────────────┐
│         ブラウザ / フロントエンド             │
│    (HTML template + JavaScript + Tailwind)  │
└──────────────────┬──────────────────────────┘
                   │ HTTP/JSON
┌──────────────────▼──────────────────────────┐
│    Flask アプリケーション (flask_app.py)     │
│  ・ルーティング                              │
│  ・ユーザー認証・セッション管理               │
│  ・14日トライアル / Stripe統合               │
└──────────────────┬──────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
┌───▼──────┐  ┌──▼────────┐  ┌──▼────────┐
│routes.py │  │utils.py  │  │database.py│
│(40+ API) │  │(ユーティ) │  │(DB管理)   │
└──────────┘  └──────────┘  └──┬────────┘
                                 │
┌────────────────────────────────▼─────────────┐
│    SQLite Database (notion.db)                │
│  ・pages (ページ/フォルダ階層)                 │
│  ・blocks (テキスト/見出し/Todo等)             │
│  ・templates (テンプレート)                   │
│  ・users (認証情報)                           │
│  ・password_reset_tokens                     │
│  ・healthplanet_tokens                       │
└──────────────────────────────────────────────┘

┌──────────────────────────────────────────────┐
│    バックアップシステム                       │
│  ・backup_scheduler.py (5分ごと自動備)        │
│  ・backups/ (JSON形式バックアップ)            │
│  ・復元スクリプト (restore_*.py)              │
└──────────────────────────────────────────────┘
```

---

## 📂 ファイル構成一覧

### コアファイル（Pythonモジュール）

| ファイル | 行数 | 役割 | 重要度 |
|---------|------|------|-------|
| **flask_app.py** | 81 | Flaskアプリ初期化、ページビューの提供 | ⭐⭐⭐ |
| **routes.py** | 1,086 | APIエンドポイント定義（40+ルート） | ⭐⭐⭐ |
| **database.py** | 170 | DB接続・スキーマ・トランザクション管理 | ⭐⭐⭐ |
| **utils.py** | 332 | ユーティリティ関数（計算・変換・バックアップ） | ⭐⭐ |
| **backup_scheduler.py** | 45 | 自動バックアップスケジューラ | ⭐⭐ |
| **daily_backup.py** | - | 日次バックアップ（cron用） | ⭐ |

### 復元・管理スクリプト

| ファイル | 用途 |
|---------|------|
| restore_full_db.py | バックアップから完全復元 |
| restore_morning_db.py | 朝のバックアップから復元 |
| restore_from_feb12.py | 特定日時のバックアップから復元 |
| check_backups.py | バックアップの検証 |

### 設定・実行ファイル

| ファイル | 用途 |
|---------|------|
| requirements.txt | Python パッケージ依存関係 |
| .env.example | 環境変数テンプレート |
| .env | 環境変数（本番機密情報） |
| deploy.sh | デプロイ自動化スクリプト |
| com.npicture.daily.backup.plist | macOS定期実行設定（LaunchAgent） |

**SQLite データベースファイル:**

| ファイル | 用途 |
|---------|------|
| **notion.db** | メインデータベース（ページ・ブロック） |
| notion.db-shm | SQLiteの共有メモリ（キャッシュ） |
| notion.db-wal | Write-Ahead Log（トランザクション管理） |

### フロントエンド

| ディレクトリ | 内容 |
|------------|------|
| templates/ | Jinja2テンプレート（HTML） |
| static/ | CSS・JavaScript・画像 |
| uploads/ | ユーザーアップロード画像 |

**主要テンプレートファイル:**

| ファイル | 用途 | 行数 |
|---------|------|------|
| **index.html** | メインアプリケーション（ページ・ブロックエディタ） | 2,983 |
| login.html | ログイン画面 | - |
| signup.html / setup.html | ユーザー登録・初期設定 | - |
| billing.html | 課金・サブスクリプション管理 | - |
| calendar.html | カレンダー表示 | - |
| chat.html | チャット/AI機能 | - |

**静的ファイル（static/）:**
- `manifest.json` - PWA設定
- CSS・JavaScript（Tailwind, Sortable, カスタムスクリプト）
- アイコン・画像資産

### ドキュメント

| ファイル | 対象読者 |
|---------|--------|
| README.md | 全員 |
| MODULARIZATION_GUIDE.md | 開発者 |
| MODULE_GUIDE.md | 開発者 |
| DEPLOY.md | DevOps |
| SAAS_SETUP.md | DevOps |
| WEBHOOK_SETUP.md | DevOps |
| SALES_CHECKLIST.md | 営業・サポート |

---

## 🔧 主要機能と実装ファイル

### 1. ページ・ブロック管理

| 機能 | 実装ファイル | 主要関数 |
|------|-----------|--------|
| ページ作成/編集/削除 | routes.py | `/api/pages` |
| ブロック作成/編集/削除 | routes.py | `/api/blocks` |
| ドラッグ&ドロップ移動 | routes.py | `/api/blocks/{id}/reorder` |
| テンプレート作成 | routes.py | `/api/templates` |
| ページ階層管理 | database.py | `get_next_position()` |

### 2. 検索・フィルタリング

| 機能 | 実装ファイル |
|------|-----------|
| 全文検索（FTS） | routes.py (`/search`) |
| カレンダー表示 | routes.py (`/calendar`) |
| ページ一覧表示 | routes.py (`/pages`, `/api/pages`) |

### 3. ユーザー認証・課金

| 機能 | 実装ファイル | 関連ドキュメント |
|------|-----------|-----------------|
| ユーザー登録 | routes.py (`/setup`, `/register`) | SAAS_SETUP.md |
| ログイン/ログアウト | routes.py | SAAS_SETUP.md |
| 14日トライアル | routes.py | SAAS_SETUP.md |
| Stripe決済 | routes.py (`/checkout`) | SAAS_SETUP.md |
| Webhook処理 | routes.py (`/webhook/stripe`) | WEBHOOK_SETUP.md |

### 4. データインポート/エクスポート

| 機能 | 実装ファイル | 主要関数 |
|------|-----------|--------|
| ページエクスポート（JSON） | routes.py (`/export`) | `export_page_to_dict()` |
| ページエクスポート（Markdown） | utils.py | `page_to_markdown()` |
| JSONインポート | routes.py (`/import`) | `create_page_from_dict()` |
| 画像アップロード | routes.py (`/upload`) | |

### 5. バックアップと復元

| 機能 | 実装ファイル | 詳細 |
|------|-----------|------|
| 自動バックアップ | backup_scheduler.py | 5分ごと実行 |
| JSON バックアップ | utils.py | `backup_database_to_json()` |
| 完全復元 | restore_full_db.py | 指定バックアップから復元 |
| 日次バックアップ | daily_backup.py | cron実行 |

### 6. カロリー記録機能

| 機能 | 実装ファイル | 主要関数 |
|------|-----------|--------|
| カロリー計算 | utils.py | `estimate_calories()` |
| 栄養素分析 | routes.py | `/calorie-analysis` |
| 健康プラットフォーム連携 | routes.py | `/healthplanet_sync_test` |

---

## 💾 データベーススキーマ

### テーブル一覧

| テーブル | 用途 | 主要カラム |
|---------|------|----------|
| **pages** | ページ/フォルダ | id, user_id, parent_id, title, position, color, icon |
| **blocks** | テキスト/見出し/Todo等 | id, page_id, type, content, position |
| **templates** | テンプレート | id, user_id, name, blocks_data |
| **users** | ユーザー情報 | id, email, password_hash, trial_end_date, subscription_id |
| **password_reset_tokens** | パスワード再設定 | token, user_id, expiry |
| **healthplanet_tokens** | 健康プラットフォーム連携 | user_id, access_token, refresh_token |

### インデックス管理

#### 1. 通常インデックス（パフォーマンス最適化）

| インデックス名 | 対象テーブル | カラム | 用途 |
|------------|----------|-------|------|
| idx_blocks_page_position | blocks | (page_id, position) | ページ内のブロック取得を高速化 |
| idx_pages_parent_position | pages | (parent_id, position, is_deleted) | ページ階層構造の走査を高速化 |
| idx_pages_is_deleted | pages | (is_deleted) | 削除状態でのフィルタリングを高速化 |

#### 2. FTS インデックス（全文検索）

- **blocks_fts**: ブロックコンテンツの全文検索用仮想テーブル
  - 型: FTS5（SQLiteの全文検索機能）
  - 対象: blocks テーブルの title と content
  - 自動同期: トリガーで INSERT/UPDATE/DELETE を自動追跡

#### 3. インデックス自動管理

**位置情報の自動計測**:
- `get_next_position()`: ページ階層内の次の position 値を計算
- `get_block_next_position()`: ブロック内の次の position 値を計算

**トリガーによる FTS 同期**:
- `blocks_ai`: INSERT トリガー - 新規ブロック追加時に FTS インデックスを更新
- `blocks_au`: UPDATE トリガー - ブロック更新時に FTS インデックスを更新
- `blocks_ad`: DELETE トリガー - ブロック削除時に FTS インデックスを更新

### SQLite WAL ファイル

- **notion.db-shm**: Shared memory ファイル（SQLiteの内部キャッシュ）
- **notion.db-wal**: Write-Ahead Logging ファイル（コミット前のトランザクション）
- 用途: 並行アクセスとデータ整合性確保
- 自動管理: SQLiteが自動的に管理・削除

---

## 🔐 環境変数と設定

### 必須環境変数（.env）

```env
# アプリケーション
APP_SECRET=ランダムな長い文字列
APP_BASE_URL=https://your-domain.com
AUTH_ENABLED=1  # 認証有効

# Stripe 課金
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID=price_...

# 機能フラグ
CALORIE_ENABLED=1
TTS_ENABLED=0
```

詳細は [SAAS_SETUP.md](SAAS_SETUP.md) を参照。

---

## 🚀 デプロイと運用

### 本番環境での起動

```bash
# PythonAnywhere / Render / Heroku
python flask_app.py
```

### 自動バックアップ設定

**macOS (LaunchAgent)**:
```bash
# 以下のファイルを設定
com.npicture.daily.backup.plist
```

**Linux (cron)**:
```bash
0 3 * * * cd /path/to/npicture-site && python daily_backup.py
```

### バックアップの管理

- **保存場所**: `backups/` ディレクトリ
- **形式**: JSON
- **自動実行**: 5分ごと（backup_scheduler.py）
- **手動復元**: `restore_*.py` スクリプト

詳細は [DEPLOY.md](DEPLOY.md) を参照。

---

## 📊 現在のシステム状態

**最終確認（2026年2月15日）**:
- ✅ ページ: 252個
- ✅ ブロック: 1,245個
- ✅ テンプレート: 3個
- ✅ 合計: 1,500レコード
- ✅ Flask アプリ: 正常動作
- ✅ Tanita/HealthPlanet 機能: 削除完了
- ✅ コード状態: c70d114（朝の状態）

---

## 🔗 関連ドキュメント

- 詳細な実装については [MODULARIZATION_GUIDE.md](MODULARIZATION_GUIDE.md) を参照
- 関数の詳細については [MODULE_GUIDE.md](MODULE_GUIDE.md) を参照
- デプロイについては [DEPLOY.md](DEPLOY.md) を参照
- SaaS機能については [SAAS_SETUP.md](SAAS_SETUP.md) を参照
- Webhook設定については [WEBHOOK_SETUP.md](WEBHOOK_SETUP.md) を参照

