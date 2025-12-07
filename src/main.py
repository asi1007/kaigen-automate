"""メインエントリーポイント"""
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

from src.domain.value_objects.credentials import Credentials, GoogleDriveCredentials
from src.infrastructure.playwright.download_service import PlaywrightDownloadService
from src.infrastructure.google_drive.upload_service import GoogleDriveUploadService
from src.infrastructure.google_sheets.spreadsheet_service import GoogleSheetsService
from src.usecases.download_and_upload_use_case import DownloadAndUploadUseCase
from src.usecases.download_only_use_case import DownloadOnlyUseCase


def setup_logging(log_level: str = "INFO") -> None:
    """ロギングの設定"""
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # ログファイルの保存先ディレクトリを作成
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)
    
    # ログファイル名にタイムスタンプを含める
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"app_{timestamp}.log"
    
    # ハンドラーの設定
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8"),
    ]
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    
    # ログファイルのパスを出力
    logger = logging.getLogger(__name__)
    logger.info(f"ログファイル: {log_file}")


def load_credentials() -> tuple[Credentials, "GoogleDriveCredentials | None", str]:
    """認証情報を環境変数からロードする"""
    load_dotenv()
    
    import os
    
    username = os.getenv("KAIGEN_USERNAME")
    password = os.getenv("KAIGEN_PASSWORD")
    base_url = os.getenv("KAIGEN_BASE_URL", "https://japan-kaigen.net")
    
    # Google DriveフォルダIDの取得
    import_permit_folder_id = os.getenv("GOOGLE_DRIVE_IMPORT_PERMIT_FOLDER_ID")
    invoice_folder_id = os.getenv("GOOGLE_DRIVE_INVOICE_FOLDER_ID")
    
    credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    token_file = os.getenv("GOOGLE_TOKEN_FILE", "token.json")
    
    if not username or not password:
        raise ValueError("KAIGEN_USERNAME と KAIGEN_PASSWORD を環境変数に設定してください")
    
    credentials = Credentials(
        username=username,
        password=password
    )
    
    # ダウンロードのみの場合はGoogle認証情報は不要
    google_credentials = None
    # フォルダIDが両方設定されていればGoogle認証情報を作成
    if import_permit_folder_id and invoice_folder_id:
        google_credentials = GoogleDriveCredentials(
            import_permit_folder_id=import_permit_folder_id,
            invoice_folder_id=invoice_folder_id,
            credentials_file=credentials_file,
            token_file=token_file
        )
    
    return credentials, google_credentials, base_url


async def main():
    """メイン処理"""
    try:
        # 環境変数をロード
        import os
        log_level = os.getenv("LOG_LEVEL", "INFO")
        setup_logging(log_level)
        logger = logging.getLogger(__name__)
        
        logger.info("=== 海源物流自動化ツール 開始 ===")
        
        # 認証情報のロード
        credentials, google_credentials, base_url = load_credentials()
        logger.info("認証情報のロードが完了しました")
        
        # 実行モードの確認
        import os
        execution_mode = os.getenv("EXECUTION_MODE", "download_and_upload").lower()
        
        # 最大ダウンロードリンク数の取得
        max_download_links_str = os.getenv("MAX_DOWNLOAD_LINKS")
        max_download_links = None
        if max_download_links_str:
            try:
                max_download_links = int(max_download_links_str)
                if max_download_links <= 0:
                    max_download_links = None
                else:
                    logger.info(f"最大ダウンロードリンク数: {max_download_links} 件")
            except ValueError:
                logger.warning(f"MAX_DOWNLOAD_LINKS の値が無効です: {max_download_links_str}。制限なしで実行します。")
        
        # ドキュメントタイプフィルタの取得
        document_type_filter = os.getenv("DOCUMENT_TYPE_FILTER")  # "請求書" または "輸入許可書" または None
        if document_type_filter:
            if document_type_filter not in ["請求書", "輸入許可書"]:
                logger.warning(f"DOCUMENT_TYPE_FILTER の値が無効です: {document_type_filter}。フィルタリングを無効にします。")
                document_type_filter = None
            else:
                logger.info(f"ドキュメントタイプフィルタ: {document_type_filter}")
        
        # ダウンロードサービスの初期化
        logger.info("サービスの初期化を開始します...")
        download_service = PlaywrightDownloadService(
            credentials=credentials,
            base_url=base_url,
            max_download_links=max_download_links,
            document_type_filter=document_type_filter
        )
        logger.info(f"ダウンロードディレクトリ: {download_service.download_dir}")
        
        # 実行モードに応じて処理を分岐
        if execution_mode == "download_only":
            logger.info("実行モード: ダウンロードのみ")
            use_case = DownloadOnlyUseCase(
                download_repository=download_service,
            )
        else:
            logger.info("実行モード: ダウンロード、経理データ作成、アップロード")
            
            if not google_credentials:
                raise ValueError(
                    "ダウンロードとアップロードモードでは "
                    "GOOGLE_DRIVE_IMPORT_PERMIT_FOLDER_ID と GOOGLE_DRIVE_INVOICE_FOLDER_ID が必要です"
                )
            
            upload_service = GoogleDriveUploadService(
                credentials_file=google_credentials.credentials_file,
                token_file=google_credentials.token_file
            )
            
            # スプレッドシートサービス（輸入許可書の経理データ出力用）
            spreadsheet_service = None
            spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID")
            sheet_id_str = os.getenv("GOOGLE_SHEET_ID")
            
            if spreadsheet_id and sheet_id_str:
                try:
                    sheet_id = int(sheet_id_str)
                    spreadsheet_service = GoogleSheetsService(
                        spreadsheet_id=spreadsheet_id,
                        sheet_id=sheet_id,
                        credentials_file=google_credentials.credentials_file,
                        token_file=google_credentials.token_file
                    )
                    logger.info("スプレッドシートサービスを初期化しました（輸入許可書の経理データ出力用）")
                except ValueError:
                    logger.warning(f"GOOGLE_SHEET_ID の値が無効です: {sheet_id_str}。経理データ出力をスキップします。")
            else:
                logger.info("スプレッドシート設定が見つかりません。経理データ出力をスキップします。")
            
            use_case = DownloadAndUploadUseCase(
                download_repository=download_service,
                upload_repository=upload_service,
                google_credentials=google_credentials,
                spreadsheet_repository=spreadsheet_service
            )
        
        logger.info("サービスの初期化が完了しました")
        
        documents = await use_case.execute()
        
        if documents:
            logger.info(f"=== 成功: {len(documents)} 件のドキュメントを処理しました ===")
            for doc in documents:
                logger.info(f"  - {doc.document_type}: {doc.file_path.name}")
        else:
            logger.warning("=== 処理完了: ダウンロード可能なドキュメントが見つかりませんでした ===")
    
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"=== エラー: {str(e)} ===")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

