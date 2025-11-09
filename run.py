"""プロジェクトルートからの実行エントリーポイント"""
import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# main.pyを実行
if __name__ == "__main__":
    from src.main import main
    import asyncio
    asyncio.run(main())

