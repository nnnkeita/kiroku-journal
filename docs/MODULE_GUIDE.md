# コードモジュール分割について

## 概要
flask_app.pyが1900行を超えたため、管理しやすくするために3つのモジュールに機能を分割しました。

## モジュール構成

### 1. `database.py` (データベース層)
**役割**: データベース接続とテーブル管理

**主な関数**:
- `get_db()` - DB接続を取得
- `init_db()` - テーブル初期化
- `get_next_position()` - 次のposition値を計算
- `get_block_next_position()` - ブロックの次のposition値
- `mark_tree_deleted()` - ページツリーを削除マーク
- `hard_delete_tree()` - ページツリーを完全削除
- `get_or_create_inbox()` - 「あとで調べる」ページを取得/作成

### 2. `utils.py` (ユーティリティ層)
**役割**: カロリー計算、エクスポート/インポート、バックアップ

**主な関数**:
- `allowed_file()` - ファイル拡張子チェック
- `estimate_calories()` - カロリー計算
- `export_page_to_dict()` - ページをJSON形式にエクスポート
- `page_to_markdown()` - ページをMarkdown形式に変換
- `create_page_from_dict()` - JSON形式からページを作成
- `copy_page_tree()` - ページツリーをコピー
- `backup_database_to_json()` - データベースバックアップ

### 3. `flask_app.py` (ルーティング層)
**役割**: FlaskアプリケーションとAPIエンドポイント

**内容**:
- 全てのAPIルート (@app.route)
- アプリケーション設定
- リクエスト/レスポンス処理

## 使い方

### 現在の状態（互換性モード）
既存のコードがそのまま動作します。モジュールは参考用に作成されています。

```python
# flask_app.py を通常通り起動
python flask_app.py
```

### モジュール分割版を使う場合
`flask_app.py`の先頭のコメントアウトを解除します：

```python
# flask_app.py の 25-28行目あたり
from database import get_db, init_db, get_next_position, get_block_next_position
from database import mark_tree_deleted, hard_delete_tree, get_or_create_inbox
from utils import allowed_file, estimate_calories, export_page_to_dict
from utils import page_to_markdown, create_page_from_dict, copy_page_tree, backup_database_to_json
```

そして、flask_app.py内の重複する関数定義（`def get_db()` など）を削除します。

## メリット

✅ **可読性向上**: 各ファイルが500-600行で管理しやすい  
✅ **メンテナンス性**: 機能ごとに分離され、修正が容易  
✅ **テスト性**: 各モジュールを個別にテスト可能  
✅ **再利用性**: 他のプロジェクトでもモジュールを再利用可能

## ファイル一覧

```
npicture-site/
├── flask_app.py      # メインアプリ（1896行 → 将来的に約800行に）
├── database.py       # DB層（約200行）
├── utils.py          # ユーティリティ層（約400行）
├── templates/        # HTMLテンプレート
├── static/           # 静的ファイル
└── notion.db         # SQLiteデータベース
```

## 今後の展開

将来的には、さらに細かく分割することも検討できます：

- `routes.py` - すべてのAPIルート
- `models.py` - データモデル定義
- `services.py` - ビジネスロジック
- `config.py` - 設定管理

## 注意事項

現在は**互換性のため既存コードをそのまま残しています**。
モジュール版に完全移行する場合は、flask_app.py内の重複コードを削除する必要があります。
