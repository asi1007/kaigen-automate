"""マネーフォワード経理登録リポジトリのインターフェース"""
from abc import ABC, abstractmethod

from src.domain.entities.invoice import Invoice
from src.domain.entities.import_permit import ImportPermit


class IMoneyforwardRepository(ABC):
    """マネーフォワード経理登録リポジトリのインターフェース"""

    @abstractmethod
    async def create_transaction(self, invoice: Invoice) -> str:
        """請求書から経理を作成する

        Args:
            invoice: 請求書エンティティ

        Returns:
            str: 作成された経理のID

        Raises:
            Exception: 経理作成に失敗した場合
        """
        pass

    @abstractmethod
    async def create_transaction_from_import_permit(self, import_permit: ImportPermit) -> str:
        """輸入許可書から経理を作成する

        Args:
            import_permit: 輸入許可書エンティティ

        Returns:
            str: 作成された経理のID

        Raises:
            Exception: 経理作成に失敗した場合
        """
        pass



