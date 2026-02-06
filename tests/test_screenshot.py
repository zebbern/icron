"""Unit tests for the screenshot tool."""

import re
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from icron.agent.tools.screenshot import (
    ScreenshotTool,
    _generate_filename,
    _validate_url,
)


# =============================================================================
# URL Validation Tests
# =============================================================================

class TestValidateUrl:
    """Tests for _validate_url function."""

    @pytest.mark.parametrize("url", [
        "http://example.com",
        "https://example.com",
        "https://www.google.com/search?q=test",
        "http://localhost:8080",
        "https://sub.domain.example.org/path/to/page",
        "https://example.com:443/path?query=value#fragment",
    ])
    def test_valid_http_https_urls(self, url: str) -> None:
        """Valid HTTP/HTTPS URLs should pass validation."""
        is_valid, error = _validate_url(url)
        assert is_valid is True
        assert error == ""

    @pytest.mark.parametrize("url,expected_scheme", [
        ("ftp://files.example.com", "ftp"),
        ("file:///home/user/file.html", "file"),
        ("mailto:test@example.com", "mailto"),
        ("javascript:alert(1)", "javascript"),
        ("data:text/html,<h1>Test</h1>", "data"),
        ("ssh://git@github.com", "ssh"),
    ])
    def test_invalid_schemes_rejected(self, url: str, expected_scheme: str) -> None:
        """Non-HTTP/HTTPS schemes should be rejected."""
        is_valid, error = _validate_url(url)
        assert is_valid is False
        assert expected_scheme in error or "none" in error

    def test_missing_scheme_rejected(self) -> None:
        """URLs without a scheme should be rejected."""
        is_valid, error = _validate_url("example.com")
        assert is_valid is False
        assert "none" in error.lower() or "http" in error.lower()

    @pytest.mark.parametrize("url", [
        "http://",
        "https://",
        "http:///path",
        "https:///path/to/resource",
    ])
    def test_missing_domain_rejected(self, url: str) -> None:
        """URLs without a domain should be rejected."""
        is_valid, error = _validate_url(url)
        assert is_valid is False
        assert "domain" in error.lower()

    def test_empty_url_rejected(self) -> None:
        """Empty URL should be rejected."""
        is_valid, error = _validate_url("")
        assert is_valid is False


# =============================================================================
# Filename Generation Tests
# =============================================================================

class TestGenerateFilename:
    """Tests for _generate_filename function."""

    def test_filename_format(self) -> None:
        """Filename should match expected format: screenshot_{timestamp}_{hash}.png."""
        filename = _generate_filename("https://example.com")
        pattern = r"^screenshot_\d{8}_\d{6}_[a-f0-9]{8}\.png$"
        assert re.match(pattern, filename), f"Filename '{filename}' doesn't match pattern"

    def test_filename_ends_with_png(self) -> None:
        """Filename should have .png extension."""
        filename = _generate_filename("https://example.com")
        assert filename.endswith(".png")

    def test_unique_filenames_for_different_urls(self) -> None:
        """Different URLs should produce different hash portions."""
        filename1 = _generate_filename("https://example.com/page1")
        filename2 = _generate_filename("https://example.com/page2")
        
        # Extract hash portion (last 8 chars before .png)
        hash1 = filename1.split("_")[-1].replace(".png", "")
        hash2 = filename2.split("_")[-1].replace(".png", "")
        
        assert hash1 != hash2

    def test_same_url_produces_same_hash(self) -> None:
        """Same URL should produce same hash portion (timestamps may differ)."""
        url = "https://example.com/consistent"
        filename1 = _generate_filename(url)
        filename2 = _generate_filename(url)
        
        hash1 = filename1.split("_")[-1].replace(".png", "")
        hash2 = filename2.split("_")[-1].replace(".png", "")
        
        assert hash1 == hash2


# =============================================================================
# Tool Initialization Tests
# =============================================================================

