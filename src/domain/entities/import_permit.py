"""輸入許可書エンティティ"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import List
from pathlib import Path

from src.domain.value_objects.import_permit_items import ImportPermitItem


@dataclass(frozen=True)
class ImportPermit:
    """輸入許可書を表すエンティティ"""

    permit_number: str
    issue_date: date
    importer_name: str
    tracking_number: str
    total_amount: Decimal
    customs_duty: Decimal
    consumption_tax: Decimal
    local_consumption_tax: Decimal
    subtotal: Decimal
    items: List[ImportPermitItem]
    pdf_path: Path

    def __post_init__(self):
        """バリデーション"""
        if not self.pdf_path.exists():
            raise ValueError(f"PDFファイルが存在しません: {self.pdf_path}")
        
        if self.total_amount < 0:
            raise ValueError(f"合計金額が負の値です: {self.total_amount}")
        
        if self.customs_duty < 0:
            raise ValueError(f"関税額が負の値です: {self.customs_duty}")
        
        if self.consumption_tax < 0:
            raise ValueError(f"消費税額が負の値です: {self.consumption_tax}")
        
        if self.local_consumption_tax < 0:
            raise ValueError(f"地方消費税額が負の値です: {self.local_consumption_tax}")

