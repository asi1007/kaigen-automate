"""ドキュメントエンティティ"""
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime


@dataclass(frozen=True)
class Document:
    """ダウンロードされたドキュメントを表すエンティティ"""

    file_path: Path
    download_url: str
    document_type: str
    download_datetime: datetime

    def __post_init__(self):
        """バリデーション"""
        if not self.file_path.exists():
            raise ValueError(f"ファイルが存在しません: {self.file_path}")

