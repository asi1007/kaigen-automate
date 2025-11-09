"""認証情報を表す値オブジェクト"""
from typing import Optional

from pydantic import BaseModel, Field


class Credentials(BaseModel):
    """認証情報の値オブジェクト"""

    username: str = Field(..., description="ユーザー名")
    password: str = Field(..., description="パスワード")

    class Config:
        frozen = True


class GoogleDriveCredentials(BaseModel):
    """Google Drive認証情報の値オブジェクト"""

    import_permit_folder_id: str = Field(..., description="輸入許可書用Google DriveフォルダID")
    invoice_folder_id: str = Field(..., description="請求書用Google DriveフォルダID")
    credentials_file: str = Field(..., description="OAuth認証情報JSONファイルパス")
    token_file: str = Field(default="token.json", description="トークン保存先ファイルパス")

    def get_folder_id(self, document_type: str) -> str:
        """ドキュメントタイプに応じたフォルダIDを取得する
        
        Args:
            document_type: ドキュメントタイプ（"輸入許可書" または "請求書"）
            
        Returns:
            str: フォルダID
            
        Raises:
            ValueError: フォルダIDが設定されていない場合
        """
        if document_type == "輸入許可書":
            return self.import_permit_folder_id
        elif document_type == "請求書":
            return self.invoice_folder_id
        else:
            raise ValueError(f"未知のドキュメントタイプ '{document_type}' 用のフォルダIDが設定されていません")

    class Config:
        frozen = True