class TestScreenshotToolInit:
    """Tests for ScreenshotTool initialization."""

    def test_default_workspace(self) -> None:
        """Default workspace should be current working directory."""
        tool = ScreenshotTool()
        assert tool.workspace_path == Path.cwd()

    def test_custom_workspace_path_string(self) -> None:
        """Custom workspace path as string should be converted to Path."""
        custom_path = "/custom/workspace"
        tool = ScreenshotTool(workspace_path=custom_path)
        assert tool.workspace_path == Path(custom_path)

    def test_custom_workspace_path_preserves_value(self) -> None:
        """Custom workspace path should be preserved."""
        custom_path = "C:\\Users\\test\\workspace"
        tool = ScreenshotTool(workspace_path=custom_path)
        assert str(tool.workspace_path) == custom_path

    def test_default_timeout(self) -> None:
        """Default timeout should be 30000ms."""
        tool = ScreenshotTool()
        assert tool.timeout_ms == 30000

    def test_custom_timeout(self) -> None:
        """Custom timeout should be preserved."""
        tool = ScreenshotTool(timeout_ms=60000)
        assert tool.timeout_ms == 60000


# =============================================================================
# Tool Schema Tests
# =============================================================================

class TestScreenshotToolSchema:
    """Tests for ScreenshotTool schema definition."""

    @pytest.fixture
    def tool(self) -> ScreenshotTool:
        return ScreenshotTool()

    def test_tool_name(self, tool: ScreenshotTool) -> None:
        """Tool should have correct name."""
        assert tool.name == "screenshot"

    def test_tool_has_description(self, tool: ScreenshotTool) -> None:
        """Tool should have a description."""
        assert tool.description
        assert "screenshot" in tool.description.lower()

    def test_url_is_required_parameter(self, tool: ScreenshotTool) -> None:
        """URL should be a required parameter."""
        assert "url" in tool.parameters.get("required", [])

    def test_width_height_have_bounds(self, tool: ScreenshotTool) -> None:
        """Width and height should have min/max bounds."""
        props = tool.parameters["properties"]
        
        assert props["width"]["minimum"] == 320
        assert props["width"]["maximum"] == 3840
        assert props["height"]["minimum"] == 240
        assert props["height"]["maximum"] == 2160


# =============================================================================
# Parameter Validation Tests
# =============================================================================

class TestScreenshotToolValidation:
    """Tests for ScreenshotTool parameter validation."""

    @pytest.fixture
    def tool(self) -> ScreenshotTool:
        return ScreenshotTool()

    def test_missing_required_url(self, tool: ScreenshotTool) -> None:
        """Missing URL should produce validation error."""
        errors = tool.validate_params({})
        assert any("url" in e.lower() for e in errors)

    def test_valid_params_no_errors(self, tool: ScreenshotTool) -> None:
        """Valid parameters should produce no errors."""
        errors = tool.validate_params({
            "url": "https://example.com",
            "width": 1920,
            "height": 1080
        })
        assert errors == []

    def test_width_below_minimum(self, tool: ScreenshotTool) -> None:
        """Width below minimum should produce error."""
        errors = tool.validate_params({
            "url": "https://example.com",
            "width": 100
        })
        assert any("width" in e.lower() and "320" in e for e in errors)

    def test_width_above_maximum(self, tool: ScreenshotTool) -> None:
        """Width above maximum should produce error."""
        errors = tool.validate_params({
            "url": "https://example.com",
            "width": 5000
        })
        assert any("width" in e.lower() and "3840" in e for e in errors)

    def test_height_below_minimum(self, tool: ScreenshotTool) -> None:
        """Height below minimum should produce error."""
        errors = tool.validate_params({
            "url": "https://example.com",
            "height": 100
        })
        assert any("height" in e.lower() and "240" in e for e in errors)

    def test_height_above_maximum(self, tool: ScreenshotTool) -> None:
        """Height above maximum should produce error."""
        errors = tool.validate_params({
            "url": "https://example.com",
            "height": 5000
        })
        assert any("height" in e.lower() and "2160" in e for e in errors)

    def test_width_wrong_type(self, tool: ScreenshotTool) -> None:
        """Width as string should produce type error."""
        errors = tool.validate_params({
            "url": "https://example.com",
            "width": "1920"
        })
        assert any("width" in e.lower() and "integer" in e.lower() for e in errors)

    def test_full_page_wrong_type(self, tool: ScreenshotTool) -> None:
        """full_page as string should produce type error."""
        errors = tool.validate_params({
            "url": "https://example.com",
            "full_page": "true"
        })
        assert any("full_page" in e.lower() and "boolean" in e.lower() for e in errors)


