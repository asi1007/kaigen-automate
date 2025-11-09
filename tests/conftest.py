"""pytest共通設定"""
import pytest
from pathlib import Path

from src.domain.value_objects.credentials import Credentials, GoogleDriveCredentials


@pytest.fixture
def test_credentials() -> Credentials:
    """テスト用の認証情報"""
    return Credentials(
        username="test_user",
        password="test_password"
    )


@pytest.fixture
def test_google_credentials() -> GoogleDriveCredentials:
    """テスト用のGoogle認証情報"""
    return GoogleDriveCredentials(
        folder_id="test_folder_id",
        import_permit_folder_id="test_import_permit_folder_id",
        invoice_folder_id="test_invoice_folder_id",
        credentials_file="credentials.json",
        token_file="token.json"
    )


@pytest.fixture
def test_download_dir(tmp_path: Path) -> Path:
    """テスト用のダウンロードディレクトリ"""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(exist_ok=True)
    return download_dir

