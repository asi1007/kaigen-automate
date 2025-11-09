"""ダウンロードのみのユースケース"""
import logging
from typing import List

from src.domain.entities.document import Document
from src.domain.repositories.download_repository import IDownloadRepository

logger = logging.getLogger(__name__)


class DownloadOnlyUseCase:
    """ドキュメントをダウンロードのみ行うユースケース"""

    def __init__(
        self,
        download_repository: IDownloadRepository,
    ):
        self.download_repository = download_repository

    async def execute(self) -> List[Document]:
        """ドキュメントをダウンロードする

        Returns:
            List[Document]: ダウンロードされたドキュメントのリスト

        Raises:
            Exception: ダウンロード処理中にエラーが発生した場合
        """
        logger.info("ドキュメントのダウンロード処理を開始します")
        
        try:
            # ダウンロード
            documents = await self.download_repository.download_documents()
            
            if not documents:
                logger.warning("ダウンロード可能なドキュメントが見つかりませんでした")
                return []
            
            logger.info(f"{len(documents)} 件のドキュメントをダウンロードしました")
            
            return documents
        
        except Exception as e:
            logger.error(f"ダウンロード処理中にエラーが発生しました: {e}")
            raise

