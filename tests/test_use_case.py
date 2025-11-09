"""DownloadAndUploadUseCaseのテスト"""
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock

from src.domain.entities.document import Document
from src.domain.value_objects.credentials import GoogleDriveCredentials
from src.usecases.download_and_upload_use_case import DownloadAndUploadUseCase


@pytest.mark.asyncio
async def test_execute_successful():
    """正常な実行のテスト"""
    # モックリポジトリの作成
    mock_download_repo = AsyncMock()
    mock_upload_repo = AsyncMock()
    
    # テストドキュメントの作成
    test_file = Path("test_invoice.pdf")
    test_file.write_bytes(b"test content")
    
    try:
        test_document = Document(
            document_type="請求書",
            file_path=test_file,
            download_url="http://example.com/invoice.pdf",
            download_datetime=datetime.now()
        )
        
        # モックの戻り値
        mock_download_repo.download_documents = AsyncMock(
            return_value=[test_document]
        )
        mock_upload_repo.upload_document = AsyncMock()
        
        # テスト用のGoogle認証情報
        google_credentials = GoogleDriveCredentials(
            folder_id="test_folder_id",
            credentials_file="credentials.json",
            token_file="token.json"
        )
        
        # ユースケースの実行
        use_case = DownloadAndUploadUseCase(
            download_repository=mock_download_repo,
            upload_repository=mock_upload_repo,
            google_credentials=google_credentials
        )
        
        result = await use_case.execute()
        
        # アサーション
        assert len(result) == 1
        assert result[0] == test_document
        mock_download_repo.download_documents.assert_called_once()
        mock_upload_repo.upload_document.assert_called_once_with(
            test_file, "test_folder_id"
        )
    
    finally:
        if test_file.exists():
            test_file.unlink()


@pytest.mark.asyncio
async def test_execute_no_documents():
    """ドキュメントが見つからない場合のテスト"""
    mock_download_repo = AsyncMock()
    mock_upload_repo = AsyncMock()
    
    mock_download_repo.download_documents = AsyncMock(return_value=[])
    
    google_credentials = GoogleDriveCredentials(
        folder_id="test_folder_id",
        credentials_file="credentials.json",
        token_file="token.json"
    )
    
    use_case = DownloadAndUploadUseCase(
        download_repository=mock_download_repo,
        upload_repository=mock_upload_repo,
        google_credentials=google_credentials
    )
    
    result = await use_case.execute()
    
    assert len(result) == 0
    mock_upload_repo.upload_document.assert_not_called()


@pytest.mark.asyncio
async def test_execute_upload_failure():
    """アップロード失敗時も処理を継続するテスト"""
    mock_download_repo = AsyncMock()
    mock_upload_repo = AsyncMock()
    
    test_file = Path("test_invoice.pdf")
    test_file.write_bytes(b"test content")
    
    try:
        test_document = Document(
            document_type="請求書",
            file_path=test_file,
            download_url="http://example.com/invoice.pdf",
            download_datetime=datetime.now()
        )
        
        mock_download_repo.download_documents = AsyncMock(
            return_value=[test_document]
        )
        mock_upload_repo.upload_document = AsyncMock(
            side_effect=Exception("Upload failed")
        )
        
        google_credentials = GoogleDriveCredentials(
            folder_id="test_folder_id",
            credentials_file="credentials.json",
            token_file="token.json"
        )
        
        use_case = DownloadAndUploadUseCase(
            download_repository=mock_download_repo,
            upload_repository=mock_upload_repo,
            google_credentials=google_credentials
        )
        
        # エラーが発生しても処理は完了する
        result = await use_case.execute()
        
        assert len(result) == 1
    
    finally:
        if test_file.exists():
            test_file.unlink()

