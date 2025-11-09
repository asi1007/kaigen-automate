"""PlaywrightDownloadServiceのテスト"""
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

from src.domain.value_objects.credentials import Credentials
from src.infrastructure.playwright.download_service import PlaywrightDownloadService
from tests.conftest import test_credentials, test_download_dir


@pytest.mark.asyncio
async def test_download_service_initialization(test_credentials, test_download_dir):
    """ダウンロードサービスの初期化テスト"""
    service = PlaywrightDownloadService(
        credentials=test_credentials,
        download_dir=test_download_dir
    )
    
    assert service.credentials.username == "test_user"
    assert service.credentials.password == "test_password"
    assert service.download_dir == test_download_dir


@pytest.mark.asyncio
async def test_login_with_mock(test_credentials, test_download_dir):
    """ログイン機能のテスト（モック使用）"""
    with patch('src.infrastructure.playwright.download_service.async_playwright') as mock_playwright:
        # モックのセットアップ
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        
        mock_playwright_instance = mock_playwright.return_value.__aenter__.return_value
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        
        mock_page.goto = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.locator = Mock()
        
        # ロケーターのモック設定
        user_input = Mock()
        password_input = Mock()
        user_input.fill = AsyncMock()
        password_input.fill = AsyncMock()
        
        mock_page.locator.return_value.all = AsyncMock(return_value=[
            user_input, password_input
        ])
        
        submit_button = Mock()
        submit_button.click = AsyncMock()
        submit_button.first = submit_button
        
        mock_page.locator.return_value.first = submit_button
        
        service = PlaywrightDownloadService(
            credentials=test_credentials,
            download_dir=test_download_dir
        )
        
        await service._setup_browser()
        await service._login()
        
        # アサーション
        mock_page.goto.assert_called()
        mock_page.wait_for_load_state.assert_called()


@pytest.mark.asyncio
async def test_find_download_links(test_credentials, test_download_dir):
    """ダウンロードリンク検索のテスト"""
    service = PlaywrightDownloadService(
        credentials=test_credentials,
        download_dir=test_download_dir
    )
    
    # ページモック
    mock_page = AsyncMock()
    service.page = mock_page
    
    # リンクのモック
    link1 = Mock()
    link1.get_attribute = AsyncMock(return_value="/download/invoice.pdf")
    link1.inner_text = AsyncMock(return_value="請求書")
    
    link2 = Mock()
    link2.get_attribute = AsyncMock(return_value="/download/permit.pdf")
    link2.inner_text = AsyncMock(return_value="輸入許可書")
    
    mock_page.locator = Mock()
    mock_page.locator.return_value.all = AsyncMock(return_value=[link1, link2])
    
    links = await service._find_download_links()
    
    assert len(links) == 2
    assert any(link["type"] == "請求書" for link in links)
    assert any(link["type"] == "輸入許可書" for link in links)

