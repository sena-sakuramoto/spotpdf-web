# SpotPDF Web Application

Web版のPDF差分比較アプリケーションです。デスクトップアプリの機能をブラウザで利用できます。

## 機能

- **ドラッグ&ドロップファイルアップロード**: 2つのPDFファイルを簡単にアップロード
- **リアルタイム比較**: サーバーサイドでピクセルレベルの差分検出
- **インタラクティブ表示**: ブラウザで結果を確認、ページ送り、表示切り替え
- **Google認証**: 既存のGoogle OAuth設定を使用
- **ユーザー管理**: Google Sheetsによる認証ユーザー管理
- **結果ダウンロード**: 差分画像とPDFレポートのダウンロード

## セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements_web.txt
```

### 2. 設定ファイル

既存の `GoogleLoginLauncher/SpotPDFLauncher.config.json` がそのまま使用されます。

### 3. アプリケーションの起動

```bash
python run_web.py
```

または

```bash
python web_app.py
```

ブラウザで `http://localhost:5000` にアクセスします。

## Docker での起動

### 基本起動

```bash
docker build -t spotpdf-web .
docker run -p 5000:5000 -v $(pwd)/uploads:/app/uploads spotpdf-web
```

### Docker Compose での起動

```bash
docker-compose up -d
```

## API エンドポイント

### 認証

- `GET /` - メインページ（認証必要）
- `GET /login` - ログインページ
- `POST /auth/google` - Google OAuth認証
- `GET /logout` - ログアウト

### ファイル処理

- `POST /upload` - PDFファイルアップロードと比較処理
- `GET /download/<filename>` - 結果ファイルダウンロード
- `GET /status` - 認証状態確認

## 使用方法

### 1. ログイン
- ブラウザでアプリケーションにアクセス
- Googleアカウントでログイン
- 認証済みユーザーのみアクセス可能

### 2. PDF比較
1. **ファイルアップロード**: 比較元と比較先のPDFをドラッグ&ドロップまたは選択
2. **設定調整**: 
   - 差分検出感度（1-50）
   - 表示フィルタ（追加/削除部分の表示切り替え）
   - エクスポートオプション
3. **比較実行**: 「比較実行」ボタンをクリック

### 3. 結果表示
- **ページ送り**: 前/次ボタンでページを切り替え
- **表示切り替え**: 追加のみ/削除のみ/重複表示を選択
- **ダウンロード**: 画像ファイルやPDFレポートをダウンロード

## ファイル構成

```
├── web_app.py              # メインFlaskアプリケーション
├── run_web.py              # アプリケーションランチャー
├── templates/              # HTMLテンプレート
│   ├── base.html          # 基本テンプレート
│   ├── login.html         # ログインページ
│   └── index.html         # メインページ
├── static/                 # 静的ファイル
│   ├── config.json        # フロントエンド設定
│   └── outputs/           # 比較結果保存
├── uploads/               # アップロードファイル一時保存
├── requirements_web.txt   # Python依存関係
├── Dockerfile            # Docker設定
├── docker-compose.yml    # Docker Compose設定
└── nginx.conf           # Nginx設定（プロダクション用）
```

## セキュリティ機能

- **レート制限**: アップロード・API呼び出しの頻度制限
- **ファイル制限**: PDFファイルのみ、最大50MB
- **認証確認**: 各リクエストでセッション認証
- **ユーザー管理**: Google Sheetsベースの認証ユーザー管理
- **セキュリティヘッダー**: Nginx経由でのセキュリティヘッダー追加

## プロダクション環境

### Nginx + Docker Compose

```bash
# SSL証明書配置
mkdir ssl
# SSL証明書ファイルを ssl/ ディレクトリに配置

# 本番環境起動
docker-compose up -d

# ログ確認
docker-compose logs -f spotpdf-web
```

### 設定のカスタマイズ

- `nginx.conf`: リバースプロキシとセキュリティ設定
- `docker-compose.yml`: コンテナとボリューム設定
- `web_app.py`: Flask設定（ポート、デバッグモードなど）

## トラブルシューティング

### よくある問題

1. **設定ファイルが見つからない**
   - `GoogleLoginLauncher/SpotPDFLauncher.config.json` の存在確認
   - JSON形式の確認

2. **認証エラー**
   - Google Console でOAuth設定確認
   - リダイレクトURIの設定確認

3. **ファイルアップロードエラー**
   - ファイルサイズ制限確認（デフォルト50MB）
   - PDFファイル形式確認

4. **処理エラー**
   - ログファイル `web_app.log` 確認
   - PyMuPDF, OpenCVの依存関係確認

### ログ確認

```bash
# アプリケーションログ
tail -f web_app.log

# Dockerログ
docker-compose logs -f
```

## 開発・拡張

### 新機能追加

1. `web_app.py` にAPIエンドポイント追加
2. `templates/` にHTMLテンプレート追加
3. `static/` に静的ファイル追加

### テスト実行

```bash
# 基本テスト（手動）
python run_web.py

# ブラウザテスト
# http://localhost:5000 にアクセスして機能確認
```