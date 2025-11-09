"""InvoiceParserのテスト"""
import pytest
from pathlib import Path
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

from src.domain.entities.invoice import Invoice
from src.domain.value_objects.invoice_items import InvoiceItem
from src.infrastructure.pdf_parser.invoice_parser import InvoiceParser


@pytest.fixture
def invoice_parser() -> InvoiceParser:
    """テスト用のInvoiceParser"""
    return InvoiceParser()


@pytest.fixture
def sample_pdf_path(tmp_path: Path) -> Path:
    """サンプルPDFファイルのパス（実際のPDFファイルを使用）"""
    # 実際のテストでは、テスト用のPDFファイルを使用するか、
    # pdfplumberをモックしてテストする
    pdf_path = tmp_path / "sample_invoice.pdf"
    # 実際のPDFファイルが存在する場合はそれを使用
    actual_pdf = Path("/Users/wadaatsushi/Documents/automation/kaigen-automate/YP5507628XX-1.pdf")
    if actual_pdf.exists():
        return actual_pdf
    # 存在しない場合は空ファイルを作成（テストは失敗する）
    pdf_path.write_bytes(b"")
    return pdf_path


@pytest.mark.skip(reason="実際のPDFファイルを使用するため、手動テストが必要")
def test_parse_real_pdf(invoice_parser: InvoiceParser, sample_pdf_path: Path):
    """実際のPDFファイルを解析するテスト"""
    invoice = invoice_parser.parse(sample_pdf_path)

    assert invoice.invoice_number == "YP5507628XX"
    assert invoice.issue_date == date(2025, 10, 23)
    assert invoice.customer_name == "新白岡輸入販売株式会社 和田篤様"
    assert invoice.tracking_number == "YP5507628XX"
    assert invoice.total_amount == Decimal("3000")
    assert invoice.payment_due_date == date(2025, 10, 25)
    assert len(invoice.items) > 0


@patch("pdfplumber.open")
def test_parse_extracts_invoice_number(mock_pdf_open, invoice_parser: InvoiceParser, tmp_path: Path):
    """請求書番号の抽出テスト"""
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"dummy")

    # モックPDFページ
    mock_page = Mock()
    mock_page.extract_text.return_value = "請求書[YP5507628XX] 1/2\n2025年10月23日"
    mock_page.extract_tables.return_value = [
        [
            ["請求項目", "請求金額", "数量", "単位"],
            ["通関申告料", "¥3,000", "1", "件"],
        ]
    ]

    mock_pdf = Mock()
    mock_pdf.__enter__ = Mock(return_value=mock_pdf)
    mock_pdf.__exit__ = Mock(return_value=None)
    mock_pdf.pages = [mock_page]
    mock_pdf_open.return_value = mock_pdf

    invoice = invoice_parser.parse(pdf_path)

    assert invoice.invoice_number == "YP5507628XX"


@patch("pdfplumber.open")
def test_parse_extracts_amounts(mock_pdf_open, invoice_parser: InvoiceParser, tmp_path: Path):
    """金額の抽出テスト"""
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"dummy")

    mock_page = Mock()
    mock_page.extract_text.return_value = (
        "請求書[YP5507628XX] 1/2\n"
        "2025年10月23日\n"
        "お客様名： テスト会社\n"
        "追跡番号： YP5507628XX\n"
        "小計： ¥3,000\n"
        "消費税額10％： ¥0\n"
        "合計金額： ¥3,000\n"
        "お支払い期限： 2025年10月25日"
    )
    mock_page.extract_tables.return_value = [
        [
            ["請求項目", "請求金額", "数量", "単位"],
            ["通関申告料", "¥3,000", "1", "件"],
        ]
    ]

    mock_pdf = Mock()
    mock_pdf.__enter__ = Mock(return_value=mock_pdf)
    mock_pdf.__exit__ = Mock(return_value=None)
    mock_pdf.pages = [mock_page]
    mock_pdf_open.return_value = mock_pdf

    invoice = invoice_parser.parse(pdf_path)

    assert invoice.subtotal == Decimal("3000")
    assert invoice.tax_amount == Decimal("0")
    assert invoice.total_amount == Decimal("3000")


def test_parse_nonexistent_file(invoice_parser: InvoiceParser, tmp_path: Path):
    """存在しないファイルのテスト"""
    pdf_path = tmp_path / "nonexistent.pdf"

    with pytest.raises(ValueError, match="PDFファイルが存在しません"):
        invoice_parser.parse(pdf_path)

