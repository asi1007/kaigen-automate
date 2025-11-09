"""ダウンロードリポジトリのインターフェース"""
from abc import ABC, abstractmethod
from typing import List

from src.domain.entities.document import Document


class IDownloadRepository(ABC):
    """ドキュメントダウンロードリポジトリのインターフェース"""

    @abstractmethod
    async def download_documents(self) -> List[Document]:
        """請求書と輸入許可書をダウンロードする

        Returns:
            List[Document]: ダウンロードされたドキュメントのリスト
        """
        pass

