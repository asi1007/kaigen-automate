"""MoneyforwardAccountingServiceのテスト"""
import pytest
from pathlib import Path
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

from src.domain.entities.invoice import Invoice
from src.domain.value_objects.invoice_items import InvoiceItem
from src.domain.value_objects.credentials import Credentials
from src.infrastructure.moneyforward.accounting_service import MoneyforwardAccountingService


@pytest.fixture
def test_credentials() -> Credentials:
    """テスト用の認証情報"""
    return Credentials(
        username="test@example.com",
        password="test_password"
    )


@pytest.fixture
def sample_invoice(tmp_path: Path) -> Invoice:
    """サンプル請求書"""
    pdf_path = tmp_path / "sample_invoice.pdf"
    pdf_path.write_bytes(b"dummy pdf content")

    return Invoice(
        invoice_number="YP5507628XX",
        issue_date=date(2025, 10, 23),
        customer_name="テスト会社",
        tracking_number="YP5507628XX",
        total_amount=Decimal("3000"),
        tax_amount=Decimal("0"),
        subtotal=Decimal("3000"),
        payment_due_date=date(2025, 10, 25),
        items=[
            InvoiceItem(
                item_name="通関申告料",
                amount=Decimal("3000"),
                quantity=Decimal("1"),
                unit="件"
            )
        ],
        pdf_path=pdf_path,
    )


@pytest.mark.asyncio
@patch("playwright.async_api.async_playwright")
async def test_create_transaction_success(
    mock_playwright,
    test_credentials: Credentials,
    sample_invoice: Invoice
):
    """経理作成の成功テスト"""
    # Playwrightのモック設定
    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_page = AsyncMock()

    mock_playwright_instance = AsyncMock()
    mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_playwright.return_value.start = AsyncMock(return_value=mock_playwright_instance)

    # ページのモック設定
    mock_page.goto = AsyncMock()
    mock_page.fill = AsyncMock()
    mock_page.click = AsyncMock()
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.url = "https://biz.moneyforward.com/accounting/12345"

    service = MoneyforwardAccountingService(credentials=test_credentials)

    transaction_id = await service.create_transaction(sample_invoice)

    assert transaction_id == "12345"
    mock_page.goto.assert_called()
    mock_page.fill.assert_called()
    mock_page.click.assert_called()


@pytest.mark.asyncio
@patch("playwright.async_api.async_playwright")
async def test_create_transaction_login_error(
    mock_playwright,
    test_credentials: Credentials,
    sample_invoice: Invoice
):
    """ログインエラーのテスト"""
    mock_playwright_instance = AsyncMock()
    mock_playwright_instance.chromium.launch = AsyncMock(side_effect=Exception("Connection error"))
    mock_playwright.return_value.start = AsyncMock(return_value=mock_playwright_instance)

    service = MoneyforwardAccountingService(credentials=test_credentials)

    with pytest.raises(Exception):
        await service.create_transaction(sample_invoice)


@pytest.mark.asyncio
@patch("playwright.async_api.async_playwright")
async def test_create_transaction_form_fill_error(
    mock_playwright,
    test_credentials: Credentials,
    sample_invoice: Invoice
):
    """フォーム入力エラーのテスト"""
    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_page = AsyncMock()

    mock_playwright_instance = AsyncMock()
    mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_playwright.return_value.start = AsyncMock(return_value=mock_playwright_instance)

    mock_page.goto = AsyncMock()
    mock_page.fill = AsyncMock(side_effect=Exception("Element not found"))
    mock_page.wait_for_load_state = AsyncMock()

    service = MoneyforwardAccountingService(credentials=test_credentials)

    with pytest.raises(Exception):
        await service.create_transaction(sample_invoice)







