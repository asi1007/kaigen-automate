"""Playwrightを使用したダウンロードサービス"""
import asyncio
import logging
import re
import tempfile
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import List

from playwright.async_api import Page, async_playwright, Browser, BrowserContext
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.domain.entities.document import Document
from src.domain.repositories.download_repository import IDownloadRepository
from src.domain.value_objects.credentials import Credentials
from src.infrastructure.playwright.pdf_downloader import PDFDownloader

logger = logging.getLogger(__name__)


class PlaywrightDownloadService(IDownloadRepository):
    """Playwrightを使用してドキュメントをダウンロードするサービス"""

    def __init__(
        self,
        credentials: Credentials,
        download_dir: Path | None = None,
        base_url: str = "https://japan-kaigen.net",
        max_download_links: int | None = None,
    ):
        self.credentials = credentials
        if download_dir is None:
            temp_dir = tempfile.mkdtemp(prefix="kaigen_downloads_")
            self.download_dir = Path(temp_dir)
        else:
            self.download_dir = Path(download_dir)
        self.base_url = base_url
        self.max_download_links = max_download_links
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    async def _setup_browser(self) -> None:
        """ブラウザをセットアップする"""
        logger.info("ブラウザを初期化しています...")
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(accept_downloads=True)
        self.page = await self.context.new_page()
        logger.info("ブラウザの初期化が完了しました（ヘッドレスモード）")

    async def _cleanup_browser(self) -> None:
        """ブラウザをクリーンアップする"""
        if self.context:
            await self.context.close()
            logger.debug("ブラウザコンテキストを閉じました")
        if self.browser:
            await self.browser.close()
            logger.debug("ブラウザを閉じました")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _login(self) -> None:
        """ログインする"""
        if not self.page:
            raise RuntimeError("ページが初期化されていません")

        logger.info(f"{self.base_url} へのログインを試みています...")
        await self.page.goto(f"{self.base_url}/member/orderlist.php")
        await self.page.wait_for_load_state("networkidle")

        # ユーザーIDとパスワードを入力
        user_inputs = await self.page.locator('input[type="text"], input[name*="user"], input[name*="id"]').all()
        if user_inputs:
            await user_inputs[0].fill(self.credentials.username)
            logger.debug("ユーザー名を入力しました")

        password_inputs = await self.page.locator('input[type="password"]').all()
        if password_inputs:
            await password_inputs[0].fill(self.credentials.password)
            logger.debug("パスワードを入力しました")

        # ログインボタンをクリック
        submit_selector = 'input[type="submit"], button[type="submit"], button:has-text("ログイン")'
        submit_button = self.page.locator(submit_selector).first
        await submit_button.click()
        logger.info("ログインボタンをクリックしました")

        # ログイン後のページ読み込みを待機
        await self.page.wait_for_load_state("networkidle")
        logger.info("ログインが完了しました")

        # 発注履歴一覧へ遷移（リンククリック）
        logger.info("『発注履歴一覧』へ遷移します…")
        # テキスト一致か href のどちらかでクリック（両方試行）
        link = self.page.locator('a:has-text("発注履歴一覧")').first
        if await link.count() == 0:
            link = self.page.locator('a[href$="orderlist.php"]').first
        await link.click()
        await self.page.wait_for_load_state("networkidle")

    async def _find_download_links(self) -> List[dict]:
        """ダウンロードリンクを探す"""
        if not self.page:
            raise RuntimeError("ページが初期化されていません")

        logger.info("ダウンロードリンクを検索しています...")
        documents = []

        # dllink.php?id= を含むリンクを直接検索
        download_links = await self.page.locator('a[href*="dllink.php?id="]').all()
        logger.debug(f"ダウンロードリンク候補数: {len(download_links)}")

        # 一時デバッグ: タイトルとURL
        try:
            title = await self.page.title()
            logger.info(f"現在タイトル: {title}")
            logger.info(f"現在URL: {self.page.url}")
        except Exception:
            pass

        for link in download_links:
            try:
                href = await link.get_attribute("href")
                text = await link.inner_text()
                
                if not href or "dllink.php?id=" not in href:
                    continue

                # 完全URLを構築
                if href.startswith("http"):
                    full_url = href
                elif href.startswith("/"):
                    full_url = f"{self.base_url}{href}"
                else:
                    # 相対パスの場合、現在のページのパスを基準にする
                    current_path = self.page.url.rsplit('/', 1)[0]
                    full_url = f"{current_path}/{href}" if not current_path.endswith('/') else f"{current_path}{href}"

                # ドキュメントタイプはダウンロード後に判別（現時点では「ダウンロード」として扱う）
                # 実際のファイル名から「請求書」や「輸入許可書」を判定する
                doc_type = "ダウンロード"
                
                documents.append({"url": full_url, "type": doc_type, "text": text, "id": text})
                logger.debug(f"ダウンロードリンクを発見: ID={text}, URL={full_url}")
            
            except Exception as e:
                logger.warning(f"リンクの解析中にエラー: {e}")
                continue

        logger.info(f"合計 {len(documents)} 件のドキュメントリンクを見つけました")
        
        # 最大件数で制限
        if self.max_download_links and self.max_download_links > 0:
            if len(documents) > self.max_download_links:
                logger.info(f"最大件数 {self.max_download_links} 件に制限します（元の件数: {len(documents)}）")
                documents = documents[:self.max_download_links]
        
        return documents

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _download_file(self, url: str, doc_type: str) -> tuple[Path, str]:
        """ファイルをダウンロードする
        
        Returns:
            tuple[Path, str]: (ファイルパス, 判定されたドキュメントタイプ)
        """
        if not self.page:
            raise RuntimeError("ページが初期化されていません")

        logger.info(f"ファイルをダウンロード中: {url}")
        
        async with self.page.expect_download(timeout=60000) as download_info:
            await self.page.goto(url)
        
        download = await download_info.value
        suggested_filename = download.suggested_filename
        file_path = self.download_dir / suggested_filename
        
        await download.save_as(file_path)
        logger.info(f"ダウンロード完了: {file_path.name}")
        
        # ファイル名からドキュメントタイプを判定
        filename_lower = file_path.name.lower()
        if "請求書" in file_path.name or "invoice" in filename_lower:
            detected_type = "請求書"
        elif "輸入許可" in file_path.name or "import" in filename_lower or "permit" in filename_lower:
            detected_type = "輸入許可書"
        else:
            detected_type = doc_type  # 判定できない場合は元のタイプを使用
        
        if detected_type != doc_type:
            logger.debug(f"ドキュメントタイプを判定: {doc_type} -> {detected_type}")
        
        return file_path, detected_type

    async def _download_from_detail(self, page: Page, url: str, base_url: str) -> list[tuple[Path, str]]:
        """数字リンクの詳細ページに遷移し、
        ページ内の『輸入許可書』『請求書』リンクを順にクリックしてダウンロードする。

        Args:
            page: 使用するPlaywrightページオブジェクト
            url: 詳細ページのURL
            base_url: ベースURL

        Returns:
            list[tuple[Path, str]]: (保存パス, 判定タイプ) のリスト
        """

        # まずは直接遷移
        await page.goto(url)
        await page.wait_for_load_state("networkidle")

        # 未ログインページへ飛ばされた場合は、一覧に戻って対象リンクをクリックで開く
        try:
            title = await page.title()
        except Exception:
            title = ""

        if "会員ログイン" in title:
            logger.info("直接アクセスでログインページへ遷移したため、一覧からリンクをクリックします")
            await page.goto(f"{base_url}/member/orderlist.php")
            await page.wait_for_load_state("networkidle")
            # 対象IDを href から抽出
            target_id = None
            if "dllink.php?id=" in url:
                try:
                    target_id = url.split("dllink.php?id=")[-1]
                except Exception:
                    target_id = None
            selector = f'a[href*="dllink.php?id={target_id}"]' if target_id else 'a[href*="dllink.php?id="]'
            link = page.locator(selector).first
            await link.click()
            await page.wait_for_load_state("networkidle")

        results: list[tuple[Path, str]] = []

        # dltemp/ で始まるリンクを探す（請求書と輸入許可書の順）
        dltemp_links = await page.locator('a[href^="dltemp/"]').all()
        logger.debug(f"dltemp/ リンクを {len(dltemp_links)} 件発見")

        # ページ内テキストから順序を確認（請求書が先、輸入許可書が後）
        page_text = await page.content()
        invoice_first = page_text.find("請求書") < page_text.find("輸入許可書") if "請求書" in page_text and "輸入許可書" in page_text else True

        for idx, link in enumerate(dltemp_links[:2]):  # 最大2つまで
            try:
                href = await link.get_attribute("href")
                link_text = await link.inner_text()
                logger.debug(f"dltemp/ リンク {idx+1}: {href} (テキスト: {link_text})")

                # 順序で判定: 最初が請求書、2つ目が輸入許可書（HTMLの順序に従う）
                if invoice_first:
                    assumed_type = "請求書" if idx == 0 else "輸入許可書"
                else:
                    assumed_type = "輸入許可書" if idx == 0 else "請求書"

                # 完全URLを構築
                if href.startswith("http"):
                    pdf_url = href
                elif href.startswith("/"):
                    pdf_url = f"{base_url}{href}"
                else:
                    # 相対パスの場合、現在のページのURLを基準にする
                    current_url = page.url
                    base_path = current_url.rsplit('/', 1)[0] if '/' in current_url else current_url
                    pdf_url = f"{base_path}/{href}" if not base_path.endswith('/') else f"{base_path}{href}"

                logger.debug(f"PDF URL: {pdf_url}")

                # PDFダウンロード処理
                # 現在のページURLを保存（ダウンロード後に戻るため）
                current_detail_url = page.url
                
                # ファイル名を生成（リンクテキストまたはURLから）
                if link_text and link_text != href:
                    filename = f"{link_text}.pdf"
                else:
                    # URLからファイル名を抽出
                    filename = href.split("/")[-1]
                    if not filename.endswith(".pdf"):
                        filename = f"{filename}.pdf"
                
                # 保存先ディレクトリを決定（ファイル名の末尾の数字で判定）
                save_dir = self.download_dir
                match = re.search(r'-(\d+)(?:\.pdf)?$', filename)
                if match:
                    suffix = match.group(1)
                    if suffix == "1":
                        save_dir = self.download_dir / "請求書"
                    elif suffix == "2":
                        save_dir = self.download_dir / "輸入許可書"
                save_dir.mkdir(parents=True, exist_ok=True)
                file_path = save_dir / filename

                if file_path.exists():
                    logger.info(
                        "既に同名のファイルが存在するためダウンロードをスキップします: %s",
                        file_path.name,
                    )
                    continue
                
                # PDFDownloaderを使用してPDFをダウンロード
                pdf_downloader = PDFDownloader(page, self.download_dir, base_url)
                download_success = await pdf_downloader.download(pdf_url, file_path, current_detail_url)
                
                if not download_success:
                    raise Exception(f"PDFダウンロードに失敗しました: {pdf_url}")
                
                # 詳細ページに戻る
                await page.goto(current_detail_url, wait_until="networkidle")
                
                # PDF検証
                if not pdf_downloader._validate_pdf_file(file_path):
                    logger.error(f"ダウンロードしたファイルがPDF形式ではありません: {file_path}")
                    if file_path.exists():
                        file_path.unlink()
                    raise Exception(f"PDFダウンロードに失敗しました: ファイルがPDF形式ではありません")

                # ファイル名から最終タイプ判定
                filename_lower = file_path.name.lower()
                if "請求" in file_path.name or "invoice" in filename_lower:
                    detected_type = "請求書"
                elif "輸入" in file_path.name or "permit" in filename_lower or "import" in filename_lower:
                    detected_type = "輸入許可書"
                else:
                    detected_type = assumed_type

                results.append((file_path, detected_type))
                logger.info(f"{detected_type} をダウンロード完了: {file_path.name}")
            
            except Exception as e:
                logger.warning(f"dltemp/ リンク {idx+1} のダウンロードでエラー: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                continue

        # フォールバック: dltemp/ リンクが見つからない場合、PDFリンクを探す
        if len(results) == 0:
            logger.debug("dltemp/ リンクが見つからないため、PDFリンクを探します")
            pdf_links = await page.locator('a[href$=".pdf"], a[href*=".pdf?"]').all()
            for idx, link in enumerate(pdf_links[:2]):
                try:
                    async with page.expect_download(timeout=60000) as download_info:
                        await link.click()
                    download = await download_info.value
                    suggested_filename = download.suggested_filename
                    file_path = self.download_dir / suggested_filename

                    if file_path.exists():
                        logger.info(
                            "既に同名のファイルが存在するためダウンロードをスキップします: %s",
                            file_path.name,
                        )
                        await download.cancel()
                        continue
                    await download.save_as(file_path)

                    filename_lower = file_path.name.lower()
                    if "invoice" in filename_lower or "請求" in file_path.name:
                        detected_type = "請求書"
                    elif "permit" in filename_lower or "import" in filename_lower or "輸入" in file_path.name:
                        detected_type = "輸入許可書"
                    else:
                        detected_type = "ダウンロード"

                    results.append((file_path, detected_type))
                    logger.info(f"{detected_type} をダウンロード完了: {file_path.name}")
                except Exception as e:
                    logger.warning(f"PDFリンクのダウンロードに失敗: {e}")

        return results

    async def download_documents(self) -> List[Document]:
        """請求書と輸入許可書をダウンロードする（並列処理）"""
        try:
            await self._setup_browser()
            await self._login()
            
            # ダウンロードリンクを探す
            download_links = await self._find_download_links()
            
            if not download_links:
                logger.warning("ダウンロード可能なドキュメントが見つかりませんでした")
                return []

            logger.info(f"{len(download_links)} 件の詳細ページを並列処理します")

            async def process_link(link_info: dict) -> List[Document]:
                """1つの詳細ページを処理する関数"""
                page = None
                try:
                    # 新しいページを作成
                    page = await self.context.new_page()
                    
                    # 数字リンクの詳細ページに入り、そこで2種のリンクを処理
                    detail_results = await self._download_from_detail(
                        page, link_info["url"], self.base_url
                    )

                    if not detail_results:
                        logger.warning(f"詳細ページでダウンロードリンクが見つかりませんでした: {link_info.get('id', 'unknown')}")
                        return []

                    documents = []
                    for file_path, detected_type in detail_results:
                        document = Document(
                            document_type=detected_type,
                            file_path=file_path,
                            download_url=link_info["url"],
                            download_datetime=datetime.now(),
                        )
                        documents.append(document)
                        logger.info(f"{detected_type} の処理が完了しました: {file_path.name} (ID: {link_info.get('id', 'unknown')})")

                    return documents
                
                except Exception as e:
                    logger.error(f"ID {link_info.get('id', 'unknown')} のダウンロード中にエラー: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
                    return []
                finally:
                    if page:
                        await page.close()

            # すべてのリンクを並列処理
            tasks = [process_link(link_info) for link_info in download_links]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 結果をフラット化
            documents: List[Document] = []
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"並列処理中にエラー: {result}")
                elif isinstance(result, list):
                    documents.extend(result)

            logger.info(f"合計 {len(documents)} 件のドキュメントをダウンロードしました")
            return documents
        
        finally:
            await self._cleanup_browser()

