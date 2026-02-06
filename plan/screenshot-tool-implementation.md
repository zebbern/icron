# Screenshot Tool Implementation Plan

## Overview
Implement native Playwright-based screenshot tool for icron.

## Tasks

- [x] Task 1: Create `icron/agent/tools/screenshot.py` - Core screenshot tool
- [x] Task 2: Update `pyproject.toml` - Add playwright dependency
- [x] Task 3: Register tool in `icron/agent/loop.py`
- [x] Task 4: Update `icron/agent/tools/__init__.py` exports
- [x] Task 5: Add Telegram media support in `icron/channels/telegram.py`
- [x] Task 6: Create `tests/test_screenshot.py` - Unit tests (50 tests)
- [x] Task 7: Update `docs/integrations.md` and `README.md`

## Technical Design

### Screenshot Tool Schema
```python
class ScreenshotTool(Tool):
    name = "screenshot"
    description = "Capture screenshot of a webpage using headless browser"
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to screenshot"},
            "full_page": {"type": "boolean", "description": "Capture full scrollable page"},
            "width": {"type": "integer", "description": "Viewport width (default: 1280)"},
            "height": {"type": "integer", "description": "Viewport height (default: 720)"}
        },
        "required": ["url"]
    }
```

### File Storage
- Screenshots saved to: `~/.icron/media/screenshots/`
- Filename format: `screenshot_{timestamp}_{hash}.png`
- Returns path for OutboundMessage.media attachment

### Dependencies
- `playwright>=1.40.0`
- Post-install: `playwright install chromium`

## Status
Created: 2026-02-06
Status: In Progress
