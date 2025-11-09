"""PDF請求書パーサー"""
import logging
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

import pdfplumber

from src.domain.entities.invoice import Invoice
from src.domain.value_objects.invoice_items import InvoiceItem

logger = logging.getLogger(__name__)


class InvoiceParser:
    """PDF請求書を解析してInvoiceエンティティに変換する"""

    def parse(self, pdf_path: Path) -> Invoice:
        """PDF請求書を解析する

        Args:
            pdf_path: PDFファイルのパス

        Returns:
            Invoice: 解析された請求書エンティティ

        Raises:
            ValueError: PDFの解析に失敗した場合
        """
        logger.info(f"請求書PDFを解析中: {pdf_path}")

        if not pdf_path.exists():
            raise ValueError(f"PDFファイルが存在しません: {pdf_path}")

        try:
            with pdfplumber.open(pdf_path) as pdf:
                if len(pdf.pages) == 0:
                    raise ValueError("PDFにページが含まれていません")

                # 最初のページからテキストを抽出
                first_page = pdf.pages[0]
                text = first_page.extract_text()

                if not text:
                    raise ValueError("PDFからテキストを抽出できませんでした")

                # 請求書情報を抽出
                invoice_number = self._extract_invoice_number(text)
                issue_date = self._extract_issue_date(text)
                customer_name = self._extract_customer_name(text)
                tracking_number = self._extract_tracking_number(text)
                payment_due_date = self._extract_payment_due_date(text)

                # テーブルから請求項目を抽出
                items = self._extract_invoice_items(first_page)

                # 金額情報を抽出
                subtotal = self._extract_subtotal(text)
                tax_amount = self._extract_tax_amount(text)
                total_amount = self._extract_total_amount(text)

                invoice = Invoice(
                    invoice_number=invoice_number,
                    issue_date=issue_date,
                    customer_name=customer_name,
                    tracking_number=tracking_number,
                    total_amount=total_amount,
                    tax_amount=tax_amount,
                    subtotal=subtotal,
                    payment_due_date=payment_due_date,
                    items=items,
                    pdf_path=pdf_path,
                )

                logger.info(f"請求書の解析が完了しました: {invoice_number}")
                return invoice

        except Exception as e:
            logger.error(f"請求書の解析中にエラーが発生しました: {e}")
            raise ValueError(f"請求書の解析に失敗しました: {e}") from e

    def _extract_invoice_number(self, text: str) -> str:
        """請求書番号を抽出"""
        # 請求書[YP5507628XX] の形式
        pattern = r"請求書\[([A-Z0-9]+)\]"
        match = re.search(pattern, text)
        if match:
            return match.group(1)
        raise ValueError("請求書番号を抽出できませんでした")

    def _extract_issue_date(self, text: str) -> datetime.date:
        """請求日を抽出"""
        # 2025年10月23日 の形式
        pattern = r"(\d{4})年(\d{1,2})月(\d{1,2})日"
        match = re.search(pattern, text)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            return datetime(year, month, day).date()
        raise ValueError("請求日を抽出できませんでした")

    def _extract_customer_name(self, text: str) -> str:
        """お客様名を抽出"""
        # お客様名： 新白岡輸入販売株式会社 和田篤様
        pattern = r"お客様名[：:]\s*(.+?)(?:\s+請求項目|\s+追跡番号|\n|$)"
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
        raise ValueError("お客様名を抽出できませんでした")

    def _extract_tracking_number(self, text: str) -> str:
        """追跡番号を抽出"""
        # 追跡番号： YP5507628XX -
        pattern = r"追跡番号[：:]\s*([A-Z0-9]+)"
        match = re.search(pattern, text)
        if match:
            return match.group(1)
        raise ValueError("追跡番号を抽出できませんでした")

    def _extract_payment_due_date(self, text: str) -> datetime.date:
        """支払期限を抽出"""
        # お支払い期限： 2025年10月25日
        pattern = r"お支払い期限[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日"
        match = re.search(pattern, text)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            return datetime(year, month, day).date()
        raise ValueError("支払期限を抽出できませんでした")

    def _extract_invoice_items(self, page) -> List[InvoiceItem]:
        """請求項目を抽出"""
        items: List[InvoiceItem] = []

        # テーブルを抽出
        tables = page.extract_tables()
        if not tables:
            raise ValueError("請求項目テーブルが見つかりませんでした")

        # 請求項目テーブルを探す（「請求項目」を含むテーブル）
        for table in tables:
            if not table or len(table) == 0:
                continue

            # ヘッダー行を探す
            header_row = None
            for i, row in enumerate(table):
                if row and any(col and "請求項目" in str(col) for col in row):
                    header_row = i
                    break

            if header_row is None:
                continue

            # データ行を抽出
            for row in table[header_row + 1:]:
                if not row or len(row) < 3:
                    continue

                item_name = str(row[0]).strip() if row[0] else ""
                amount_str = str(row[1]).strip() if row[1] else "¥0"
                quantity_str = str(row[2]).strip() if row[2] else "1"
                unit = str(row[3]).strip() if len(row) > 3 and row[3] else "件"

                # 「：」や余分な文字を削除
                if item_name.endswith("："):
                    item_name = item_name[:-1]

                # 金額から「¥」や「,」を除去してDecimalに変換
                amount = self._parse_amount(amount_str)

                # 数量をDecimalに変換
                try:
                    quantity = Decimal(quantity_str)
                except Exception:
                    quantity = Decimal("1")

                if item_name:  # 空でない項目のみ追加
                    items.append(
                        InvoiceItem(
                            item_name=item_name,
                            amount=amount,
                            quantity=quantity,
                            unit=unit,
                        )
                    )

        if not items:
            raise ValueError("請求項目を抽出できませんでした")

        return items

    def _parse_amount(self, amount_str: str) -> Decimal:
        """金額文字列をDecimalに変換"""
        # 「¥3,000」のような形式を処理
        cleaned = amount_str.replace("¥", "").replace(",", "").strip()
        try:
            return Decimal(cleaned)
        except Exception:
            return Decimal("0")

    def _extract_subtotal(self, text: str) -> Decimal:
        """小計を抽出"""
        pattern = r"小計[：:]\s*¥([\d,]+)"
        match = re.search(pattern, text)
        if match:
            return self._parse_amount(f"¥{match.group(1)}")
        return Decimal("0")

    def _extract_tax_amount(self, text: str) -> Decimal:
        """消費税額を抽出"""
        pattern = r"消費税額10％[：:]\s*¥([\d,]+)"
        match = re.search(pattern, text)
        if match:
            return self._parse_amount(f"¥{match.group(1)}")
        return Decimal("0")

    def _extract_total_amount(self, text: str) -> Decimal:
        """合計金額を抽出"""
        pattern = r"合計金額[：:]\s*¥([\d,]+)"
        match = re.search(pattern, text)
        if match:
            return self._parse_amount(f"¥{match.group(1)}")
        raise ValueError("合計金額を抽出できませんでした")







