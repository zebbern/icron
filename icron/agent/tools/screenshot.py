"""Screenshot tool using Playwright for browser automation."""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from icron.agent.tools.base import Tool


def _validate_url(url: str) -> tuple[bool, str]:
    """
    Validate URL format for screenshot capture.

    Args:
        url: The URL to validate.

    Returns:
        Tuple of (is_valid, error_message). Error message is empty if valid.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False, f"Only http/https allowed, got '{parsed.scheme or 'none'}'"
        if not parsed.netloc:
            return False, "Missing domain"
        return True, ""
    except Exception as e:
        return False, str(e)


def _generate_filename(url: str) -> str:
    """
    Generate a unique filename for the screenshot.

    Args:
        url: The URL being captured.

    Returns:
        Filename in format: screenshot_{timestamp}_{url_hash}.png
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"screenshot_{timestamp}_{url_hash}.png"


class ScreenshotTool(Tool):
    """
    Capture screenshots of web pages using Playwright.

    This tool launches a headless Chromium browser, navigates to the specified URL,
    and captures a screenshot. Supports full-page captures and custom viewport sizes.
    """

    name = "screenshot"
    description = (
        "Capture a screenshot of a web page. Returns the file path for attachment. "
        "Supports full-page screenshots and custom viewport dimensions."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL of the web page to capture (must be http/https)"
            },
            "full_page": {
                "type": "boolean",
                "description": "Capture the full scrollable page (default: False)",
                "default": False
            },
            "width": {
                "type": "integer",
                "description": "Viewport width in pixels (default: 1280)",
                "minimum": 320,
                "maximum": 3840,
                "default": 1280
            },
            "height": {
                "type": "integer",
                "description": "Viewport height in pixels (default: 720)",
                "minimum": 240,
                "maximum": 2160,
                "default": 720
            }
        },
        "required": ["url"]
    }

    def __init__(self, workspace_path: str | None = None, timeout_ms: int = 30000) -> None:
        """
        Initialize the screenshot tool.

        Args:
            workspace_path: Base path for saving screenshots. Defaults to current directory.
            timeout_ms: Page load timeout in milliseconds (default: 30000).
        """
        self.workspace_path = Path(workspace_path) if workspace_path else Path.cwd()
        self.timeout_ms = timeout_ms

    async def execute(
        self,
        url: str,
        full_page: bool = False,
        width: int = 1280,
        height: int = 720,
        **kwargs: Any
    ) -> str:
        """
        Capture a screenshot of the specified URL.

        Args:
            url: The web page URL to capture.
            full_page: Whether to capture the full scrollable page.
            width: Viewport width in pixels.
            height: Viewport height in pixels.
            **kwargs: Additional keyword arguments (ignored).

        Returns:
            Success message with file path, or error message on failure.
        """
        # Validate URL
        is_valid, error_msg = _validate_url(url)
        if not is_valid:
            return f"Error: URL validation failed - {error_msg}"

        # Ensure media/screenshots directory exists
        screenshots_dir = self.workspace_path / "media" / "screenshots"
        try:
            screenshots_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return f"Error: Failed to create screenshots directory - {e}"

        # Generate output path
        filename = _generate_filename(url)
        output_path = screenshots_dir / filename

        try:
            from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
        except ImportError:
            return (
                "Error: Playwright not installed. "
                "Install with: pip install playwright && playwright install chromium"
            )

        browser = None
        try:
            async with async_playwright() as p:
                # Launch headless Chromium browser
                browser = await p.chromium.launch(headless=True)

                # Create browser context with viewport
                context = await browser.new_context(
                    viewport={"width": width, "height": height},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                )

                # Create page and navigate
                page = await context.new_page()

                try:
                    await page.goto(url, wait_until="networkidle", timeout=self.timeout_ms)
                except PlaywrightTimeout:
                    # Fall back to domcontentloaded if networkidle times out
                    await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)

                # Capture screenshot
                await page.screenshot(path=str(output_path), full_page=full_page)

                # Close context and browser
                await context.close()
                await browser.close()
                browser = None

            # Return success with ABSOLUTE path for attachment (required by media parameter)
            return (
                f"Screenshot captured successfully.\n"
                f"URL: {url}\n"
                f"Path: {output_path}\n"
                f"Dimensions: {width}x{height}\n"
                f"Full page: {full_page}\n\n"
                f"To send this screenshot, use: message(content=\"your text\", media=[\"{output_path}\"])"
            )

        except PlaywrightTimeout:
            return f"Error: Page load timed out after {self.timeout_ms}ms - {url}"
        except Exception as e:
            return f"Error: Screenshot capture failed - {type(e).__name__}: {e}"
        finally:
            # Ensure browser is closed on error
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
