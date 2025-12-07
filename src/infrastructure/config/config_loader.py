"""設定の読み込みを行うサービス"""
import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from src.domain.value_objects.application_config import ApplicationConfig, DocumentType
from src.domain.value_objects.credentials import Credentials, GoogleDriveCredentials


class ConfigLoader:
    """環境変数から設定を読み込むサービス"""

    def __init__(self, project_root: Path) -> None:
        """初期化
        
        Args:
            project_root: プロジェクトルートディレクトリ
        """
        self.project_root = project_root
        self.logger = logging.getLogger(__name__)

    def load_config(self) -> ApplicationConfig:
        """アプリケーション設定を読み込む
        
        Returns:
            ApplicationConfig: アプリケーション設定
            
        Raises:
            ValueError: 設定値が無効な場合
        """
        load_dotenv()
        
        log_level = os.getenv("LOG_LEVEL", "INFO")
        
        # 最大ダウンロードリンク数の取得とバリデーション
        max_download_links = self._parse_max_download_links(
            os.getenv("MAX_DOWNLOAD_LINKS")
        )
        
        # ドキュメントタイプフィルタの取得とバリデーション
        document_type_filter = self._parse_document_type_filter(
            os.getenv("DOCUMENT_TYPE_FILTER")
        )
        
        # Googleスプレッドシート設定の取得
        spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID")
        sheet_id = self._parse_sheet_id(os.getenv("GOOGLE_SHEET_ID"))
        
        try:
            config = ApplicationConfig(
                log_level=log_level,
                max_download_links=max_download_links,
                document_type_filter=document_type_filter,
                spreadsheet_id=spreadsheet_id,
                sheet_id=sheet_id,
            )
            
            if max_download_links:
                self.logger.info(f"最大ダウンロードリンク数: {max_download_links} 件")
            if document_type_filter:
                self.logger.info(f"ドキュメントタイプフィルタ: {document_type_filter}")
                
            return config
        except ValueError as e:
            raise ValueError(f"設定値が無効です: {str(e)}")

    def load_credentials(self) -> tuple[Credentials, GoogleDriveCredentials, str]:
        """認証情報を環境変数から読み込む
        
        Returns:
            tuple[Credentials, GoogleDriveCredentials, str]: 
                海源物流認証情報、Google認証情報、ベースURL
            
        Raises:
            ValueError: 必須の認証情報が設定されていない場合
        """
        load_dotenv()
        
        username = os.getenv("KAIGEN_USERNAME")
        password = os.getenv("KAIGEN_PASSWORD")
        base_url = os.getenv("KAIGEN_BASE_URL", "https://japan-kaigen.net")
        
        if not username or not password:
            raise ValueError("KAIGEN_USERNAME と KAIGEN_PASSWORD を環境変数に設定してください")
        
        credentials = Credentials(
            username=username,
            password=password
        )
        
        # Google DriveフォルダIDの取得
        import_permit_folder_id = os.getenv("GOOGLE_DRIVE_IMPORT_PERMIT_FOLDER_ID")
        invoice_folder_id = os.getenv("GOOGLE_DRIVE_INVOICE_FOLDER_ID")
        
        credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
        token_file = os.getenv("GOOGLE_TOKEN_FILE", "token.json")
        
        # Google認証情報は必須
        if not import_permit_folder_id or not invoice_folder_id:
            raise ValueError(
                "GOOGLE_DRIVE_IMPORT_PERMIT_FOLDER_ID と GOOGLE_DRIVE_INVOICE_FOLDER_ID を環境変数に設定してください"
            )
        
        google_credentials = GoogleDriveCredentials(
            import_permit_folder_id=import_permit_folder_id,
            invoice_folder_id=invoice_folder_id,
            credentials_file=credentials_file,
            token_file=token_file
        )
        
        return credentials, google_credentials, base_url

    def _parse_max_download_links(self, value: Optional[str]) -> Optional[int]:
        """最大ダウンロードリンク数をパースする
        
        Args:
            value: 環境変数の値
            
        Returns:
            Optional[int]: パースされた値、無効な場合はNone
        """
        if not value:
            return None
        
        try:
            parsed = int(value)
            if parsed <= 0:
                self.logger.warning(
                    f"MAX_DOWNLOAD_LINKS の値が無効です: {value}。制限なしで実行します。"
                )
                return None
            return parsed
        except ValueError:
            self.logger.warning(
                f"MAX_DOWNLOAD_LINKS の値が無効です: {value}。制限なしで実行します。"
            )
            return None

    def _parse_document_type_filter(self, value: Optional[str]) -> Optional[str]:
        """ドキュメントタイプフィルタをパースする
        
        Args:
            value: 環境変数の値
            
        Returns:
            Optional[str]: パースされた値、無効な場合はNone
        """
        if not value:
            return None
        
        valid_types = [DocumentType.INVOICE, DocumentType.IMPORT_PERMIT]
        if value not in valid_types:
            self.logger.warning(
                f"DOCUMENT_TYPE_FILTER の値が無効です: {value}。フィルタリングを無効にします。"
            )
            return None
        
        return value

    def _parse_sheet_id(self, value: Optional[str]) -> Optional[int]:
        """シートIDをパースする
        
        Args:
            value: 環境変数の値
            
        Returns:
            Optional[int]: パースされた値、無効な場合はNone
        """
        if not value:
            return None
        
        try:
            return int(value)
        except ValueError:
            self.logger.warning(
                f"GOOGLE_SHEET_ID の値が無効です: {value}。経理データ出力をスキップします。"
            )
            return None

