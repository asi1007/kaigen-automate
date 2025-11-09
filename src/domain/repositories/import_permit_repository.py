"""輸入許可書リポジトリのインターフェース"""
from abc import ABC, abstractmethod
from pathlib import Path

from src.domain.entities.import_permit import ImportPermit


class IImportPermitRepository(ABC):
    """輸入許可書リポジトリのインターフェース"""

    @abstractmethod
    def parse(self, pdf_path: Path) -> ImportPermit:
        """PDF輸入許可書を解析する

        Args:
            pdf_path: PDFファイルのパス

        Returns:
            ImportPermit: 解析された輸入許可書エンティティ

        Raises:
            ValueError: PDFの解析に失敗した場合
        """
        pass

