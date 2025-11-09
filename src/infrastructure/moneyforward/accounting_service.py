"""マネーフォワード経理登録サービス"""
import logging
from pathlib import Path
from typing import Optional

from playwright.async_api import Page, async_playwright, Browser, BrowserContext
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.domain.entities.invoice import Invoice
from src.domain.entities.import_permit import ImportPermit
from src.domain.repositories.moneyforward_repository import IMoneyforwardRepository
from src.domain.value_objects.credentials import Credentials

logger = logging.getLogger(__name__)


class MoneyforwardAccountingService(IMoneyforwardRepository):
    """Playwrightを使用してマネーフォワードに経理を登録するサービス"""

    def __init__(
        self,
        credentials: Credentials,
        base_url: str = "https://biz.moneyforward.com",
    ):
        self.credentials = credentials
        self.base_url = base_url
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

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
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        logger.info("ブラウザをクリーンアップしました")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _login(self) -> None:
        """マネーフォワードにログインする"""
        if not self.page:
            raise RuntimeError("ページが初期化されていません")

        logger.info("マネーフォワードにログインしています...")
        await self.page.goto(f"{self.base_url}/sign_in", wait_until="networkidle")

        # メールアドレスを入力
        email_selector = 'input[name="user[email]"], input[type="email"]'
        await self.page.fill(email_selector, self.credentials.username)
        logger.debug("メールアドレスを入力しました")

        # パスワードを入力
        password_selector = 'input[name="user[password]"], input[type="password"]'
        await self.page.fill(password_selector, self.credentials.password)
        logger.debug("パスワードを入力しました")

        # ログインボタンをクリック
        login_button_selector = 'button[type="submit"], input[type="submit"], button:has-text("ログイン")'
        await self.page.click(login_button_selector)
        await self.page.wait_for_load_state("networkidle")
        logger.info("ログインが完了しました")

    async def create_transaction(self, invoice: Invoice) -> str:
        """請求書から経理を作成する

        Args:
            invoice: 請求書エンティティ

        Returns:
            str: 作成された経理のID

        Raises:
            Exception: 経理作成に失敗した場合
        """
        try:
            await self._setup_browser()
            await self._login()

            # 経理登録ページに移動
            await self._navigate_to_accounting_page()

            # 経理を作成
            transaction_id = await self._fill_transaction_form(invoice)

            logger.info(f"経理の作成が完了しました: {transaction_id}")
            return transaction_id

        except Exception as e:
            logger.error(f"経理作成中にエラーが発生しました: {e}")
            raise
        finally:
            await self._cleanup_browser()

    async def _navigate_to_accounting_page(self) -> None:
        """経理登録ページに移動する"""
        if not self.page:
            raise RuntimeError("ページが初期化されていません")

        logger.info("経理登録ページに移動しています...")
        # 経理登録ページのURL（実際のURLは要確認）
        # 一般的には /accounting/new や /transactions/new などのパス
        accounting_url = f"{self.base_url}/accounting/new"
        
        try:
            await self.page.goto(accounting_url, wait_until="networkidle")
        except Exception:
            # URLが見つからない場合は、メニューから経理登録を探す
            logger.info("直接URLでアクセスできませんでした。メニューから経理登録を探します...")
            # 「経理」や「取引登録」などのリンクを探してクリック
            menu_selectors = [
                'a:has-text("経理")',
                'a:has-text("取引登録")',
                'a:has-text("仕訳登録")',
            ]
            for selector in menu_selectors:
                try:
                    await self.page.click(selector, timeout=5000)
                    await self.page.wait_for_load_state("networkidle")
                    logger.info(f"メニューから経理登録ページに移動しました: {selector}")
                    return
                except Exception:
                    continue
            
            raise ValueError("経理登録ページに移動できませんでした")

    async def _fill_transaction_form(self, invoice: Invoice) -> str:
        """経理登録フォームに入力する

        Args:
            invoice: 請求書エンティティ

        Returns:
            str: 作成された経理のID
        """
        if not self.page:
            raise RuntimeError("ページが初期化されていません")

        logger.info("経理登録フォームに入力しています...")

        # 日付を入力
        date_selector = 'input[name*="date"], input[type="date"]'
        date_value = invoice.issue_date.strftime("%Y-%m-%d")
        await self.page.fill(date_selector, date_value)
        logger.debug(f"日付を入力しました: {date_value}")

        # 取引先を入力（取引先が存在しない場合は新規作成が必要な場合もある）
        customer_selector = 'input[name*="customer"], input[name*="partner"], input[placeholder*="取引先"]'
        try:
            await self.page.fill(customer_selector, invoice.customer_name, timeout=5000)
            logger.debug(f"取引先を入力しました: {invoice.customer_name}")
        except Exception:
            logger.warning("取引先入力フィールドが見つかりませんでした。スキップします。")

        # 金額を入力
        amount_selector = 'input[name*="amount"], input[name*="price"], input[type="number"]'
        amount_value = str(int(invoice.total_amount))
        await self.page.fill(amount_selector, amount_value)
        logger.debug(f"金額を入力しました: {amount_value}")

        # 摘要（メモ）を入力
        memo_selector = 'textarea[name*="memo"], textarea[name*="description"], input[name*="memo"]'
        memo_text = f"請求書番号: {invoice.invoice_number}, 追跡番号: {invoice.tracking_number}"
        try:
            await self.page.fill(memo_selector, memo_text, timeout=5000)
            logger.debug(f"摘要を入力しました: {memo_text}")
        except Exception:
            logger.warning("摘要入力フィールドが見つかりませんでした。スキップします。")

        # 保存ボタンをクリック
        submit_selectors = [
            'button[type="submit"]:has-text("保存")',
            'button:has-text("登録")',
            'button:has-text("作成")',
            'input[type="submit"]',
        ]
        
        submitted = False
        for selector in submit_selectors:
            try:
                await self.page.click(selector, timeout=5000)
                await self.page.wait_for_load_state("networkidle")
                logger.info("経理登録フォームを送信しました")
                submitted = True
                break
            except Exception:
                continue
        
        if not submitted:
            raise ValueError("保存ボタンが見つかりませんでした")

        # 作成された経理のIDを取得（URLから取得する場合が多い）
        current_url = self.page.url
        transaction_id = self._extract_transaction_id_from_url(current_url)
        
        if not transaction_id:
            # URLから取得できない場合は、ページ内のIDを探す
            transaction_id = await self._extract_transaction_id_from_page()

        return transaction_id or "unknown"

    def _extract_transaction_id_from_url(self, url: str) -> Optional[str]:
        """URLから経理IDを抽出する"""
        import re
        # /transactions/123 や /accounting/456 のような形式を探す
        pattern = r"/(?:transactions|accounting)/(\d+)"
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return None

    async def _extract_transaction_id_from_page(self) -> Optional[str]:
        """ページから経理IDを抽出する"""
        if not self.page:
            return None

        # 一般的なIDの場所を探す
        id_selectors = [
            '[data-transaction-id]',
            '[data-id]',
            '.transaction-id',
        ]

        for selector in id_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    id_attr = await element.get_attribute("data-transaction-id") or await element.get_attribute("data-id")
                    if id_attr:
                        return id_attr
            except Exception:
                continue

        return None

    async def create_transaction_from_import_permit(self, import_permit: ImportPermit) -> str:
        """輸入許可書から経理を作成する

        Args:
            import_permit: 輸入許可書エンティティ

        Returns:
            str: 作成された経理のID

        Raises:
            Exception: 経理作成に失敗した場合
        """
        try:
            await self._setup_browser()
            await self._login()

            # 経理登録ページに移動
            await self._navigate_to_accounting_page()

            # 経理を作成
            transaction_id = await self._fill_transaction_form_from_import_permit(import_permit)

            logger.info(f"経理の作成が完了しました: {transaction_id}")
            return transaction_id

        except Exception as e:
            logger.error(f"経理作成中にエラーが発生しました: {e}")
            raise
        finally:
            await self._cleanup_browser()

    async def _fill_transaction_form_from_import_permit(self, import_permit: ImportPermit) -> str:
        """輸入許可書から経理登録フォームに入力する

        Args:
            import_permit: 輸入許可書エンティティ

        Returns:
            str: 作成された経理のID
        """
        if not self.page:
            raise RuntimeError("ページが初期化されていません")

        logger.info("経理登録フォームに入力しています（輸入許可書）...")

        # 日付を入力
        date_selector = 'input[name*="date"], input[type="date"]'
        date_value = import_permit.issue_date.strftime("%Y-%m-%d")
        await self.page.fill(date_selector, date_value)
        logger.debug(f"日付を入力しました: {date_value}")

        # 取引先を入力（取引先が存在しない場合は新規作成が必要な場合もある）
        customer_selector = 'input[name*="customer"], input[name*="partner"], input[placeholder*="取引先"]'
        try:
            await self.page.fill(customer_selector, import_permit.importer_name, timeout=5000)
            logger.debug(f"取引先を入力しました: {import_permit.importer_name}")
        except Exception:
            logger.warning("取引先入力フィールドが見つかりませんでした。スキップします。")

        # 金額を入力
        amount_selector = 'input[name*="amount"], input[name*="price"], input[type="number"]'
        amount_value = str(int(import_permit.total_amount))
        await self.page.fill(amount_selector, amount_value)
        logger.debug(f"金額を入力しました: {amount_value}")

        # 摘要（メモ）を入力
        memo_selector = 'textarea[name*="memo"], textarea[name*="description"], input[name*="memo"]'
        memo_text = (
            f"輸入許可書番号: {import_permit.permit_number}, "
            f"追跡番号: {import_permit.tracking_number}, "
            f"関税: ¥{import_permit.customs_duty:,}, "
            f"消費税: ¥{import_permit.consumption_tax:,}, "
            f"地方消費税: ¥{import_permit.local_consumption_tax:,}"
        )
        try:
            await self.page.fill(memo_selector, memo_text, timeout=5000)
            logger.debug(f"摘要を入力しました: {memo_text}")
        except Exception:
            logger.warning("摘要入力フィールドが見つかりませんでした。スキップします。")

        # 保存ボタンをクリック
        submit_selectors = [
            'button[type="submit"]:has-text("保存")',
            'button:has-text("登録")',
            'button:has-text("作成")',
            'input[type="submit"]',
        ]
        
        submitted = False
        for selector in submit_selectors:
            try:
                await self.page.click(selector, timeout=5000)
                await self.page.wait_for_load_state("networkidle")
                logger.info("経理登録フォームを送信しました")
                submitted = True
                break
            except Exception:
                continue
        
        if not submitted:
            raise ValueError("保存ボタンが見つかりませんでした")

        # 作成された経理のIDを取得（URLから取得する場合が多い）
        current_url = self.page.url
        transaction_id = self._extract_transaction_id_from_url(current_url)
        
        if not transaction_id:
            # URLから取得できない場合は、ページ内のIDを探す
            transaction_id = await self._extract_transaction_id_from_page()

        return transaction_id or "unknown"



