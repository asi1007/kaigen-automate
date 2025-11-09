"""PDFダウンロード処理を担当するクラス"""
import logging
import re
from pathlib import Path

from playwright.async_api import Page

logger = logging.getLogger(__name__)


class PDFDownloader:
    """PDFダウンロード処理を担当するクラス"""
    
    def __init__(self, page: Page, download_dir: Path, base_url: str):
        self.page = page
        self.download_dir = download_dir
        self.base_url = base_url
    
    async def download(self, pdf_url: str, file_path: Path, return_url: str) -> bool:
        """PDFをダウンロードする
        
        Args:
            pdf_url: PDFのURL
            file_path: 保存先ファイルパス
            return_url: ダウンロード後に戻るURL
            
        Returns:
            bool: ダウンロード成功した場合True
        """
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                # レスポンスから直接取得
                success = await self._download_via_direct_response(pdf_url, file_path)
                if success:
                    # PDF検証
                    if self._validate_pdf_file(file_path):
                        return True
                    else:
                        logger.warning(f"ダウンロードしたファイルがPDF形式ではありません（試行 {attempt + 1}/{max_retries + 1}）")
                        if file_path.exists():
                            file_path.unlink()  # 不正なファイルを削除
                        if attempt < max_retries:
                            continue
                elif attempt < max_retries:
                    logger.debug(f"再試行します（試行 {attempt + 1}/{max_retries + 1}）")
                    await self.page.wait_for_timeout(2000)  # 再試行前に少し待つ
                    continue
            except Exception as e:
                logger.error(f"PDFの取得に失敗しました（試行 {attempt + 1}/{max_retries + 1}）: {e}")
                if attempt < max_retries:
                    # 詳細ページに戻って再試行
                    try:
                        await self.page.goto(return_url, wait_until="networkidle")
                        await self.page.wait_for_timeout(2000)
                    except Exception:
                        pass
                    continue
                else:
                    # 詳細ページに戻る
                    try:
                        await self.page.goto(return_url, wait_until="networkidle")
                    except Exception:
                        pass
                    raise
        
        logger.error(f"PDFのダウンロードに失敗しました（最大試行回数に達しました）")
        return False
    
    def _validate_pdf_file(self, file_path: Path) -> bool:
        """ファイルがPDF形式かどうかを検証する
        
        Args:
            file_path: 検証するファイルのパス
            
        Returns:
            bool: PDF形式の場合True、そうでない場合False
        """
        try:
            if not file_path.exists():
                return False
            
            # ファイルサイズが小さすぎる場合はHTMLの可能性が高い
            if file_path.stat().st_size < 1000:  # 1KB未満は疑わしい
                logger.debug(f"ファイルサイズが小さすぎます: {file_path.stat().st_size} bytes")
                # マジックナンバーで確認
                with open(file_path, "rb") as f:
                    header = f.read(10)
                    if header.startswith(b'%PDF'):
                        return True
                    # HTMLの可能性をチェック
                    if header.startswith(b'<!doctype') or header.startswith(b'<html') or header.startswith(b'<HTML'):
                        return False
                return False
            
            # マジックナンバーで確認
            with open(file_path, "rb") as f:
                header = f.read(10)
                if header.startswith(b'%PDF'):
                    return True
                # HTMLの可能性をチェック
                if header.startswith(b'<!doctype') or header.startswith(b'<html') or header.startswith(b'<HTML'):
                    return False
            
            return False
        except Exception as e:
            logger.error(f"PDF検証中にエラー: {e}")
            return False
    
    def _get_save_directory(self, filename: str) -> Path:
        """ファイル名から保存先ディレクトリを決定する
        
        Args:
            filename: ファイル名
            
        Returns:
            Path: 保存先ディレクトリパス
        """
        # ファイル名の末尾の数字を抽出（例: "DQ2107018-1" -> 1, "DQ2107018-2" -> 2）
        match = re.search(r'-(\d+)(?:\.pdf)?$', filename)
        if match:
            suffix = match.group(1)
            if suffix == "1":
                folder = self.download_dir / "請求書"
            elif suffix == "2":
                folder = self.download_dir / "輸入許可書"
            else:
                # 数字が1でも2でもない場合は元のディレクトリ
                folder = self.download_dir
        else:
            # 数字が見つからない場合は元のディレクトリ
            folder = self.download_dir
        
        # フォルダが存在しない場合は作成
        folder.mkdir(parents=True, exist_ok=True)
        return folder
    
    async def _download_via_direct_response(self, pdf_url: str, file_path: Path) -> bool:
        """HTTPリクエストで直接PDFを取得する"""
        # 既存のファイルを削除（HTMLファイルの可能性があるため）
        if file_path.exists():
            file_path.unlink()
        
        # ファイルパスの親ディレクトリが存在することを確認
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # HTTPリクエストで直接PDFを取得
        logger.debug(f"PDF URLにアクセス: {pdf_url}")
        try:
            # page.request.get()を使用してPDFを直接ダウンロード
            response = await self.page.request.get(pdf_url)
            
            if response.status != 200:
                logger.error(f"PDFの取得に失敗しました。ステータスコード: {response.status}")
                return False
            
            # レスポンスボディを取得
            pdf_data = await response.body()
            
            if pdf_data and len(pdf_data) > 100:  # 小さすぎる場合は無効
                file_path.write_bytes(pdf_data)
                # PDF検証
                if self._validate_pdf_file(file_path):
                    logger.debug(f"PDFを保存: {file_path.name}")
                    return True
                else:
                    logger.warning("ダウンロードしたファイルがPDF形式ではありません")
                    if file_path.exists():
                        file_path.unlink()
                    return False
            else:
                logger.error("PDFデータを取得できませんでした（データサイズが小さすぎます）")
                return False
        except Exception as e:
            logger.error(f"PDFの取得に失敗: {e}")
            # フォールバック: ブラウザの印刷機能を試す
            logger.info("HTTPリクエストに失敗したため、ブラウザの印刷機能を試します")
            return await self._download_via_print(pdf_url, file_path)
    
    async def _download_via_print(self, pdf_url: str, file_path: Path) -> bool:
        """ブラウザのダウンロード機能または印刷機能を使用してPDFを取得する（フォールバック用）"""
        try:
            # PDF URLにアクセス（ダウンロードイベントを待つ）
            logger.debug(f"PDF URLにアクセス（ダウンロード機能）: {pdf_url}")
            
            # ダウンロードイベントを待つ（gotoの前に設定する必要がある）
            async with self.page.expect_download(timeout=30000) as download_info:
                try:
                    # wait_untilを"domcontentloaded"に変更して、ダウンロード開始を検出しやすくする
                    await self.page.goto(pdf_url, wait_until="domcontentloaded", timeout=10000)
                except Exception as e:
                    # "Download is starting" エラーの場合は、ダウンロードイベントを待つ
                    if "Download is starting" in str(e):
                        logger.debug("ダウンロードが開始されました")
                    else:
                        # 他のエラーの場合は、少し待ってからダウンロードイベントを確認
                        logger.debug(f"gotoでエラーが発生しましたが、ダウンロードイベントを待ちます: {e}")
                        await self.page.wait_for_timeout(2000)
            
            # ダウンロードイベントが発生した場合
            download = await download_info.value
            await download.save_as(file_path)
            
            # PDF検証
            if self._validate_pdf_file(file_path):
                logger.debug(f"ダウンロードでPDFを保存: {file_path.name}")
                return True
            else:
                logger.warning("ダウンロードしたファイルがPDF形式ではありません")
                if file_path.exists():
                    file_path.unlink()
                return False
        except Exception as e:
            logger.error(f"ダウンロード機能でのPDF取得に失敗: {e}")
            # 最後の手段として、page.pdf()を試す
            try:
                logger.info("ダウンロード機能に失敗したため、印刷機能を試します")
                # ダウンロードが開始されないように、wait_untilを変更
                await self.page.goto(pdf_url, wait_until="domcontentloaded", timeout=10000)
                await self.page.wait_for_timeout(2000)
                pdf_data = await self.page.pdf(format="A4", print_background=True)
                if pdf_data and len(pdf_data) > 100:
                    file_path.write_bytes(pdf_data)
                    if self._validate_pdf_file(file_path):
                        logger.debug(f"印刷機能でPDFを保存: {file_path.name}")
                        return True
            except Exception as print_error:
                logger.error(f"印刷機能でのPDF取得に失敗: {print_error}")
            return False
    

