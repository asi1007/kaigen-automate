# 海源物流自動化ツール

海源物流の請求書・輸入許可書を自動的にダウンロードし、Google Driveにアップロードする自動化ツールです。

## 機能

- 海源物流への自動ログイン
- 請求書・輸入許可書の自動検出とダウンロード
- 輸入許可書PDFの解析とGoogleスプレッドシートへの経理データ出力（マネーフォワード形式）
- Google Driveへの自動アップロード
- 請求書・輸入許可書PDFの解析機能
- マネーフォワードへの経理登録機能
- リトライ機能（tenacity）
- 詳細なログ出力
- DDD（ドメイン駆動設計）による構造化

## 技術スタック

- **Python 3.10+**
- **Playwright**: Web自動化
- **Google Drive API**: ファイルアップロード
- **tenacity**: リトライ処理
- **pydantic**: データ検証
- **pytest**: テストフレームワーク

## セットアップ

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd kaigen-automate
```

### 2. 依存パッケージのインストール

Poetryを使用する場合:

```bash
poetry install
```

または、pipを使用する場合:

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Google Drive API認証情報の設定（OAuth 2.0）

個人アカウントのGoogle Driveを使用するため、OAuth 2.0認証を設定します。

#### OAuth認証情報の取得手順

1. [Google Cloud Console](https://console.cloud.google.com/)でプロジェクトを作成
   - 既存のプロジェクトを使用するか、新規プロジェクトを作成

2. Google Drive APIを有効化
   - 「APIとサービス」→「ライブラリ」から「Google Drive API」を検索して有効化
   - Google Sheets APIも使用する場合は「Google Sheets API」も有効化

3. OAuth認証情報を作成
   - 「APIとサービス」→「認証情報」を開く
   - 「認証情報を作成」→「OAuth クライアント ID」を選択
   - アプリケーションの種類: 「デスクトップアプリ」を選択
   - 名前: 任意の名前（例: "Kaigen Automate"）
   - 「作成」をクリック

4. OAuth認証情報をダウンロード
   - 作成したOAuthクライアントIDの右側にある「ダウンロード」ボタンをクリック
   - ダウンロードしたJSONファイルを `credentials.json` としてプロジェクトルートに配置

5. アップロード先フォルダの準備
   - Google Driveにアクセス
   - アップロード先のフォルダを開く
   - フォルダのURLからフォルダIDを取得
     - URL例: `https://drive.google.com/drive/folders/1mVX9YY0Y0OwBIbF5pxMvEYUwUgkukGJ5`
     - フォルダID: `1mVX9YY0Y0OwBIbF5pxMvEYUwUgkukGJ5`（URLの最後の部分）

#### 初回認証フロー

初回実行時、ブラウザが自動的に開き、Googleアカウントでの認証が求められます：
1. ブラウザでGoogleアカウントにログイン
2. アプリケーションへのアクセス許可を確認
3. 認証が完了すると、`token.json` が自動生成されます
4. 次回以降は保存されたトークンを使用するため、再認証は不要です

**注意**: トークンが無効になった場合は、`token.json` を削除して再認証してください。

### 4. 環境変数の設定

`.env.example` を `.env` にコピーして編集:

```bash
cp env.example .env
```

`.env` ファイルを編集:

```env
# 海源物流のログイン情報
KAIGEN_USERNAME=2408024602
KAIGEN_PASSWORD=Yamada0402
KAIGEN_BASE_URL=https://japan-kaigen.net

# Google Drive設定
GOOGLE_DRIVE_FOLDER_ID=1mVX9YY0Y0OwBIbF5pxMvEYUwUgkukGJ5
# OAuth認証情報JSONファイル（Google Cloud Consoleで取得）
GOOGLE_CREDENTIALS_FILE=credentials.json
# トークン保存先ファイル（デフォルト: token.json）
GOOGLE_TOKEN_FILE=token.json

# ログレベル
LOG_LEVEL=INFO
```

## 使用方法

### 基本実行

#### ダウンロード・経理データ作成・アップロードモード（デフォルト）

```bash
poetry run python run.py
```

または:

```bash
python run.py
```

このモードでは、以下の順序で処理が実行されます：

1. **ステップ1: ダウンロード** - 海源物流から請求書・輸入許可書をダウンロード
2. **ステップ2: 経理データ作成** - 輸入許可書PDFを解析してGoogleスプレッドシートに経理データを出力（マネーフォワード形式）
3. **ステップ3: アップロード** - ダウンロードしたPDFファイルをGoogle Driveにアップロード

**注意**: 経理データ作成機能を使用するには、環境変数に`GOOGLE_SPREADSHEET_ID`と`GOOGLE_SHEET_ID`を設定してください。設定がない場合は、経理データ作成ステップがスキップされます。

### 初回実行時の注意

初回実行時、ブラウザが自動的に開き、Googleアカウントでの認証が求められます：
1. ブラウザでGoogleアカウントにログイン
2. アプリケーションへのアクセス許可を確認
3. 認証が完了すると、`token.json` が自動生成されます
4. 次回以降は保存されたトークンを使用するため、再認証は不要です

**注意**: トークンが無効になった場合は、`token.json` を削除して再認証してください。

### 輸入許可書PDFの解析

輸入許可書PDFから経理用データを読み込む場合:

