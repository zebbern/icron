"""Reminder tool for scheduling timed messages."""

import re
import time
from datetime import datetime, timedelta
from typing import Any, TYPE_CHECKING

from icron.agent.tools.base import Tool

if TYPE_CHECKING:
    from icron.cron.service import CronService


def _parse_duration(text: str) -> int | None:
    """
    Parse a duration like '5 minutes', '2 hours', '30 seconds' into milliseconds.
    
    Returns None if parsing fails.
    """
    text = text.lower().strip()
    
    # Patterns: "5 minutes", "2 hours", "30 seconds", "1 hour"
    patterns = [
        (r"(\d+)\s*(?:second|sec|s)s?", 1000),
        (r"(\d+)\s*(?:minute|min|m)s?", 60 * 1000),
        (r"(\d+)\s*(?:hour|hr|h)s?", 60 * 60 * 1000),
        (r"(\d+)\s*(?:day|d)s?", 24 * 60 * 60 * 1000),
    ]
    
    total_ms = 0
    found = False
    
    for pattern, multiplier in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            total_ms += int(match) * multiplier
            found = True
    
    return total_ms if found else None


def _parse_time_expression(text: str) -> int | None:
    """
    Parse various time expressions into a future timestamp in milliseconds.
    
    Supports:
    - "in 5 minutes"
    - "in 2 hours"
    - "at 2pm"
    - "at 14:30"
    - "tomorrow at 9am"
    
    Returns None if parsing fails.
    """
    text = text.lower().strip()
    now = datetime.now()
    
    # "in X duration" pattern
    if text.startswith("in "):
        duration_text = text[3:]
        duration_ms = _parse_duration(duration_text)
        if duration_ms:
            return int(time.time() * 1000) + duration_ms
    
    # "at HH:MM" or "at H:MM am/pm" pattern
    at_match = re.search(r"at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
    if at_match:
        hour = int(at_match.group(1))
        minute = int(at_match.group(2) or 0)
        period = at_match.group(3)
        
        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0
        
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # If time has passed today, schedule for tomorrow
        if target <= now:
            target += timedelta(days=1)
        
        # Check for "tomorrow" in the text
        if "tomorrow" in text:
            if target.date() == now.date():
                target += timedelta(days=1)
        
        return int(target.timestamp() * 1000)
    
    # Try pure duration parsing
    duration_ms = _parse_duration(text)
    if duration_ms:
        return int(time.time() * 1000) + duration_ms
    
    return None


class ReminderTool(Tool):
    """
    Tool to set reminders that will be delivered at a future time.
    
    The reminder will be sent back to the user through the same channel
    at the specified time.
    """
    
    def __init__(self, cron_service: "CronService | None" = None, channel: str = "", chat_id: str = ""):
        self._cron_service = cron_service
        self._channel = channel
        self._chat_id = chat_id
    
    def set_context(self, channel: str, chat_id: str) -> None:
        """Update the current channel context."""
        self._channel = channel
        self._chat_id = chat_id
    
    def set_cron_service(self, cron_service: "CronService") -> None:
        """Set the cron service reference."""
        self._cron_service = cron_service
    
    @property
    def name(self) -> str:
        return "set_reminder"
    
    @property
    def description(self) -> str:
        return (
            "Set a reminder that will be delivered at a future time. "
            "Use this when the user asks to be reminded about something. "
            "Supports expressions like 'in 5 minutes', 'in 2 hours', 'at 3pm', 'at 14:30', 'tomorrow at 9am'."
        )
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The reminder message to send to the user"
                },
                "when": {
                    "type": "string",
                    "description": "When to send the reminder (e.g., 'in 5 minutes', 'at 2pm', 'in 1 hour')"
                }
            },
            "required": ["message", "when"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """Set a reminder."""
        message = kwargs.get("message", "")
        when = kwargs.get("when", "")
        
        if not message:
            return "Error: 'message' is required"
        if not when:
            return "Error: 'when' is required"
        
        if not self._cron_service:
            return "Error: Reminder service not available"
        
        if not self._channel or not self._chat_id:
            return "Error: Cannot determine where to send reminder"
        
        # Parse the time expression
        target_ms = _parse_time_expression(when)
        if not target_ms:
            return f"Error: Could not understand time expression '{when}'. Try 'in 5 minutes' or 'at 2pm'."
        
        # Calculate when the reminder will trigger
        now_ms = int(time.time() * 1000)
        if target_ms <= now_ms:
            return "Error: Reminder time must be in the future"
        
        # Format the reminder message
        reminder_text = f"⏰ **Reminder:** {message}"
        
        # Create the cron job as a system_event (delivers directly, no agent processing)
        from icron.cron.types import CronSchedule, CronPayload
        
        self._cron_service.add_job(
            name=f"Reminder: {message[:30]}...",
            schedule=CronSchedule(kind="at", at_ms=target_ms),
            payload=CronPayload(
                kind="system_event",
                message=reminder_text,
                deliver=True,
                channel=self._channel,
                to=self._chat_id,
            ),
            delete_after_run=True,
        )
        
        # Format human-readable time with exact trigger time
        target_time = datetime.fromtimestamp(target_ms / 1000)
        time_diff = (target_ms - now_ms) / 1000
        
        # Include the actual trigger time so the LLM doesn't guess
        trigger_time_str = target_time.strftime('%H:%M:%S')
        
        if time_diff < 60:
            when_str = f"in {int(time_diff)} seconds (at {trigger_time_str})"
        elif time_diff < 3600:
            when_str = f"in {int(time_diff / 60)} minutes (at {trigger_time_str})"
        elif time_diff < 86400:
            when_str = f"at {target_time.strftime('%I:%M %p')}"
        else:
            when_str = f"on {target_time.strftime('%b %d at %I:%M %p')}"
        
        return f"✅ Reminder scheduled {when_str}. Message: \"{message}\" (Do not recalculate or restate the time - use exactly what's shown.)"


class ListRemindersool(Tool):
    """Tool to list active reminders."""
    
    def __init__(self, cron_service: "CronService | None" = None):
        self._cron_service = cron_service
    
    def set_cron_service(self, cron_service: "CronService") -> None:
        """Set the cron service reference."""
        self._cron_service = cron_service
    
    @property
    def name(self) -> str:
        return "list_reminders"
    
    @property
    def description(self) -> str:
        return "List all active reminders/scheduled jobs."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """List active reminders."""
        if not self._cron_service:
            return "Error: Reminder service not available"
        
        jobs = self._cron_service.list_jobs()
        
        if not jobs:
            return "📭 No active reminders."
        
        lines = ["📋 **Active Reminders:**"]
        for job in jobs:
            if job.state.next_run_at_ms:
                when = datetime.fromtimestamp(job.state.next_run_at_ms / 1000)
                time_str = when.strftime("%b %d, %I:%M %p")
                lines.append(f"- [{job.id}] {job.name} - {time_str}")
        
        return "\n".join(lines)


class CancelReminderTool(Tool):
    """Tool to cancel a reminder."""
    
    def __init__(self, cron_service: "CronService | None" = None):
        self._cron_service = cron_service
    
    def set_cron_service(self, cron_service: "CronService") -> None:
        """Set the cron service reference."""
        self._cron_service = cron_service
    
    @property
    def name(self) -> str:
        return "cancel_reminder"
    
    @property
    def description(self) -> str:
        return "Cancel an active reminder by its ID."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "reminder_id": {
                    "type": "string",
                    "description": "The ID of the reminder to cancel (get from list_reminders)"
                }
            },
            "required": ["reminder_id"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """Cancel a reminder."""
        reminder_id = kwargs.get("reminder_id", "")
        
        if not reminder_id:
            return "Error: 'reminder_id' is required"
        
        if not self._cron_service:
            return "Error: Reminder service not available"
        
        success = self._cron_service.remove_job(reminder_id)
        
        if success:
            return f"✅ Reminder {reminder_id} cancelled."
        else:
            return f"❌ Could not find reminder with ID '{reminder_id}'"
