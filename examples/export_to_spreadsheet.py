"""輸入許可書をスプレッドシートに出力する例"""
import asyncio
import logging
import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
import os

from src.infrastructure.pdf_parser.import_permit_parser import ImportPermitParser
from src.infrastructure.google_sheets.spreadsheet_service import GoogleSheetsService
from src.usecases.export_import_permit_to_spreadsheet_use_case import ExportImportPermitToSpreadsheetUseCase

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """メイン処理"""
    # 環境変数をロード
    load_dotenv()
    
    # スプレッドシート設定
    spreadsheet_id = os.getenv(
        "GOOGLE_SPREADSHEET_ID",
        "1Dvz3cS9DRGx4woEY0NNypgLPKxLZ55a4j8778YlCFls"
    )
    sheet_id = int(os.getenv("GOOGLE_SHEET_ID", "463665153"))
    service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
    delegated_subject = os.getenv("GOOGLE_DELEGATED_SUBJECT")
    
    # PDFファイルのパス
    pdf_path = Path("downloads/輸入許可書/YP5507887XX-2.pdf")
    
    if not pdf_path.exists():
        logger.error(f"PDFファイルが見つかりません: {pdf_path}")
        return
    
    # パーサーとリポジトリを初期化
    parser = ImportPermitParser()
    spreadsheet_service = GoogleSheetsService(
        spreadsheet_id=spreadsheet_id,
        sheet_id=sheet_id,
        service_account_file=service_account_file,
        delegated_subject=delegated_subject
    )
    
    # ユースケースを初期化
    use_case = ExportImportPermitToSpreadsheetUseCase(
        import_permit_parser=parser,
        spreadsheet_repository=spreadsheet_service
    )
    
    # スプレッドシートに出力
    await use_case.execute(pdf_path)
    logger.info("処理が完了しました")


if __name__ == "__main__":
    asyncio.run(main())

