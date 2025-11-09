"""PDF輸入許可書パーサー（Gemini API使用）"""
import logging
import os
from pathlib import Path

from src.domain.entities.import_permit import ImportPermit
from src.infrastructure.pdf_parser.gemini_import_permit_parser import GeminiImportPermitParser

logger = logging.getLogger(__name__)


class ImportPermitParser:
    """PDF輸入許可書を解析してImportPermitエンティティに変換する（Gemini APIを使用）"""
    
    def __init__(self, api_key: str | None = None):
        """パーサーを初期化する

        Args:
            api_key: Gemini APIキー（Noneの場合は環境変数から取得）
        """
        if api_key is None:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY環境変数が設定されていません")
        
        # APIキーをクリーニング（前後の空白や改行を削除）
        api_key = api_key.strip()
        if not api_key:
            raise ValueError("GEMINI_API_KEYが空です")
        
        self.gemini_parser = GeminiImportPermitParser(api_key=api_key)

    def parse(self, pdf_path: Path) -> ImportPermit:
        """PDF輸入許可書を解析する

        Args:
            pdf_path: PDFファイルのパス

        Returns:
            ImportPermit: 解析された輸入許可書エンティティ

        Raises:
            ValueError: PDFの解析に失敗した場合
        """
        return self.gemini_parser.parse(pdf_path)
