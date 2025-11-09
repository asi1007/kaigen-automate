"""アップロードリポジトリのインターフェース"""
from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path
from typing import Optional


class IUploadRepository(ABC):
    """Google Driveアップロードリポジトリのインターフェース"""

    @abstractmethod
    async def document_exists(
        self, file_path: Path, folder_id: str, issue_date: Optional[date] = None
    ) -> bool:
        """同名のドキュメントが既に存在するかを確認する

        Args:
            file_path: 確認対象のファイルパス
            folder_id: フォルダID
            issue_date: 文書の発行日（オプション）
        """
        pass

    @abstractmethod
    async def upload_document(
        self, file_path: Path, folder_id: str, issue_date: Optional[date] = None
    ) -> None:
        """ドキュメントをアップロードする

        Args:
            file_path: アップロードするファイルのパス
            folder_id: フォルダID
            issue_date: 文書の発行日（オプション）
        """
        pass

