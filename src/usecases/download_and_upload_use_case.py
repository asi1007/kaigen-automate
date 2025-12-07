import logging
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Set, TYPE_CHECKING

from src.domain.entities.document import Document
from src.domain.entities.import_permit import ImportPermit
from src.domain.entities.invoice import Invoice
from src.domain.repositories.download_repository import IDownloadRepository
from src.domain.repositories.upload_repository import IUploadRepository
from src.domain.repositories.spreadsheet_repository import ISpreadsheetRepository
from src.infrastructure.pdf_parser.import_permit_parser import ImportPermitParser
from src.infrastructure.pdf_parser.invoice_parser import InvoiceParser

if TYPE_CHECKING:
    from src.domain.value_objects.credentials import GoogleDriveCredentials

logger = logging.getLogger(__name__)


class DownloadAndUploadUseCase:

    def __init__(
        self,
        download_repository: IDownloadRepository,
        upload_repository: IUploadRepository,
        google_credentials: "GoogleDriveCredentials",
        spreadsheet_repository: Optional[ISpreadsheetRepository] = None,
    ):
        self.download_repository = download_repository
        self.upload_repository = upload_repository
        self.google_credentials = google_credentials
        self.spreadsheet_repository = spreadsheet_repository
        self.import_permit_parser = ImportPermitParser() if spreadsheet_repository else None
        self.invoice_parser = InvoiceParser() if spreadsheet_repository else None

    async def execute(self) -> List[Document]:
        logger.info("ドキュメントのダウンロードとアップロード処理を開始します")
        
        try:
            # ステップ1: ダウンロード
            documents = await self._download_documents()
            if not documents:
                return []
            
            # 解析済みデータを保持する辞書
            import_permit_dict: Dict[Path, ImportPermit] = {}
            invoice_dict: Dict[Path, Invoice] = {}
            skip_file_paths: Set[Path] = set()
            
            # ステップ2: 経理データ作成（スプレッドシートに出力）
            if self.spreadsheet_repository:
                await self._create_accounting_data(
                    documents, import_permit_dict, invoice_dict, skip_file_paths
                )
            
            # ステップ3: アップロード
            await self._upload_documents(
                documents, import_permit_dict, invoice_dict, skip_file_paths
            )
            
            return documents
        
        except Exception as e:
            logger.error(f"処理中にエラーが発生しました: {e}")
            raise

    async def _download_documents(self) -> List[Document]:
        logger.info("ステップ1: ドキュメントのダウンロード")
        documents = await self.download_repository.download_documents()
        
        if not documents:
            logger.warning("ダウンロード可能なドキュメントが見つかりませんでした")
            return []
        
        logger.info(f"{len(documents)} 件のドキュメントをダウンロードしました")
        return documents

    async def _create_accounting_data(
        self,
        documents: List[Document],
        import_permit_dict: Dict[Path, ImportPermit],
        invoice_dict: Dict[Path, Invoice],
        skip_file_paths: Set[Path],
    ) -> None:
        logger.info("ステップ2: 経理データ作成")
        import_permit_count = 0
        invoice_count = 0
        
        for document in documents:
            try:
                folder_id = self.google_credentials.get_folder_id(document.document_type)
                
                if document.document_type == "輸入許可書" and self.import_permit_parser:
                    result = await self._process_import_permit_for_accounting(
                        document, folder_id, import_permit_dict, skip_file_paths
                    )
                    if result:
                        import_permit_count += 1
                elif document.document_type == "請求書" and self.invoice_parser:
                    result = await self._process_invoice_for_accounting(
                        document, folder_id, invoice_dict, skip_file_paths
                    )
                    if result:
                        invoice_count += 1
            except Exception as e:
                logger.error(
                    f"経理データ作成失敗: {document.document_type} - {document.file_path.name} - {e}"
                )
                continue
        
        if import_permit_count > 0:
            logger.info(f"経理データ作成完了: {import_permit_count} 件の輸入許可書を処理しました")
        if invoice_count > 0:
            logger.info(f"経理データ作成完了: {invoice_count} 件の請求書を処理しました")

    async def _process_import_permit_for_accounting(
        self,
        document: Document,
        folder_id: str,
        import_permit_dict: Dict[Path, ImportPermit],
        skip_file_paths: Set[Path],
    ) -> bool:
        logger.info(
            f"経理データ作成中: {document.document_type} - {document.file_path.name}"
        )
        
        import_permit = self.import_permit_parser.parse(document.file_path)
        import_permit_dict[document.file_path] = import_permit

        exists_on_drive = await self.upload_repository.document_exists(
            document.file_path,
            folder_id,
            import_permit.issue_date
        )
        
        if exists_on_drive:
            logger.info(
                f"Google Driveに既存のためスプレッドシート出力とアップロードをスキップします: "
                f"{document.document_type} - {document.file_path.name}"
            )
            skip_file_paths.add(document.file_path)
            return False

        await self.spreadsheet_repository.write_import_permit(import_permit)
        logger.info(
            f"経理データ作成完了: {document.document_type} - {document.file_path.name}"
        )
        return True

    async def _process_invoice_for_accounting(
        self,
        document: Document,
        folder_id: str,
        invoice_dict: Dict[Path, Invoice],
        skip_file_paths: Set[Path],
    ) -> bool:
        logger.info(
            f"経理データ作成中: {document.document_type} - {document.file_path.name}"
        )
        
        invoice = self.invoice_parser.parse(document.file_path)
        invoice_dict[document.file_path] = invoice

        exists_on_drive = await self.upload_repository.document_exists(
            document.file_path,
            folder_id,
            invoice.issue_date
        )
        
        if exists_on_drive:
            logger.info(
                f"Google Driveに既存のためスプレッドシート出力とアップロードをスキップします: "
                f"{document.document_type} - {document.file_path.name}"
            )
            skip_file_paths.add(document.file_path)
            return False

        await self.spreadsheet_repository.write_invoice(invoice)
        logger.info(
            f"経理データ作成完了: {document.document_type} - {document.file_path.name}"
        )
        return True

    async def _upload_documents(
        self,
        documents: List[Document],
        import_permit_dict: Dict[Path, ImportPermit],
        invoice_dict: Dict[Path, Invoice],
        skip_file_paths: Set[Path],
    ) -> None:
        logger.info("ステップ3: Google Drive へのアップロード")
        uploaded_count = 0

        for document in documents:
            try:
                issue_date = self._get_issue_date(
                    document, import_permit_dict, invoice_dict
                )
                folder_id = self.google_credentials.get_folder_id(document.document_type)

                if document.file_path in skip_file_paths:
                    logger.info(
                        f"Google Driveに既存のためアップロードをスキップします: "
                        f"{document.document_type} - {document.file_path.name}"
                    )
                    continue

                if await self.upload_repository.document_exists(
                    document.file_path,
                    folder_id,
                    issue_date
                ):
                    skip_file_paths.add(document.file_path)
                    logger.info(
                        f"Google Driveに既存のためアップロードをスキップします: "
                        f"{document.document_type} - {document.file_path.name}"
                    )
                    continue
                
                logger.info(
                    f"アップロード中: {document.document_type} - {document.file_path.name}"
                )
                await self.upload_repository.upload_document(
                    document.file_path,
                    folder_id,
                    issue_date=issue_date
                )
                uploaded_count += 1
                logger.info(
                    f"アップロード完了: {document.document_type} - {document.file_path.name}"
                )
            except Exception as e:
                logger.error(
                    f"アップロード失敗: {document.document_type} - {document.file_path.name} - {e}"
                )
                continue
            finally:
                self._remove_local_file(document.file_path)
        
        logger.info(
            f"処理完了: {uploaded_count}/{len(documents)} 件のアップロードに成功しました"
        )

    def _get_issue_date(
        self,
        document: Document,
        import_permit_dict: Dict[Path, ImportPermit],
        invoice_dict: Dict[Path, Invoice],
    ) -> date:
        if document.document_type == "輸入許可書":
            if document.file_path in import_permit_dict:
                return import_permit_dict[document.file_path].issue_date
            
            if self.import_permit_parser:
                try:
                    import_permit = self.import_permit_parser.parse(document.file_path)
                    import_permit_dict[document.file_path] = import_permit
                    return import_permit.issue_date
                except Exception as e:
                    logger.warning(f"日付取得失敗（ダウンロード日時を使用）: {e}")
            
            return document.download_datetime.date()
        
        elif document.document_type == "請求書":
            if document.file_path in invoice_dict:
                return invoice_dict[document.file_path].issue_date
            
            if self.invoice_parser:
                try:
                    invoice = self.invoice_parser.parse(document.file_path)
                    invoice_dict[document.file_path] = invoice
                    return invoice.issue_date
                except Exception as e:
                    logger.warning(f"日付取得失敗（ダウンロード日時を使用）: {e}")
            
            return document.download_datetime.date()
        
        else:
            return document.download_datetime.date()

    def _remove_local_file(self, file_path: Path) -> None:
        try:
            if file_path.exists():
                file_path.unlink()
                logger.debug(f"ローカルファイルを削除しました: {file_path}")
            root_dir = Path(getattr(self.download_repository, "download_dir", file_path.parent))
            current = file_path.parent
            while current != root_dir.parent:
                try:
                    current.rmdir()
                except OSError:
                    break
                if current == root_dir:
                    break
                current = current.parent
        except Exception as e:
            logger.warning(f"ローカルファイルの削除に失敗しました: {file_path} - {e}")

