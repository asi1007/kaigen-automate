"""輸入許可書項目の値オブジェクト"""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ImportPermitItem:
    """輸入許可書の各項目を表す値オブジェクト"""

    item_name: str
    amount: Decimal
    quantity: Decimal
    unit: str

    def __post_init__(self):
        """バリデーション"""
        if not self.item_name:
            raise ValueError("項目名が空です")
        
        if self.amount < 0:
            raise ValueError(f"金額が負の値です: {self.amount}")
        
        if self.quantity < 0:
            raise ValueError(f"数量が負の値です: {self.quantity}")