# =============================================================================
# Execute Method Tests
# =============================================================================

def _create_playwright_mocks() -> tuple[AsyncMock, AsyncMock, AsyncMock, MagicMock]:
    """Create standard Playwright mock objects."""
    mock_page = AsyncMock()
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.close = AsyncMock()
    
    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_browser.close = AsyncMock()
    
    mock_playwright_instance = AsyncMock()
    mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
    
    mock_async_playwright_cm = MagicMock()
    mock_async_playwright_cm.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
    mock_async_playwright_cm.__aexit__ = AsyncMock(return_value=None)
    
    return mock_page, mock_browser, mock_playwright_instance, mock_async_playwright_cm


class TestScreenshotToolExecute:
    """Tests for ScreenshotTool.execute method with mocked Playwright."""

    @pytest.fixture
    def tool(self, tmp_path: Path) -> ScreenshotTool:
        """Create tool with temporary workspace."""
        return ScreenshotTool(workspace_path=str(tmp_path))

    @pytest.mark.asyncio
    async def test_invalid_url_returns_error(self, tool: ScreenshotTool) -> None:
        """Invalid URL should return error without calling Playwright."""
        result = await tool.execute(url="ftp://invalid.com")
        assert "Error" in result
        assert "validation failed" in result.lower()

    @pytest.mark.asyncio
    async def test_missing_domain_returns_error(self, tool: ScreenshotTool) -> None:
        """URL without domain should return error."""
        result = await tool.execute(url="http://")
        assert "Error" in result
        assert "domain" in result.lower()

    @pytest.mark.asyncio
    async def test_playwright_import_error(self, tool: ScreenshotTool) -> None:
        """Should return helpful error when Playwright import fails."""
        import sys
        
        # Save original modules
        original_playwright = sys.modules.get("playwright")
        original_async_api = sys.modules.get("playwright.async_api")
        
        # Remove playwright from modules to force ImportError
        sys.modules["playwright"] = None  # type: ignore
        sys.modules["playwright.async_api"] = None  # type: ignore
        
        try:
            result = await tool.execute(url="https://example.com")
            # The tool handles ImportError gracefully
            assert "Error" in result or "Playwright" in result or "screenshot" in result.lower()
        finally:
            # Restore original modules
            if original_playwright is not None:
                sys.modules["playwright"] = original_playwright
            if original_async_api is not None:
                sys.modules["playwright.async_api"] = original_async_api

    @pytest.mark.asyncio
    async def test_creates_screenshots_directory(self, tool: ScreenshotTool, tmp_path: Path) -> None:
        """Should create media/screenshots directory."""
        mock_page, mock_browser, _, mock_async_playwright_cm = _create_playwright_mocks()
        
        # Create mock module with async_playwright function
        mock_playwright_module = MagicMock()
        mock_playwright_module.async_playwright = MagicMock(return_value=mock_async_playwright_cm)
        mock_playwright_module.TimeoutError = TimeoutError
        
        with patch.dict("sys.modules", {"playwright.async_api": mock_playwright_module}):
            await tool.execute(url="https://example.com")
        
        screenshots_dir = tmp_path / "media" / "screenshots"
        assert screenshots_dir.exists()

    @pytest.mark.asyncio
    async def test_successful_screenshot_returns_info(self, tool: ScreenshotTool, tmp_path: Path) -> None:
        """Successful screenshot should return path and metadata."""
        mock_page, mock_browser, _, mock_async_playwright_cm = _create_playwright_mocks()
        
        mock_playwright_module = MagicMock()
        mock_playwright_module.async_playwright = MagicMock(return_value=mock_async_playwright_cm)
        mock_playwright_module.TimeoutError = TimeoutError
        
        with patch.dict("sys.modules", {"playwright.async_api": mock_playwright_module}):
            result = await tool.execute(
                url="https://example.com",
                width=1920,
                height=1080,
                full_page=True
            )
        
        assert "Screenshot captured successfully" in result
        assert "https://example.com" in result
        assert "1920x1080" in result
        assert "True" in result  # full_page

    @pytest.mark.asyncio
    async def test_browser_called_with_correct_viewport(self, tool: ScreenshotTool) -> None:
        """Browser should be configured with requested viewport."""
        mock_page, mock_browser, _, mock_async_playwright_cm = _create_playwright_mocks()
        
        mock_playwright_module = MagicMock()
        mock_playwright_module.async_playwright = MagicMock(return_value=mock_async_playwright_cm)
        mock_playwright_module.TimeoutError = TimeoutError
        
        with patch.dict("sys.modules", {"playwright.async_api": mock_playwright_module}):
            await tool.execute(url="https://example.com", width=800, height=600)
        
        # Check viewport was set correctly
        call_kwargs = mock_browser.new_context.call_args[1]
        assert call_kwargs["viewport"] == {"width": 800, "height": 600}

    @pytest.mark.asyncio
    async def test_full_page_screenshot_option(self, tool: ScreenshotTool) -> None:
        """full_page option should be passed to screenshot."""
        mock_page, mock_browser, _, mock_async_playwright_cm = _create_playwright_mocks()
        
        mock_playwright_module = MagicMock()
        mock_playwright_module.async_playwright = MagicMock(return_value=mock_async_playwright_cm)
        mock_playwright_module.TimeoutError = TimeoutError
        
        with patch.dict("sys.modules", {"playwright.async_api": mock_playwright_module}):
            await tool.execute(url="https://example.com", full_page=True)
        
        # Check full_page was passed to screenshot
        call_kwargs = mock_page.screenshot.call_args[1]
        assert call_kwargs["full_page"] is True


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestScreenshotToolEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def tool(self, tmp_path: Path) -> ScreenshotTool:
        return ScreenshotTool(workspace_path=str(tmp_path))

    @pytest.mark.asyncio
    async def test_timeout_error_handling(self, tool: ScreenshotTool) -> None:
        """Timeout errors should be caught and reported."""
        mock_page, mock_browser, _, mock_async_playwright_cm = _create_playwright_mocks()
        
        # Create a custom timeout exception
        class PlaywrightTimeout(Exception):
            pass
        
        mock_page.goto = AsyncMock(side_effect=PlaywrightTimeout("Page load timed out"))
        
        mock_playwright_module = MagicMock()
        mock_playwright_module.async_playwright = MagicMock(return_value=mock_async_playwright_cm)
        mock_playwright_module.TimeoutError = PlaywrightTimeout
        
        with patch.dict("sys.modules", {"playwright.async_api": mock_playwright_module}):
            result = await tool.execute(url="https://slow-site.example.com")
        
        assert "Error" in result
        assert "timed out" in result.lower()

    def test_url_with_special_characters(self) -> None:
        """URLs with special characters should be handled."""
        url = "https://example.com/path?query=hello%20world&foo=bar#section"
        is_valid, error = _validate_url(url)
        assert is_valid is True

    def test_url_with_port(self) -> None:
        """URLs with port numbers should be valid."""
        is_valid, error = _validate_url("https://localhost:3000/api")
        assert is_valid is True

    def test_url_with_ipv4(self) -> None:
        """URLs with IPv4 addresses should be valid."""
        is_valid, error = _validate_url("http://192.168.1.1:8080")
        assert is_valid is True
