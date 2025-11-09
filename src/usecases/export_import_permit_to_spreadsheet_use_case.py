"""輸入許可書をスプレッドシートに出力するユースケース"""
import logging
from pathlib import Path

from src.domain.entities.import_permit import ImportPermit
from src.domain.repositories.spreadsheet_repository import ISpreadsheetRepository
from src.infrastructure.pdf_parser.import_permit_parser import ImportPermitParser

logger = logging.getLogger(__name__)


class ExportImportPermitToSpreadsheetUseCase:
    """輸入許可書PDFを解析してスプレッドシートに出力するユースケース"""

    def __init__(
        self,
        import_permit_parser: ImportPermitParser,
        spreadsheet_repository: ISpreadsheetRepository,
    ):
        self.import_permit_parser = import_permit_parser
        self.spreadsheet_repository = spreadsheet_repository

    async def execute(self, pdf_path: Path) -> None:
        """輸入許可書PDFを解析してスプレッドシートに出力する

        Args:
            pdf_path: 輸入許可書PDFファイルのパス

        Raises:
            ValueError: PDFの解析に失敗した場合
            Exception: スプレッドシートへの書き込みに失敗した場合
        """
        logger.info(f"輸入許可書をスプレッドシートに出力する処理を開始します: {pdf_path}")

        try:
            # ステップ1: PDFを解析してImportPermitエンティティに変換
            logger.info("ステップ1: 輸入許可書PDFを解析中...")
            import_permit = self.import_permit_parser.parse(pdf_path)
            logger.info(
                f"輸入許可書の解析が完了しました: {import_permit.permit_number} "
                f"(金額: ¥{import_permit.total_amount:,})"
            )

            # ステップ2: スプレッドシートに書き込み
            logger.info("ステップ2: スプレッドシートに書き込み中...")
            await self.spreadsheet_repository.write_import_permit(import_permit)
            logger.info(f"スプレッドシートへの書き込みが完了しました: {import_permit.permit_number}")

            logger.info(
                f"処理完了: 輸入許可書 {import_permit.permit_number} をスプレッドシートに出力しました"
            )

        except ValueError as e:
            logger.error(f"輸入許可書の解析に失敗しました: {e}")
            raise
        except Exception as e:
            logger.error(f"スプレッドシートへの書き込み中にエラーが発生しました: {e}")
            raise

