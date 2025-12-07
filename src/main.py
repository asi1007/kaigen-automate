"""メインエントリーポイント"""
import asyncio
import logging
import sys
import traceback
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.config.config_loader import ConfigLoader
from src.infrastructure.logging.logging_setup import LoggingSetup
from src.infrastructure.services.service_factory import ServiceFactory


async def main() -> None:
    """メイン処理"""
    logger: logging.Logger | None = None
    
    try:
        # 設定の読み込み
        config_loader = ConfigLoader(project_root)
        config = config_loader.load_config()
        
        # ロギングの設定
        LoggingSetup.setup(config.log_level, project_root)
        logger = logging.getLogger(__name__)
        
        logger.info("=== 海源物流自動化ツール 開始 ===")
        
        # 認証情報のロード
        credentials, google_credentials, base_url = config_loader.load_credentials()
        logger.info("認証情報のロードが完了しました")
        
        # サービスの初期化
        service_factory = ServiceFactory(logger)
        download_service = service_factory.create_download_service(
            credentials=credentials,
            base_url=base_url,
            config=config,
        )
        
        # アップロードサービスとスプレッドシートサービスの初期化
        upload_service = service_factory.create_upload_service(google_credentials)
        spreadsheet_service = service_factory.create_spreadsheet_service(
            config=config,
            google_credentials=google_credentials,
        )
        
        # ユースケースの作成
        use_case = service_factory.create_use_case(
            download_service=download_service,
            google_credentials=google_credentials,
            upload_service=upload_service,
            spreadsheet_service=spreadsheet_service,
        )
        
        logger.info("サービスの初期化が完了しました")
        
        # ユースケースの実行
        documents = await use_case.execute()
        
        # 結果の表示
        if documents:
            logger.info(f"=== 成功: {len(documents)} 件のドキュメントを処理しました ===")
            for doc in documents:
                logger.info(f"  - {doc.document_type}: {doc.file_path.name}")
        else:
            logger.warning("=== 処理完了: ダウンロード可能なドキュメントが見つかりませんでした ===")
    
    except Exception as e:
        if logger is None:
            logger = logging.getLogger(__name__)
        logger.error(f"=== エラー: {str(e)} ===")
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

