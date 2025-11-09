# 輸入許可書ドメインモデルの使い方

輸入許可書PDFから経理用データを読み込むドメインモデルの使い方を説明します。

## 基本的な使い方

### 1. PDFを解析するだけの場合

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
print(f"発行日: {import_permit.issue_date}")
print(f"輸入者名: {import_permit.importer_name}")
print(f"追跡番号: {import_permit.tracking_number}")
print(f"関税: ¥{import_permit.customs_duty:,}")
print(f"消費税: ¥{import_permit.consumption_tax:,}")
print(f"地方消費税: ¥{import_permit.local_consumption_tax:,}")
print(f"小計: ¥{import_permit.subtotal:,}")
print(f"合計金額: ¥{import_permit.total_amount:,}")

# 輸入項目を表示
for item in import_permit.items:
    print(f"  - {item.item_name}: ¥{item.amount:,} ({item.quantity} {item.unit})")
```

### 2. マネーフォワードに経理を登録する場合

```python
import asyncio
from pathlib import Path
from src.domain.value_objects.credentials import Credentials
from src.infrastructure.pdf_parser.import_permit_parser import ImportPermitParser
from src.infrastructure.moneyforward.accounting_service import MoneyforwardAccountingService
from src.usecases.create_accounting_from_import_permit_use_case import CreateAccountingFromImportPermitUseCase

async def main():
    # PDFファイルのパス
    pdf_path = Path("downloads/輸入許可書/YP5507887XX-2.pdf")
    
    # 認証情報を設定
    credentials = Credentials(
        username="your_email@example.com",
        password="your_password"
    )
    
    # パーサーとリポジトリを初期化
    parser = ImportPermitParser()
    moneyforward_repository = MoneyforwardAccountingService(credentials)
    
    # ユースケースを初期化
    use_case = CreateAccountingFromImportPermitUseCase(
        import_permit_parser=parser,
        moneyforward_repository=moneyforward_repository
    )
    
    # 経理を作成
    transaction_id = await use_case.execute(pdf_path)
    print(f"経理が作成されました: {transaction_id}")

if __name__ == "__main__":
    asyncio.run(main())
```

## ImportPermitエンティティの構造

```python
@dataclass(frozen=True)
class ImportPermit:
    permit_number: str              # 輸入許可書番号
    issue_date: date                # 発行日
    importer_name: str              # 輸入者名
    tracking_number: str           # 追跡番号
    total_amount: Decimal           # 合計金額
    customs_duty: Decimal          # 関税額
    consumption_tax: Decimal      # 消費税額
    local_consumption_tax: Decimal # 地方消費税額
    subtotal: Decimal              # 小計
    items: List[ImportPermitItem]  # 輸入項目リスト
    pdf_path: Path                 # PDFファイルのパス
```

## ImportPermitItem値オブジェクトの構造

```python
@dataclass(frozen=True)
class ImportPermitItem:
    item_name: str      # 項目名
    amount: Decimal     # 金額
    quantity: Decimal   # 数量
    unit: str           # 単位
```

## 実行例

実際のPDFファイルを使って実行する場合:

```bash
# プロジェクトルートから実行
python examples/import_permit_usage.py
```

## エラーハンドリング

パーサーは以下の場合に`ValueError`を発生させます：

- PDFファイルが存在しない場合
- PDFからテキストを抽出できない場合
- 必要な情報（許可書番号、発行日など）を抽出できない場合

```python
try:
    import_permit = parser.parse(pdf_path)
except ValueError as e:
    print(f"解析エラー: {e}")
```

