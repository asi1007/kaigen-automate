"""GoogleDriveUploadServiceのテスト"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from src.infrastructure.google_drive.upload_service import GoogleDriveUploadService


@patch('src.infrastructure.google_drive.upload_service.os.path.exists', return_value=True)
@patch('google.oauth2.service_account.Credentials.from_service_account_file')
def test_authenticate_service_account(mock_from_service_account, mock_exists):
    """サービスアカウント認証のテスト"""
    mock_creds = Mock()
    mock_from_service_account.return_value = mock_creds

    with patch('src.infrastructure.google_drive.upload_service.build') as mock_build:
        service = GoogleDriveUploadService(
            service_account_file="service_account.json"
        )

        mock_from_service_account.assert_called_once_with(
            "service_account.json",
            scopes=GoogleDriveUploadService.SCOPES
        )
        mock_build.assert_called_once_with('drive', 'v3', credentials=mock_creds)
        assert service.service is not None


@patch('src.infrastructure.google_drive.upload_service.os.path.exists', return_value=True)
@patch('google.oauth2.service_account.Credentials.from_service_account_file')
def test_authenticate_service_account_with_delegation(mock_from_service_account, mock_exists):
    """サービスアカウント認証（ユーザ委任あり）のテスト"""
    mock_creds = Mock()
    mock_delegated_creds = Mock()
    mock_creds.with_subject.return_value = mock_delegated_creds
    mock_from_service_account.return_value = mock_creds

    with patch('src.infrastructure.google_drive.upload_service.build') as mock_build:
        service = GoogleDriveUploadService(
            service_account_file="service_account.json",
            delegated_subject="user@example.com"
        )

        mock_creds.with_subject.assert_called_once_with("user@example.com")
        mock_build.assert_called_once_with('drive', 'v3', credentials=mock_delegated_creds)
        assert service.service is not None


@pytest.mark.asyncio
async def test_upload_document():
    """ファイルアップロードのテスト"""
    with patch.object(GoogleDriveUploadService, '_authenticate'):
        service = GoogleDriveUploadService(
            service_account_file="service_account.json"
        )
        
        # サービスのモック
        mock_file_service = Mock()
        mock_create = Mock()
        mock_file = Mock()
        mock_file.get = Mock(return_value="file_id_123")
        
        mock_create.execute = Mock(return_value=mock_file)
        mock_file_service.files = Mock(return_value=mock_file_service)
        mock_file_service.create = Mock(return_value=mock_create)
        service.service = mock_file_service
        
        # テストファイルの作成
        test_file = Path("test.pdf")
        test_file.write_bytes(b"test content")
        
        try:
            await service.upload_document(test_file, "folder_id")
            
            # アサーション
            mock_create.execute.assert_called_once()
        finally:
            if test_file.exists():
                test_file.unlink()

