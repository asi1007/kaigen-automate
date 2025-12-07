import logging
import sys
from datetime import datetime
from pathlib import Path


class LoggingSetup:

    @staticmethod
    def setup(log_level: str, project_root: Path) -> None:
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

