"""輸入許可書パーサーの使用例"""
import asyncio
import logging
import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.domain.value_objects.credentials import Credentials
from src.infrastructure.pdf_parser.import_permit_parser import ImportPermitParser
from src.infrastructure.moneyforward.accounting_service import MoneyforwardAccountingService
from src.usecases.create_accounting_from_import_permit_use_case import CreateAccountingFromImportPermitUseCase

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def example_parse_import_permit():
    """輸入許可書PDFを解析する例"""
    # PDFファイルのパス
    pdf_path = Path("downloads/輸入許可書/YP5507887XX-2.pdf")
    
    # パーサーを初期化
    parser = ImportPermitParser()
    
    # PDFを解析
    import_permit = parser.parse(pdf_path)
    
    # 解析結果を表示
    print(f"輸入許可書番号: {import_permit.permit_number}")
    print(f"発行日: {import_permit.issue_date}")
    print(f"輸入者名: {import_permit.importer_name}")
    print(f"追跡番号: {import_permit.tracking_number}")
    print(f"関税: ¥{import_permit.customs_duty:,}")
    print(f"消費税: ¥{import_permit.consumption_tax:,}")
    print(f"地方消費税: ¥{import_permit.local_consumption_tax:,}")
    print(f"小計: ¥{import_permit.subtotal:,}")
    print(f"合計金額: ¥{import_permit.total_amount:,}")
    print(f"\n輸入項目:")
    for item in import_permit.items:
        print(f"  - {item.item_name}: ¥{item.amount:,} ({item.quantity} {item.unit})")


async def example_create_accounting_from_import_permit():
    """輸入許可書から経理を作成する例"""
    # PDFファイルのパス
    pdf_path = Path("downloads/輸入許可書/YP5507887XX-2.pdf")
    
    # 認証情報を設定（環境変数から取得する場合）
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    credentials = Credentials(
        username=os.getenv("MONEYFORWARD_USERNAME", ""),
        password=os.getenv("MONEYFORWARD_PASSWORD", "")
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
    # 例1: PDFを解析するだけ
    print("=== 例1: 輸入許可書PDFを解析 ===")
    example_parse_import_permit()
    
    # 例2: 経理を作成する（認証情報が必要）
    # print("\n=== 例2: 輸入許可書から経理を作成 ===")
    # asyncio.run(example_create_accounting_from_import_permit())

