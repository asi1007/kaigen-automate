"""Google Driveへのアップロードサービス"""
import logging
from pathlib import Path
from datetime import date
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.domain.repositories.upload_repository import IUploadRepository
from src.infrastructure.google_drive.oauth_helper import OAuthHelper

logger = logging.getLogger(__name__)


class GoogleDriveUploadService(IUploadRepository):
    """OAuth 2.0でGoogle Driveにドキュメントをアップロードするサービス"""

    def __init__(self, credentials_file: str, token_file: str):
        """Google Driveアップロードサービスを初期化する

        Args:
            credentials_file: OAuth認証情報JSONファイルのパス
            token_file: トークン保存先ファイルのパス
        """
        self.oauth_helper = OAuthHelper(credentials_file, token_file)
        self.service = None
        self._authenticate()

    def _authenticate(self) -> None:
        """Google Drive API をOAuth 2.0で認証する"""
        logger.info("Google Drive API のOAuth認証を開始します...")

        try:
            creds = self.oauth_helper.get_credentials()
            self.service = build('drive', 'v3', credentials=creds)
            logger.info("Google Drive API の認証が完了しました")
        except Exception as e:
            logger.error(f"Google Drive API の認証に失敗しました: {e}")
            raise

    def _build_file_name(self, file_path: Path, issue_date: Optional[date]) -> str:
        """アップロード先で使用するファイル名を生成する"""
        if issue_date:
            date_prefix = issue_date.strftime("%Y%m%d")
            return f"{date_prefix}_{file_path.name}"
        return file_path.name

    def _find_month_folder_id(self, parent_folder_id: str, issue_date: date) -> Optional[str]:
        """該当月のフォルダIDを取得する（存在しない場合はNoneを返す）"""
        if not self.service:
            raise RuntimeError("Google Driveサービスが初期化されていません")

        month = issue_date.strftime("%m")
        query = (
            f"name='{month}' and parents in '{parent_folder_id}' "
            "and mimeType='application/vnd.google-apps.folder' and trashed=false"
        )
        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute()

        folders = results.get('files', [])
        if folders:
            return folders[0]['id']
        return None

    def _get_or_create_folder(self, parent_folder_id: str, folder_name: str) -> str:
        """フォルダを取得または作成する
        
        Args:
            parent_folder_id: 親フォルダのID
            folder_name: 作成するフォルダ名
            
        Returns:
            str: フォルダID
        """
        if not self.service:
            raise RuntimeError("Google Driveサービスが初期化されていません")
        
        try:
            # 既存のフォルダを検索
            query = f"name='{folder_name}' and parents in '{parent_folder_id}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            folders = results.get('files', [])
            if folders:
                folder_id = folders[0]['id']
                logger.debug(f"既存のフォルダを使用: {folder_name} (ID: {folder_id})")
                return folder_id
            
            # フォルダが存在しない場合は作成
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_folder_id]
            }
            
            folder = self.service.files().create(
                body=file_metadata,
                fields='id, name'
            ).execute()
            
            folder_id = folder.get('id')
            logger.info(f"フォルダを作成しました: {folder_name} (ID: {folder_id})")
            return folder_id
            
        except HttpError as error:
            logger.error(f"フォルダの取得/作成中にエラーが発生しました: {error}")
            raise

    def _get_target_folder_id(self, base_folder_id: str, issue_date: date) -> str:
        """発行日に基づいてターゲットフォルダIDを取得する
        
        Args:
            base_folder_id: ベースフォルダID（輸入許可書または請求書フォルダ）
            issue_date: 発行日
            
        Returns:
            str: 最終的なターゲットフォルダID（月フォルダ）
        """
        # 月フォルダを作成/取得（01, 02, ..., 11, 12）
        month = issue_date.strftime("%m")
        month_folder_id = self._get_or_create_folder(base_folder_id, month)

        return month_folder_id

    async def document_exists(
        self, file_path: Path, folder_id: str, issue_date: Optional[date] = None
    ) -> bool:
        """同名のドキュメントが既に存在するかを確認する"""
        if not self.service:
            raise RuntimeError("Google Driveサービスが初期化されていません")

        if not issue_date:
            raise ValueError("issue_dateは必須です（月フォルダの判定に必要）")

        month_folder_id = self._find_month_folder_id(folder_id, issue_date)
        if not month_folder_id:
            return False

        file_name = self._build_file_name(file_path, issue_date)
        query = (
            f"name='{file_name}' and parents in '{month_folder_id}' and trashed=false"
        )
        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id)'
        ).execute()

        exists = bool(results.get('files', []))
        if exists:
            logger.info(f"Google Drive上に既に存在するためスキップします: {file_name}")
        return exists

    async def upload_document(
        self, file_path: Path, folder_id: str, issue_date: Optional[date] = None
    ) -> None:
        """ドキュメントをGoogle Driveにアップロードする
        
        Args:
            file_path: アップロードするファイルのパス
            folder_id: Google DriveのベースフォルダID（輸入許可書または請求書フォルダ）
            issue_date: 文書の発行日（必須、月フォルダの作成に使用）
        """
        if not self.service:
            raise RuntimeError("Google Driveサービスが初期化されていません")

        if not issue_date:
            raise ValueError("issue_dateは必須です（月フォルダの作成に必要）")

        # 月フォルダを作成/取得
        target_folder_id = self._get_target_folder_id(folder_id, issue_date)
        
        # ファイル名に発行日（輸入許可日）を付与（YYYYMMDD_元の名前）
        new_name = self._build_file_name(file_path, issue_date)

        # 念のため重複チェック
        if await self.document_exists(file_path, folder_id, issue_date):
            logger.info(f"既存ファイルのためアップロードをスキップします: {new_name}")
            return

        logger.info(f"Google Drive にアップロード中: {new_name} (フォルダ: {issue_date.strftime('%Y年%m月%d日')})")
        
        try:
            file_metadata = {
                'name': new_name,
                'parents': [target_folder_id]
            }
            
            # MIMEタイプを推測
            mimetype = 'application/pdf'
            if file_path.suffix.lower() in ['.xlsx', '.xls']:
                mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            
            media = MediaFileUpload(str(file_path), mimetype=mimetype)
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name'
            ).execute()
            
            logger.info(
                f"アップロード完了: {new_name} (ID: {file.get('id')})"
            )
        
        except HttpError as error:
            error_details = error.error_details if hasattr(error, 'error_details') else []
            logger.error(f"アップロード中にエラーが発生しました: {error}")
            if error_details:
                for detail in error_details:
                    logger.error(f"エラー詳細: {detail}")
            
            # 認証エラーの場合、より詳細な情報を提供
            if error.resp.status == 401 or 'unauthorized' in str(error).lower():
                logger.error(
                    "\n認証エラーが発生しました。以下の設定を確認してください:\n"
                    "1. OAuth認証情報ファイル（credentials.json）が正しいか確認\n"
                    "2. トークンファイルを削除して再認証を試してください\n"
                    "3. Googleアカウントに適切な権限が付与されているか確認"
                )
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((HttpError, Exception)),
        reraise=True,
    )
    async def upload_with_retry(
        self, file_path: Path, folder_id: str
    ) -> None:
        """リトライ機能付きでドキュメントをアップロードする"""
        await self.upload_document(file_path, folder_id)