```python
from pathlib import Path
from src.infrastructure.pdf_parser.import_permit_parser import ImportPermitParser

# PDFファイルのパス
pdf_path = Path("downloads/輸入許可書/YP5507887XX-2.pdf")

# パーサーを初期化
parser = ImportPermitParser()

# PDFを解析
import_permit = parser.parse(pdf_path)

# 解析結果にアクセス
print(f"輸入許可書番号: {import_permit.permit_number}")
print(f"関税: ¥{import_permit.customs_duty:,}")
print(f"消費税: ¥{import_permit.consumption_tax:,}")
print(f"地方消費税: ¥{import_permit.local_consumption_tax:,}")
print(f"合計金額: ¥{import_permit.total_amount:,}")
```

詳細な使い方は [`docs/import_permit_usage.md`](docs/import_permit_usage.md) を参照してください。

### 輸入許可書をGoogleスプレッドシートに出力

輸入許可書PDFから経理データを抽出してGoogleスプレッドシートに出力する場合:

```python
import asyncio
from pathlib import Path
from src.infrastructure.pdf_parser.import_permit_parser import ImportPermitParser
from src.infrastructure.google_sheets.spreadsheet_service import GoogleSheetsService
from src.usecases.export_import_permit_to_spreadsheet_use_case import ExportImportPermitToSpreadsheetUseCase

async def main():
    pdf_path = Path("downloads/輸入許可書/YP5507887XX-2.pdf")
    
    # パーサーとリポジトリを初期化
    parser = ImportPermitParser()
    spreadsheet_service = GoogleSheetsService(
        spreadsheet_id="1Dvz3cS9DRGx4woEY0NNypgLPKxLZ55a4j8778YlCFls",
        sheet_id=463665153,
        credentials_file="credentials.json",
        token_file="token.json"
    )
    
    # ユースケースを初期化
    use_case = ExportImportPermitToSpreadsheetUseCase(
        import_permit_parser=parser,
        spreadsheet_repository=spreadsheet_service
    )
    
    # スプレッドシートに出力
    await use_case.execute(pdf_path)

if __name__ == "__main__":
    asyncio.run(main())
```

環境変数を使用する場合:

```bash
# .envファイルに設定
GOOGLE_SPREADSHEET_ID=1Dvz3cS9DRGx4woEY0NNypgLPKxLZ55a4j8778YlCFls
GOOGLE_SHEET_ID=463665153
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_TOKEN_FILE=token.json
```

実行例:

```bash
python examples/export_to_spreadsheet.py
```

**出力形式**: マネーフォワードのインポート形式に合わせて以下の列で出力されます:
- **日付**: YYYY/MM/DD形式（例: 2025/11/08）
- **内容**: 取引の内容（例: 輸入許可書 YP5507887XX 関税）
- **金額**: 取引金額（数値）
- **勘定科目**: 勘定科目名（関税、租税公課、仕入など）
- **補助科目**: 補助科目（空欄）
- **メモ**: 備考・詳細情報（輸入許可書番号、追跡番号、内訳など）

輸入許可書1件につき、以下の行が作成されます:
1. 関税の行（関税額が0より大きい場合）
2. 消費税の行（消費税額が0より大きい場合）
3. 地方消費税の行（地方消費税額が0より大きい場合）
4. 合計金額の行（仕入として）

**注意**: 
- Google Sheets APIを使用するには、Google Cloud ConsoleでGoogle Sheets APIを有効化する必要があります。
- スプレッドシートの1行目にヘッダー行（日付、内容、金額、勘定科目、補助科目、メモ）を設定してください。

## プロジェクト構造

```
kaigen-automate/
├── src/
│   ├── domain/                  # ドメイン層
│   │   ├── entities/            # エンティティ
│   │   ├── value_objects/       # 値オブジェクト
│   │   └── repositories/        # リポジトリインターフェース
│   ├── infrastructure/          # インフラストラクチャ層
│   │   ├── playwright/          # Playwright実装
│   │   └── google_drive/        # Google Drive API実装
│   ├── usecases/                # ユースケース層
│   └── main.py                  # エントリーポイント
├── tests/                       # テストコード
│   ├── test_download_service.py
│   ├── test_upload_service.py
│   └── test_use_case.py
├── pyproject.toml              # Poetry設定
├── env.example                 # 環境変数テンプレート
└── README.md                   # このファイル
```

## テストの実行

```bash
# すべてのテストを実行
poetry run pytest

# カバレッジ付きで実行
poetry run pytest --cov=src --cov-report=html
```

## 設計思想

### ドメイン駆動設計（DDD）

このプロジェクトは以下のレイヤーに分離されています:

1. **ドメイン層**: ビジネスロジックとビジネスルール
2. **インフラストラクチャ層**: 外部サービス（Playwright、Google Drive）との連携
3. **ユースケース層**: アプリケーション固有のロジック

### リポジトリパターン

外部依存を抽象化するため、`IDownloadRepository` と `IUploadRepository` のインターフェースを定義しています。
これにより、実装を容易に差し替え可能です。

## トラブルシューティング

### ログインに失敗する場合

- ユーザー名とパスワードが正しいか確認
- ネットワーク接続を確認
- 海源物流のサイトがメンテナンス中でないか確認

### Google Driveアップロードに失敗する場合

- `credentials.json` が正しく配置されているか確認
- Google Drive APIが有効になっているか確認
- OAuth認証情報が正しく設定されているか確認
- トークンを削除して再認証（`token.json` を削除して再実行）
- ブラウザが開かない場合は、ファイアウォールやセキュリティソフトの設定を確認

### ダウンロードリンクが見つからない場合

- サイトの構造が変更された可能性があります
- ログレベルを `DEBUG` に設定して詳細を確認

```env
LOG_LEVEL=DEBUG
```

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## 貢献

プルリクエストやイシューの報告を歓迎します。

