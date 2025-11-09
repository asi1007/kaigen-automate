"""請求書エンティティ"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import List
from pathlib import Path

from src.domain.value_objects.invoice_items import InvoiceItem


@dataclass(frozen=True)
class Invoice:
    """請求書を表すエンティティ"""

    invoice_number: str
    issue_date: date
    customer_name: str
    tracking_number: str
    total_amount: Decimal
    tax_amount: Decimal
    subtotal: Decimal
    payment_due_date: date
    items: List[InvoiceItem]
    pdf_path: Path

    def __post_init__(self):
        """バリデーション"""
        if not self.pdf_path.exists():
            raise ValueError(f"PDFファイルが存在しません: {self.pdf_path}")
        
        if self.total_amount < 0:
            raise ValueError(f"合計金額が負の値です: {self.total_amount}")
        
        if self.issue_date > self.payment_due_date:
            raise ValueError(
                f"請求日が支払期限より後です: {self.issue_date} > {self.payment_due_date}"
            )

