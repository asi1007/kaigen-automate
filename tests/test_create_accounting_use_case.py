"""CreateAccountingFromInvoiceUseCaseのテスト"""
import pytest
from pathlib import Path
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch

from src.domain.entities.invoice import Invoice
from src.domain.value_objects.invoice_items import InvoiceItem
from src.domain.repositories.moneyforward_repository import IMoneyforwardRepository
from src.infrastructure.pdf_parser.invoice_parser import InvoiceParser
from src.usecases.create_accounting_from_invoice_use_case import CreateAccountingFromInvoiceUseCase


@pytest.fixture
def mock_invoice_parser() -> InvoiceParser:
    """モックInvoiceParser"""
    return Mock(spec=InvoiceParser)


@pytest.fixture
def mock_moneyforward_repo() -> IMoneyforwardRepository:
    """モックMoneyforwardRepository"""
    return Mock(spec=IMoneyforwardRepository)


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
async def test_execute_successful(
    mock_invoice_parser: InvoiceParser,
    mock_moneyforward_repo: IMoneyforwardRepository,
    sample_invoice: Invoice,
    tmp_path: Path
):
    """正常な実行のテスト"""
    pdf_path = tmp_path / "test_invoice.pdf"
    pdf_path.write_bytes(b"dummy pdf content")

    # モックの設定
    mock_invoice_parser.parse = Mock(return_value=sample_invoice)
    mock_moneyforward_repo.create_transaction = AsyncMock(return_value="transaction_123")

    use_case = CreateAccountingFromInvoiceUseCase(
        invoice_parser=mock_invoice_parser,
        moneyforward_repository=mock_moneyforward_repo,
    )

    transaction_id = await use_case.execute(pdf_path)

    assert transaction_id == "transaction_123"
    mock_invoice_parser.parse.assert_called_once_with(pdf_path)
    mock_moneyforward_repo.create_transaction.assert_called_once_with(sample_invoice)


@pytest.mark.asyncio
async def test_execute_parser_error(
    mock_invoice_parser: InvoiceParser,
    mock_moneyforward_repo: IMoneyforwardRepository,
    tmp_path: Path
):
    """PDF解析エラーのテスト"""
    pdf_path = tmp_path / "test_invoice.pdf"
    pdf_path.write_bytes(b"dummy pdf content")

    mock_invoice_parser.parse = Mock(side_effect=ValueError("PDF解析に失敗しました"))

    use_case = CreateAccountingFromInvoiceUseCase(
        invoice_parser=mock_invoice_parser,
        moneyforward_repository=mock_moneyforward_repo,
    )

    with pytest.raises(ValueError, match="PDF解析に失敗しました"):
        await use_case.execute(pdf_path)

    mock_moneyforward_repo.create_transaction.assert_not_called()


@pytest.mark.asyncio
async def test_execute_accounting_creation_error(
    mock_invoice_parser: InvoiceParser,
    mock_moneyforward_repo: IMoneyforwardRepository,
    sample_invoice: Invoice,
    tmp_path: Path
):
    """経理作成エラーのテスト"""
    pdf_path = tmp_path / "test_invoice.pdf"
    pdf_path.write_bytes(b"dummy pdf content")

    mock_invoice_parser.parse = Mock(return_value=sample_invoice)
    mock_moneyforward_repo.create_transaction = AsyncMock(
        side_effect=Exception("経理作成に失敗しました")
    )

    use_case = CreateAccountingFromInvoiceUseCase(
        invoice_parser=mock_invoice_parser,
        moneyforward_repository=mock_moneyforward_repo,
    )

    with pytest.raises(Exception, match="経理作成に失敗しました"):
        await use_case.execute(pdf_path)

    mock_invoice_parser.parse.assert_called_once_with(pdf_path)
    mock_moneyforward_repo.create_transaction.assert_called_once()







