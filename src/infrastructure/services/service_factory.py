"""サービスの初期化を行うファクトリ"""
import logging
from typing import Optional

from src.domain.value_objects.application_config import ApplicationConfig
from src.domain.value_objects.credentials import Credentials, GoogleDriveCredentials
from src.infrastructure.google_drive.upload_service import GoogleDriveUploadService
from src.infrastructure.google_sheets.spreadsheet_service import GoogleSheetsService
from src.infrastructure.playwright.download_service import PlaywrightDownloadService
from src.usecases.download_and_upload_use_case import DownloadAndUploadUseCase


class ServiceFactory:
    """サービスの初期化を行うファクトリ"""

    def __init__(self, logger: logging.Logger) -> None:
        """初期化
        
        Args:
            logger: ロガー
        """
        self.logger = logger

    def create_download_service(
        self,
        credentials: Credentials,
        base_url: str,
        config: ApplicationConfig,
    ) -> PlaywrightDownloadService:
        """ダウンロードサービスを作成
        
        Args:
            credentials: 認証情報
            base_url: ベースURL
            config: アプリケーション設定
            
        Returns:
            PlaywrightDownloadService: ダウンロードサービス
        """
        self.logger.info("サービスの初期化を開始します...")
        
        download_service = PlaywrightDownloadService(
            credentials=credentials,
            base_url=base_url,
            max_download_links=config.max_download_links,
            document_type_filter=config.document_type_filter
        )
        
        self.logger.info(f"ダウンロードディレクトリ: {download_service.download_dir}")
        return download_service

    def create_upload_service(
        self,
        google_credentials: GoogleDriveCredentials,
    ) -> GoogleDriveUploadService:
        """アップロードサービスを作成
        
        Args:
            google_credentials: Google認証情報
            
        Returns:
            GoogleDriveUploadService: アップロードサービス
        """
        return GoogleDriveUploadService(
            credentials_file=google_credentials.credentials_file,
            token_file=google_credentials.token_file
        )

    def create_spreadsheet_service(
        self,
        config: ApplicationConfig,
        google_credentials: GoogleDriveCredentials,
    ) -> Optional[GoogleSheetsService]:
        """スプレッドシートサービスを作成
        
        Args:
            config: アプリケーション設定
            google_credentials: Google認証情報
            
        Returns:
            Optional[GoogleSheetsService]: スプレッドシートサービス、設定がない場合はNone
        """
        if not config.spreadsheet_id or not config.sheet_id:
            self.logger.info("スプレッドシート設定が見つかりません。経理データ出力をスキップします。")
            return None
        
        spreadsheet_service = GoogleSheetsService(
            spreadsheet_id=config.spreadsheet_id,
            sheet_id=config.sheet_id,
            credentials_file=google_credentials.credentials_file,
            token_file=google_credentials.token_file
        )
        
        self.logger.info("スプレッドシートサービスを初期化しました（輸入許可書の経理データ出力用）")
        return spreadsheet_service

    def create_use_case(
        self,
        download_service: PlaywrightDownloadService,
        google_credentials: GoogleDriveCredentials,
        upload_service: GoogleDriveUploadService,
        spreadsheet_service: Optional[GoogleSheetsService],
    ) -> DownloadAndUploadUseCase:
        """ユースケースを作成
        
        Args:
            download_service: ダウンロードサービス
            google_credentials: Google認証情報
            upload_service: アップロードサービス
            spreadsheet_service: スプレッドシートサービス
            
        Returns:
            DownloadAndUploadUseCase: ユースケース
        """
        self.logger.info("実行モード: ダウンロード、経理データ作成、アップロード")
        
        return DownloadAndUploadUseCase(
            download_repository=download_service,
            upload_repository=upload_service,
            google_credentials=google_credentials,
            spreadsheet_repository=spreadsheet_service
        )

