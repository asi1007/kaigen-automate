import logging
import sys
from datetime import datetime
from pathlib import Path

from src.infrastructure.logging.json_formatter import JSONFormatter, get_version


class LoggingSetup:

    @staticmethod
    def setup(log_level: str, project_root: Path) -> None:
        level = getattr(logging, log_level.upper(), logging.INFO)
        
        version = get_version(project_root)
        formatter = JSONFormatter(version=version)
        
        # ログファイルの保存先ディレクトリを作成
        log_dir = project_root / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # ログファイル名にタイムスタンプを含める
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"app_{timestamp}.log"
        
        # ハンドラーの設定
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        
        handlers = [stream_handler, file_handler]
        
        logging.basicConfig(
            level=level,
            handlers=handlers,
            force=True
        )
        
        # ログファイルのパスを出力
        logger = logging.getLogger(__name__)
        logger.info("ログファイルを初期化しました", extra={"context": {"log_file": str(log_file)}})

