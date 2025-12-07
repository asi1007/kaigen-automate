"""請求書から経理を作成するユースケース"""
import logging
from pathlib import Path

from src.domain.entities.invoice import Invoice
from src.domain.repositories.moneyforward_repository import IMoneyforwardRepository
from src.infrastructure.pdf_parser.invoice_parser import InvoiceParser

logger = logging.getLogger(__name__)


class CreateAccountingFromInvoiceUseCase:
    """請求書PDFからマネーフォワードの経理を作成するユースケース"""

    def __init__(
        self,
        invoice_parser: InvoiceParser,
        moneyforward_repository: IMoneyforwardRepository,
    ):
        self.invoice_parser = invoice_parser
        self.moneyforward_repository = moneyforward_repository

    async def execute(self, pdf_path: Path) -> str:
        """請求書PDFから経理を作成する

        Args:
            pdf_path: 請求書PDFファイルのパス

        Returns:
            str: 作成された経理のID

        Raises:
            ValueError: PDFの解析に失敗した場合
            Exception: 経理作成に失敗した場合
        """
        logger.info(f"請求書から経理を作成する処理を開始します: {pdf_path}")

        try:
            # ステップ1: PDFを解析してInvoiceエンティティに変換
            logger.info("ステップ1: 請求書PDFを解析中...")
            invoice = self.invoice_parser.parse(pdf_path)
            logger.info(
                f"請求書の解析が完了しました: {invoice.invoice_number} "
                f"(金額: ¥{invoice.total_amount:,})"
            )

            # ステップ2: マネーフォワードに経理を登録
            logger.info("ステップ2: マネーフォワードに経理を登録中...")
            transaction_id = await self.moneyforward_repository.create_transaction(invoice)
            logger.info(f"経理の登録が完了しました: {transaction_id}")

            logger.info(
                f"処理完了: 請求書 {invoice.invoice_number} から経理 {transaction_id} を作成しました"
            )
            return transaction_id

        except ValueError as e:
            logger.error(f"請求書の解析に失敗しました: {e}")
            raise
        except Exception as e:
            logger.error(f"経理作成中にエラーが発生しました: {e}")
            raise








