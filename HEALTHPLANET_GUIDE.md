# Health Planet 連携 実装ガイド

このドキュメントは、Health Planet（タニタの健康管理サービス）との連携実装をまとめたものです。

## 概要

便利記録は、タニタの体重計・体組成計と連携して、健康データを自動で記録できるよう実装されました。シンプルで使いやすい設計を心がけています。

## 実装される内容

### ページ
- **`/healthplanet`** - Health Planet 専用ページ
  - 連携ステータス表示
  - 最新のデータ表示（体重、計測日時）
  - 連携・同期操作ボタン
  - 手動同期機能

### メインページの機能
- **サイドバー** - 「⚖️ Health Planet」ボタン
  - 連携状況をポップアップで表示
  - 詳細ページへのリンク

### API エンドポイント
すべて `/api/healthplanet/` 配下

| エンドポイント | メソッド | 説明 |
|---|---|---|
| `/auth` | GET | OAuth 認可フロー開始 |
| `/callback` | GET | OAuth コールバック（自動） |
| `/status` | GET | 連携状況確認 |
| `/disconnect` | POST | 連携を解除 |
| `/sync` | POST | 今日のデータを同期 |
| `/latest-weight` | GET | 最新の体重データ取得 |

## 設定されている情報

### `.env` ファイル

```dotenv
HEALTHPLANET_CLIENT_ID=39349.Z1fqIos8Qg.apps.healthplanet.jp
HEALTHPLANET_CLIENT_SECRET=1770513240597-fBgbT6q6NexGMsxjGZ6Ec0oNSLs5V9JHaWOvPlv6
HEALTHPLANET_REDIRECT_URI=https://nnnkeita.pythonanywhere.com/api/healthplanet/callback
HEALTHPLANET_SCOPE=innerscan
```

⚠️ **注意**: これらの認証情報は本番環境用です。ローカル開発環境で使用する際は、`HEALTHPLANET_REDIRECT_URI` を `http://localhost:5000/api/healthplanet/callback` に変更してください。

## 使用方法

### 1. Health Planet に連携する

メインページのサイドバーから「⚖️ Health Planet」をクリック、または `/healthplanet` にアクセスします。

表示される「Health Planet に連携する」ボタンをクリックすると、タニタのログインページにリダイレクトされます。

### 2. データを同期する

連携後、「今すぐ同期」ボタンでデータを取得できます。

### 3. 連携を解除する

「連携を解除」ボタンで、いつでも連携を削除できます。

## トラブルシューティング

### 連携に失敗する

**症状**: "認可に失敗しました" というメッセージが表示される

**原因と対策**:
1. `.env` の `HEALTHPLANET_CLIENT_ID` が正しいか確認
2. `HEALTHPLANET_REDIRECT_URI` がタニタの設定と一致しているか確認
3. タニタのアカウント設定でアプリケーションが許可されているか確認

### トークンが期限切れ

**症状**: "トークン期限切れです。再度認可してください" というメッセージ

**解決方法**: 連携ページから再度連携ボタンをクリックして認可し直してください。

### データが見つからない

**症状**: "この 30 日間に体重データが見つかりません" というメッセージ

**原因と対策**:
1. タニタデバイスで最近計測をしていない
2. Health Planet アカウントにデータが同期されていない
3. タニタアプリまたは Web から計測データを確認してください

### API エラー

**症状**: "Health Planet API からエラーが返されました"

**原因と対策**:
1. Health Planet のサービスが利用可能か確認
2. トークンが無効の可能性 - 再度連携してください
3. ネットワーク接続を確認してください

## 開発者向け情報

### データベース

新しいテーブル: `healthplanet_tokens`

```sql
CREATE TABLE healthplanet_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TIMESTAMP,
    scope TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### ページテーブル拡張

新しいカラムが追加されました：

```sql
ALTER TABLE pages ADD COLUMN weight REAL DEFAULT NULL;  -- 体重データ
ALTER TABLE pages ADD COLUMN weight_at TEXT DEFAULT NULL;  -- 計測日時
```

### ブロック props

Health Planet で追加されたブロックは、`props` に以下のメタデータを含みます：

```json
{
  "source": "healthplanet",
  "type": "body"
}
```

## 今後の機能拡張案

- [ ] 定期自動同期（スケジューラー）
- [ ] グラフ表示（体重推移）
- [ ] 日記への自動挿入
- [ ] 食事データとの連携
- [ ] 複数デバイスの対応
- [ ] Linux における体組成計データの取得

## 参考リンク

- [Health Planet API ドキュメント](https://www.healthplanet.jp/oauth/guide)
- [タニタ Health Planet](https://www.healthplanet.jp/)

