"""アプリケーション設定を表す値オブジェクト"""
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class DocumentType:
    """ドキュメントタイプの定数"""
    INVOICE = "請求書"
    IMPORT_PERMIT = "輸入許可書"


class ApplicationConfig(BaseModel):
    """アプリケーション設定の値オブジェクト"""

    # ログ設定
    log_level: str = Field(default="INFO", description="ログレベル")
    
    # ダウンロード設定
    max_download_links: Optional[int] = Field(default=None, description="最大ダウンロードリンク数")
    document_type_filter: Optional[str] = Field(default=None, description="ドキュメントタイプフィルタ")
    
    # Googleスプレッドシート設定
    spreadsheet_id: Optional[str] = Field(default=None, description="GoogleスプレッドシートID")
    sheet_id: Optional[int] = Field(default=None, description="シートID")

    @field_validator("document_type_filter")
    @classmethod
    def validate_document_type_filter(cls, v: Optional[str]) -> Optional[str]:
        """ドキュメントタイプフィルタのバリデーション"""
        if v is None:
            return None
        valid_types = [DocumentType.INVOICE, DocumentType.IMPORT_PERMIT]
        if v not in valid_types:
            raise ValueError(f"ドキュメントタイプフィルタは {valid_types} のいずれかである必要があります")
        return v

    @field_validator("max_download_links")
    @classmethod
    def validate_max_download_links(cls, v: Optional[int]) -> Optional[int]:
        """最大ダウンロードリンク数のバリデーション"""
        if v is not None and v <= 0:
            return None
        return v

    class Config:
        frozen = True

