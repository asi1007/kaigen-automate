"""Googleスプレッドシートリポジトリのインターフェース"""
from abc import ABC, abstractmethod

from src.domain.entities.import_permit import ImportPermit


class ISpreadsheetRepository(ABC):
    """Googleスプレッドシートリポジトリのインターフェース"""

    @abstractmethod
    async def write_import_permit(self, import_permit: ImportPermit) -> None:
        """輸入許可書のデータをスプレッドシートに書き込む

        Args:
            import_permit: 輸入許可書エンティティ

        Raises:
            Exception: 書き込みに失敗した場合
        """
        pass

