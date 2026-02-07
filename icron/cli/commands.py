"""CLI commands for icron."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from icron import __version__, __logo__

app = typer.Typer(
    name="icron",
    help=f"{__logo__} icron - Personal AI Assistant",
    no_args_is_help=True,
)

console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"{__logo__} icron v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """icron - Personal AI Assistant."""
    pass


# ============================================================================
# Onboard / Setup
# ============================================================================


@app.command()
def onboard():
    """Initialize icron configuration and workspace."""
    from icron.config.loader import get_config_path, save_config
    from icron.config.schema import Config
    from icron.utils.helpers import get_workspace_path
    
    config_path = get_config_path()
    
    if config_path.exists():
        console.print(f"[yellow]Config already exists at {config_path}[/yellow]")
        if not typer.confirm("Overwrite?"):
            raise typer.Exit()
    
    # Create default config
    config = Config()
    save_config(config)
    console.print(f"[green]✓[/green] Created config at {config_path}")
    
    # Create workspace
    workspace = get_workspace_path()
    console.print(f"[green]✓[/green] Created workspace at {workspace}")
    
    # Create default bootstrap files
    _create_workspace_templates(workspace)
    
    console.print(f"\n{__logo__} icron is ready!")
    console.print("\nNext steps:")
    console.print("  1. Add your API key to [cyan]~/.icron/config.json[/cyan]")
    console.print("     Get one at: https://openrouter.ai/keys")
    console.print("  2. Chat: [cyan]icron agent -m \"Hello!\"[/cyan]")
    console.print("\n[dim]Want Telegram/WhatsApp? See: https://github.com/zebbern/icron#-chat-apps[/dim]")




def _create_workspace_templates(workspace: Path):
    """Create default workspace template files."""
    templates = {
        "AGENTS.md": """# Agent Instructions

You are a helpful AI assistant. Be concise, accurate, and friendly.

## Guidelines

- Always explain what you're doing before taking actions
- Ask for clarification when the request is ambiguous
- Use tools to help accomplish tasks
- Remember important information in your memory files
""",
        "SOUL.md": """# Soul

I am icron, a lightweight AI assistant.

## Personality

- Helpful and friendly
- Concise and to the point
- Curious and eager to learn

## Values

- Accuracy over speed
- User privacy and safety
- Transparency in actions
""",
        "USER.md": """# User

Information about the user goes here.

## Preferences

- Communication style: (casual/formal)
- Timezone: (your timezone)
- Language: (your preferred language)
""",
    }
    
    for filename, content in templates.items():
        file_path = workspace / filename
        if not file_path.exists():
            file_path.write_text(content)
            console.print(f"  [dim]Created {filename}[/dim]")
    
    # Create memory directory and MEMORY.md
    memory_dir = workspace / "memory"
    memory_dir.mkdir(exist_ok=True)
    memory_file = memory_dir / "MEMORY.md"
    if not memory_file.exists():
        memory_file.write_text("""# Long-term Memory

This file stores important information that should persist across sessions.

## User Information

(Important facts about the user)

## Preferences

(User preferences learned over time)

## Important Notes

(Things to remember)
""")
        console.print("  [dim]Created memory/MEMORY.md[/dim]")


# ============================================================================
# Setup Wizard
# ============================================================================

# Provider info for setup wizard
PROVIDER_INFO = {
    "anthropic": {
        "name": "Anthropic (Claude)",
        "models": [
            "anthropic/claude-opus-4-5",
            "anthropic/claude-sonnet-4-20250514",
            "anthropic/claude-3-5-sonnet-20241022",
            "anthropic/claude-3-5-haiku-20241022",
        ],
        "key_url": "https://console.anthropic.com/settings/keys",
        "key_prefix": "sk-ant-",
    },
    "openai": {
        "name": "OpenAI (GPT)",
        "models": [
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "openai/gpt-4-turbo",
            "openai/o1-preview",
        ],
        "key_url": "https://platform.openai.com/api-keys",
        "key_prefix": "sk-",
    },
    "openrouter": {
        "name": "OpenRouter (Any Model)",
        "models": [
            "anthropic/claude-opus-4-5",
            "openai/gpt-4o",
            "meta-llama/llama-3.1-70b-instruct",
            "google/gemini-2.0-flash-001",
        ],
        "key_url": "https://openrouter.ai/keys",
        "key_prefix": "sk-or-",
    },
    "gemini": {
        "name": "Google Gemini",
        "models": [
            "gemini/gemini-2.0-flash",
            "gemini/gemini-1.5-pro",
            "gemini/gemini-1.5-flash",
        ],
        "key_url": "https://aistudio.google.com/apikey",
        "key_prefix": "",
    },
    "local": {
        "name": "Local/vLLM (Self-hosted)",
        "models": ["custom"],
        "key_url": None,
        "key_prefix": "",
    },
}


def _test_api_connection(provider: str, api_key: str, api_base: str | None = None) -> tuple[bool, str]:
    """Test API connection with a minimal request. Returns (success, message)."""
    import httpx
    
    if provider == "local":
        if not api_base:
            return False, "API base URL required for local provider"
        try:
            resp = httpx.get(f"{api_base.rstrip('/')}/models", timeout=10)
            if resp.status_code == 200:
                return True, "Connected to local server"
            return False, f"Server returned {resp.status_code}"
        except Exception as e:
            return False, f"Connection failed: {e}"
    
    # Test with minimal chat completion
    endpoints = {
        "anthropic": ("https://api.anthropic.com/v1/messages", {
            "model": "claude-3-haiku-20240307",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "hi"}],
        }, {"x-api-key": api_key, "anthropic-version": "2023-06-01"}),
        "openai": ("https://api.openai.com/v1/chat/completions", {
            "model": "gpt-4o-mini",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "hi"}],
        }, {"Authorization": f"Bearer {api_key}"}),
        "openrouter": ("https://openrouter.ai/api/v1/chat/completions", {
            "model": "openai/gpt-4o-mini",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "hi"}],
        }, {"Authorization": f"Bearer {api_key}"}),
        "gemini": (f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}", {
            "contents": [{"parts": [{"text": "hi"}]}],
            "generationConfig": {"maxOutputTokens": 1},
        }, {}),
    }
    
    if provider not in endpoints:
        return False, f"Unknown provider: {provider}"
    
    url, body, headers = endpoints[provider]
    headers["Content-Type"] = "application/json"
    
    try:
        resp = httpx.post(url, json=body, headers=headers, timeout=30)
        if resp.status_code in (200, 201):
            return True, "API key verified"
        elif resp.status_code == 401:
            return False, "Invalid API key"
        elif resp.status_code == 403:
            return False, "API key lacks permissions"
        elif resp.status_code == 429:
            # Rate limit still means key is valid
            return True, "API key verified (rate limited)"
        else:
            try:
                err = resp.json()
                msg = err.get("error", {}).get("message", resp.text[:100])
            except Exception:
                msg = resp.text[:100]
            return False, f"API error ({resp.status_code}): {msg}"
    except httpx.TimeoutException:
        return False, "Connection timed out"
    except Exception as e:
        return False, f"Connection error: {e}"


@app.command()
def setup(
    guided: bool = typer.Option(True, "--guided/--quick", help="Run interactive guided setup"),
):
    """Interactive setup wizard for icron configuration."""
    from rich.prompt import Prompt, Confirm
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.panel import Panel
    from rich.markdown import Markdown
    
    from icron.config.loader import get_config_path, save_config, load_config
    from icron.config.schema import Config
    from icron.utils.helpers import get_workspace_path
    
    config_path = get_config_path()
    
    console.print(Panel.fit(
        f"[bold cyan]{__logo__} icron Setup Wizard[/bold cyan]\n\n"
        "This wizard will help you configure icron step by step.",
        border_style="cyan"
    ))
    
    # Check for existing config
    if config_path.exists():
        console.print(f"\n[yellow]Existing config found at {config_path}[/yellow]")
        if not Confirm.ask("Modify existing configuration?", default=True):
            raise typer.Exit()
        config = load_config()
    else:
        config = Config()
    
    console.print()
    
    # Step 1: Provider Selection
    console.print("[bold]Step 1/5: LLM Provider[/bold]")
    console.print("Which AI provider would you like to use?\n")
    
    providers = list(PROVIDER_INFO)
    for i, prov in enumerate(providers, 1):
        info = PROVIDER_INFO[prov]
        console.print(f"  [{i}] {info['name']}")
    
    while True:
        choice = Prompt.ask(
            "\nEnter number",
            default="1",
            show_default=True
        )
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(providers):
                selected_provider = providers[idx]
                break
        except ValueError:
            pass
        console.print("[red]Invalid choice. Enter a number 1-5.[/red]")
    
    provider_info = PROVIDER_INFO[selected_provider]
    console.print(f"\n[green]✓[/green] Selected: {provider_info['name']}\n")
    
    # Step 2: API Key
    console.print("[bold]Step 2/5: API Key[/bold]")
    
    if selected_provider == "local":
        console.print("For local/vLLM, enter your server's base URL.")
        api_base = Prompt.ask("API Base URL", default="http://localhost:8000/v1")
        api_key = Prompt.ask("API Key (optional, press Enter to skip)", default="", password=True)
        config.providers.vllm.api_base = api_base
        if api_key:
            config.providers.vllm.api_key = api_key
    else:
        key_url = provider_info.get("key_url")
        if key_url:
            console.print(f"Get your API key at: [link={key_url}]{key_url}[/link]")
        
        # Check existing key
        existing_key = getattr(config.providers, selected_provider).api_key
        if existing_key:
            masked = f"{existing_key[:8]}...{existing_key[-4:]}"
            console.print(f"[dim]Current key: {masked}[/dim]")
            if not Confirm.ask("Replace existing key?", default=False):
                api_key = existing_key
            else:
                api_key = Prompt.ask("Enter API key", password=True)
        else:
            api_key = Prompt.ask("Enter API key", password=True)
        
        if not api_key:
            console.print("[red]API key is required.[/red]")
            raise typer.Exit(1)
        
        # Set the key
        setattr(getattr(config.providers, selected_provider), "api_key", api_key)
        api_base = None
    
    # Test connection
    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Testing API connection...", total=None)
        success, message = _test_api_connection(selected_provider, api_key, api_base)
    
    if success:
        console.print(f"[green]✓[/green] {message}\n")
    else:
        console.print(f"[red]✗[/red] {message}")
        if not Confirm.ask("Continue anyway?", default=False):
            raise typer.Exit(1)
        console.print()
    
    # Step 3: Model Selection
    console.print("[bold]Step 3/5: Model Selection[/bold]")
    
    models = provider_info["models"]
    if selected_provider == "local":
        model = Prompt.ask("Enter model name", default="")
        if not model:
            console.print("[yellow]No model specified. You can set this later.[/yellow]")
    else:
        console.print("Recommended models:\n")
        for i, model_name in enumerate(models, 1):
            console.print(f"  [{i}] {model_name}")
        console.print(f"  [c] Custom (enter your own)")
        
        while True:
            choice = Prompt.ask("\nEnter number or 'c' for custom", default="1")
            if choice.lower() == "c":
                model = Prompt.ask("Enter model name")
                break
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(models):
                    model = models[idx]
                    break
            except ValueError:
                pass
            console.print("[red]Invalid choice.[/red]")
    
    if model:
        config.agents.defaults.model = model
        console.print(f"\n[green]✓[/green] Model: {model}\n")
    
    # Step 4: Workspace
    console.print("[bold]Step 4/5: Workspace Location[/bold]")
    console.print("Where should icron store its workspace files?\n")
    
    default_workspace = "~/.icron/workspace"
    workspace_input = Prompt.ask("Workspace path", default=default_workspace)
    workspace_path = Path(workspace_input).expanduser()
    
    # Validate/create workspace
    try:
        workspace_path.mkdir(parents=True, exist_ok=True)
        test_file = workspace_path / ".icron_test"
        test_file.write_text("test")
        test_file.unlink()
        console.print(f"[green]✓[/green] Workspace: {workspace_path}\n")
        config.agents.defaults.workspace = workspace_input
    except Exception as e:
        console.print(f"[red]✗[/red] Cannot write to workspace: {e}")
        if not Confirm.ask("Continue with default workspace?", default=True):
            raise typer.Exit(1)
        config.agents.defaults.workspace = default_workspace
        workspace_path = Path(default_workspace).expanduser()
        workspace_path.mkdir(parents=True, exist_ok=True)
        console.print()
    
    # Step 5: Optional Channels
    console.print("[bold]Step 5/5: Chat Channels (Optional)[/bold]")
    console.print("Configure chat channels to interact with icron.\n")
    
    # Telegram
    if Confirm.ask("Set up Telegram?", default=False):
        console.print("\nGet a bot token from @BotFather on Telegram")
        tg_token = Prompt.ask("Bot token", password=True)
        if tg_token:
            config.channels.telegram.enabled = True
            config.channels.telegram.token = tg_token
            tg_users = Prompt.ask("Allowed user IDs/usernames (comma-separated, or empty for all)", default="")
            if tg_users:
                config.channels.telegram.allow_from = [u.strip() for u in tg_users.split(",") if u.strip()]
            console.print("[green]✓[/green] Telegram configured\n")
    
    # Discord
    if Confirm.ask("Set up Discord?", default=False):
        console.print("\nCreate a bot at https://discord.com/developers/applications")
        dc_token = Prompt.ask("Bot token", password=True)
        if dc_token:
            config.channels.discord.enabled = True
            config.channels.discord.token = dc_token
            dc_users = Prompt.ask("Allowed user IDs (comma-separated, or empty for all)", default="")
            if dc_users:
                config.channels.discord.allow_from = [u.strip() for u in dc_users.split(",") if u.strip()]
            console.print("[green]✓[/green] Discord configured\n")
    
    # Save configuration
    console.print("[bold]Saving configuration...[/bold]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Writing config...", total=None)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        save_config(config)
    
    console.print(f"[green]✓[/green] Config saved to {config_path}\n")
    
    # Create workspace templates
    _create_workspace_templates(workspace_path)
    
    # Summary
    console.print(Panel.fit(
        f"[bold green]Setup Complete![/bold green]\n\n"
        f"Provider: {provider_info['name']}\n"
        f"Model: {config.agents.defaults.model}\n"
        f"Workspace: {workspace_path}\n"
        f"Config: {config_path}\n\n"
        "[bold]Next steps:[/bold]\n"
        "  • Chat: [cyan]icron agent -m \"Hello!\"[/cyan]\n"
        "  • Start gateway: [cyan]icron gateway[/cyan]\n"
        "  • Validate config: [cyan]icron validate[/cyan]",
        border_style="green"
    ))


@app.command()
def validate():
    """Validate icron configuration and environment."""
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    
    from icron.config.loader import get_config_path, load_config
    
    console.print(Panel.fit(
        f"[bold cyan]{__logo__} icron Configuration Validator[/bold cyan]",
        border_style="cyan"
    ))
    console.print()
    
    checks_passed = 0
    checks_failed = 0
    warnings = 0
    
    def pass_check(msg: str):
        nonlocal checks_passed
        checks_passed += 1
        console.print(f"[green]✓[/green] {msg}")
    
    def fail_check(msg: str, suggestion: str = ""):
        nonlocal checks_failed
        checks_failed += 1
        console.print(f"[red]✗[/red] {msg}")
        if suggestion:
            console.print(f"  [dim]→ {suggestion}[/dim]")
    
    def warn_check(msg: str):
        nonlocal warnings
        warnings += 1
        console.print(f"[yellow]![/yellow] {msg}")
    
    # Check 1: Config file exists
    console.print("[bold]Configuration File[/bold]")
    config_path = get_config_path()
    
    if config_path.exists():
        pass_check(f"Config exists: {config_path}")
    else:
        fail_check(
            f"Config not found: {config_path}",
            "Run 'icron setup' to create configuration"
        )
        console.print(f"\n[red]Cannot continue without config file.[/red]")
        raise typer.Exit(1)
    
    # Check 2: Valid JSON
    import json
    try:
        with open(config_path, encoding="utf-8") as f:
            json.load(f)  # Validate JSON is parseable
        pass_check("Valid JSON format")
    except json.JSONDecodeError as e:
        fail_check(
            f"Invalid JSON: {e}",
            "Fix JSON syntax errors in config file"
        )
        raise typer.Exit(1)
    
    # Check 3: Schema validation
    try:
        config = load_config()
        pass_check("Schema validation passed")
    except Exception as e:
        fail_check(
            f"Schema validation failed: {e}",
            "Check config structure matches expected format"
        )
        raise typer.Exit(1)
    
    # Check 4: Provider configuration
    console.print("\n[bold]API Providers[/bold]")
    
    has_provider = False
    providers_to_test = []
    
    if config.providers.anthropic.api_key:
        pass_check("Anthropic API key configured")
        providers_to_test.append(("anthropic", config.providers.anthropic.api_key, None))
        has_provider = True
    
    if config.providers.openai.api_key:
        pass_check("OpenAI API key configured")
        providers_to_test.append(("openai", config.providers.openai.api_key, None))
        has_provider = True
    
    if config.providers.openrouter.api_key:
        pass_check("OpenRouter API key configured")
        providers_to_test.append(("openrouter", config.providers.openrouter.api_key, None))
        has_provider = True
    
    if config.providers.gemini.api_key:
        pass_check("Gemini API key configured")
        providers_to_test.append(("gemini", config.providers.gemini.api_key, None))
        has_provider = True
    
    if config.providers.vllm.api_base:
        pass_check(f"vLLM/Local configured: {config.providers.vllm.api_base}")
        providers_to_test.append(("local", config.providers.vllm.api_key, config.providers.vllm.api_base))
        has_provider = True
    
    if not has_provider:
        fail_check(
            "No LLM provider configured",
            "Run 'icron setup' to configure a provider"
        )
    
    # Test API connections
    if providers_to_test:
        console.print("\n[bold]API Connection Tests[/bold]")
        for provider, api_key, api_base in providers_to_test:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task(f"Testing {provider}...", total=None)
                success, message = _test_api_connection(provider, api_key, api_base)
            
            if success:
                pass_check(f"{provider}: {message}")
            else:
                fail_check(f"{provider}: {message}")
    
    # Check 5: Workspace
    console.print("\n[bold]Workspace[/bold]")
    workspace = config.workspace_path
    
    if workspace.exists():
        pass_check(f"Workspace exists: {workspace}")
        
        # Check write permissions
        try:
            test_file = workspace / ".icron_validate_test"
            test_file.write_text("test")
            test_file.unlink()
            pass_check("Workspace is writable")
        except Exception as e:
            fail_check(
                f"Workspace not writable: {e}",
                "Check file permissions on workspace directory"
            )
        
        # Check for key files
        for filename in ["AGENTS.md", "SOUL.md"]:
            if (workspace / filename).exists():
                pass_check(f"Found {filename}")
            else:
                warn_check(f"Missing {filename} (optional)")
    else:
        fail_check(
            f"Workspace not found: {workspace}",
            "Run 'icron setup' or 'icron onboard' to create workspace"
        )
    
    # Check 6: Channels
    console.print("\n[bold]Chat Channels[/bold]")
    
    channels_configured = False
    
    if config.channels.telegram.enabled:
        if config.channels.telegram.token:
            pass_check("Telegram enabled and configured")
            channels_configured = True
        else:
            fail_check(
                "Telegram enabled but no token set",
                "Add bot token from @BotFather"
            )
    
    if config.channels.discord.enabled:
        if config.channels.discord.token:
            pass_check("Discord enabled and configured")
            channels_configured = True
        else:
            fail_check(
                "Discord enabled but no token set",
                "Add bot token from Discord Developer Portal"
            )
    
    if config.channels.slack.enabled:
        if config.channels.slack.bot_token and config.channels.slack.app_token:
            pass_check("Slack enabled and configured")
            channels_configured = True
        else:
            fail_check(
                "Slack enabled but tokens missing",
                "Add bot_token (xoxb-) and app_token (xapp-)"
            )
    
    if config.channels.whatsapp.enabled:
        pass_check("WhatsApp enabled")
        channels_configured = True
    
    if not channels_configured:
        warn_check("No chat channels configured (optional)")
    
    # Check 7: MCP
    console.print("\n[bold]MCP (Model Context Protocol)[/bold]")
    
    if config.tools.mcp.enabled:
        mcp_count = len(config.tools.mcp.servers)
        if mcp_count > 0:
            pass_check(f"MCP enabled with {mcp_count} server(s)")
            for name, server in config.tools.mcp.servers.items():
                if server.transport == "sse":
                    console.print(f"  [dim]• {name}: SSE ({server.url})[/dim]")
                else:
                    console.print(f"  [dim]• {name}: stdio ({server.command})[/dim]")
        else:
            warn_check("MCP enabled but no servers configured")
    else:
        console.print("[dim]MCP disabled[/dim]")
    
    # Summary
    console.print()
    total = checks_passed + checks_failed
    if checks_failed == 0:
        status_color = "green"
        status_text = "All checks passed!"
    else:
        status_color = "red"
        status_text = f"{checks_failed} check(s) failed"
    
    console.print(Panel.fit(
        f"[bold {status_color}]{status_text}[/bold {status_color}]\n\n"
        f"[green]Passed:[/green] {checks_passed}\n"
        f"[red]Failed:[/red] {checks_failed}\n"
        f"[yellow]Warnings:[/yellow] {warnings}",
        border_style=status_color
    ))
    
    if checks_failed > 0:
        raise typer.Exit(1)


# ============================================================================
# Gateway / Server
# ============================================================================


@app.command()
def gateway(
    port: int = typer.Option(3883, "--port", "-p", help="Gateway port"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Start the icron gateway."""
    import html
    import json
    import os
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from urllib.parse import parse_qs, urlparse

    from icron.config.loader import (
        load_config,
        save_config,
        get_config_path,
        get_data_dir,
        convert_keys,
        convert_to_camel,
    )
    from icron.config.schema import Config
    from icron.bus.queue import MessageBus
    from icron.providers.factory import create_provider, ProviderConfigError
    from icron.agent.loop import AgentLoop
    from icron.channels.manager import ChannelManager
    from icron.cron.service import CronService
    from icron.cron.types import CronJob
    from icron.heartbeat.service import HeartbeatService
    
    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)

    console.print(f"{__logo__} Starting icron gateway on port {port}...")

    config = load_config()

    def _escape(value: str) -> str:
        return html.escape(value or "")

    def _is_true(value: str | None) -> bool:
        return (value or "").lower() in {"1", "true", "yes", "on"}

    def _get_field(fields: dict[str, list[str]], name: str) -> str:
        return (fields.get(name, [""])[0] or "").strip()

    def _render_settings_page(saved: bool = False, error: str | None = None) -> str:
        cfg = load_config()
        cfg_path = get_config_path()
        write_mode = os.getenv("ICRON_WRITE_CONFIG", "auto")

        together_set = bool(cfg.providers.together.api_key)
        openrouter_set = bool(cfg.providers.openrouter.api_key)
        brave_set = bool(cfg.tools.web.search.api_key)
        telegram_set = bool(cfg.channels.telegram.token)

        allow_from = ", ".join(cfg.channels.telegram.allow_from)
        raw_json = ""
        if cfg_path.exists():
            try:
                raw_json = cfg_path.read_text(encoding="utf-8")
            except Exception:
                raw_json = ""
        if not raw_json:
            raw_json = json.dumps(convert_to_camel(cfg.model_dump()), indent=2)
        notice = ""
        if saved:
            notice = "<div class='notice ok'>Saved. Restart the service to apply changes.</div>"
        elif error:
            notice = f"<div class='notice err'>Error: {_escape(error)}</div>"

        write_note = ""
        if _is_true(write_mode):
            write_note = (
                "<div class='notice warn'>ICRON_WRITE_CONFIG is enabled. "
                "Config will be overwritten on restart. Set it to 0 after the first save.</div>"
            )
        priority_note = (
            "<div class='notice warn'>Provider priority: OpenRouter > Together > Anthropic > OpenAI "
            "> Gemini > Zhipu > vLLM.</div>"
        )

        return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>icron Settings</title>
    <style>
      :root {{ color-scheme: dark; }}
      body {{ margin: 0; font-family: Arial, sans-serif; background: #0a0a0a; color: #ffffff; }}
      header {{ background: linear-gradient(135deg, rgba(34, 211, 208, 0.12), rgba(248, 113, 113, 0.08)); border-bottom: 1px solid rgba(255, 255, 255, 0.1); color: #fff; padding: 24px; }}
      header h1 {{ margin: 0 0 8px 0; font-size: 22px; }}
      header p {{ margin: 0; opacity: 0.8; }}
      main {{ max-width: 900px; margin: 0 auto; padding: 24px; }}
      .card {{ background: #1a1a1a; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 20px; margin-bottom: 16px; }}
      .card h3 {{ color: #ffffff; margin-top: 0; }}
      .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }}
      label {{ display: block; font-weight: 600; margin-bottom: 6px; color: #ffffff; }}
      input[type="text"], input[type="password"] {{
        width: 100%; padding: 10px 12px; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px;
        background: #2a2a2a; color: #ffffff;
      }}
      input[type="text"]::placeholder, input[type="password"]::placeholder {{ color: #9ca3af; }}
      textarea {{
        width: 100%; min-height: 320px; padding: 10px 12px; border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
        "Liberation Mono", "Courier New", monospace; font-size: 12px;
        background: #141414; color: #ffffff;
      }}
      .hint {{ font-size: 12px; color: #9ca3af; margin-top: 6px; }}
      .notice {{ padding: 10px 12px; border-radius: 8px; margin-bottom: 12px; }}
      .notice.ok {{ background: rgba(34, 211, 208, 0.15); border: 1px solid rgba(34, 211, 208, 0.3); color: #22d3d0; }}
      .notice.err {{ background: rgba(248, 113, 113, 0.15); border: 1px solid rgba(248, 113, 113, 0.3); color: #fca5a5; }}
      .notice.warn {{ background: rgba(251, 191, 36, 0.15); border: 1px solid rgba(251, 191, 36, 0.3); color: #fbbf24; }}
      .row {{ display: flex; gap: 12px; align-items: center; }}
      .row input[type="checkbox"] {{ width: 18px; height: 18px; accent-color: #22d3d0; }}
      button {{
        background: linear-gradient(135deg, #22d3d0, #14b8a6); color: #0a0a0a; border: 0; padding: 12px 18px;
        border-radius: 8px; font-weight: 600; cursor: pointer;
      }}
      button:hover {{ opacity: 0.9; }}
      footer {{ font-size: 12px; color: #9ca3af; margin-top: 10px; }}
      code {{ background: #2a2a2a; padding: 2px 6px; border-radius: 6px; color: #22d3d0; }}
    </style>
  </head>
  <body>
    <header>
      <h1>icron Settings</h1>
      <p>Configure API keys, models, and chat channels.</p>
    </header>
    <main>
      {notice}
      {write_note}
      {priority_note}
      <div class="card">
        <form method="post" action="/config">
          <div class="grid">
            <div>
              <label for="model">Model</label>
              <input id="model" name="model" type="text" value="{_escape(cfg.agents.defaults.model)}" />
              <div class="hint">Example: meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo</div>
            </div>
            <div>
              <label for="brave_api_key">Brave Search API Key</label>
              <input id="brave_api_key" name="brave_api_key" type="password" placeholder="{('set' if brave_set else 'not set')}" />
              <div class="hint">Leave blank to keep current value.</div>
            </div>
          </div>

          <div class="card" style="margin-top:16px;">
            <h3>Together AI</h3>
            <div class="grid">
              <div>
                <label for="together_api_key">API Key</label>
                <input id="together_api_key" name="together_api_key" type="password" placeholder="{('set' if together_set else 'not set')}" />
                <div class="hint">Leave blank to keep current value.</div>
              </div>
              <div>
                <label for="together_api_base">API Base (optional)</label>
                <input id="together_api_base" name="together_api_base" type="text" value="{_escape(cfg.providers.together.api_base or '')}" />
                <div class="hint">Default: https://api.together.xyz/v1</div>
              </div>
            </div>
          </div>

          <div class="card">
            <h3>OpenRouter</h3>
            <div class="grid">
              <div>
                <label for="openrouter_api_key">API Key</label>
                <input id="openrouter_api_key" name="openrouter_api_key" type="password" placeholder="{('set' if openrouter_set else 'not set')}" />
                <div class="hint">Leave blank to keep current value.</div>
              </div>
              <div>
                <label for="openrouter_api_base">API Base (optional)</label>
                <input id="openrouter_api_base" name="openrouter_api_base" type="text" value="{_escape(cfg.providers.openrouter.api_base or '')}" />
                <div class="hint">Default: https://openrouter.ai/api/v1</div>
              </div>
            </div>
          </div>

          <div class="card">
            <h3>Telegram</h3>
            <div class="row">
              <input id="telegram_enabled" name="telegram_enabled" type="checkbox" {'checked' if cfg.channels.telegram.enabled else ''} />
              <label for="telegram_enabled">Enable Telegram</label>
            </div>
            <div class="grid" style="margin-top:12px;">
              <div>
                <label for="telegram_token">Bot Token</label>
                <input id="telegram_token" name="telegram_token" type="password" placeholder="{('set' if telegram_set else 'not set')}" />
                <div class="hint">Leave blank to keep current value.</div>
              </div>
              <div>
                <label for="telegram_allow_from">Allowed Users (comma-separated)</label>
                <input id="telegram_allow_from" name="telegram_allow_from" type="text" value="{_escape(allow_from)}" />
              </div>
            </div>
          </div>

          <div class="card">
            <h3>WhatsApp</h3>
            <div class="row">
              <input id="whatsapp_enabled" name="whatsapp_enabled" type="checkbox" {'checked' if cfg.channels.whatsapp.enabled else ''} />
              <label for="whatsapp_enabled">Enable WhatsApp</label>
            </div>
          </div>

          <div class="card">
            <h3>Discord</h3>
            <div class="row">
              <input id="discord_enabled" name="discord_enabled" type="checkbox" {'checked' if cfg.channels.discord.enabled else ''} />
              <label for="discord_enabled">Enable Discord</label>
            </div>
            <div class="fields">
              <div>
                <label for="discord_token">Bot Token</label>
                <input id="discord_token" name="discord_token" type="password" placeholder="{('set' if cfg.channels.discord.token else 'not set')}" />
                <div class="hint">Leave blank to keep current value.</div>
              </div>
              <div>
                <label for="discord_allow_from">Allowed Users (comma-separated user IDs)</label>
                <input id="discord_allow_from" name="discord_allow_from" type="text" value="{_escape(','.join(str(x) for x in cfg.channels.discord.allow_from))}" />
              </div>
              <div>
                <label for="discord_allowed_channels">Allowed Channels (comma-separated channel IDs, empty = all)</label>
                <input id="discord_allowed_channels" name="discord_allowed_channels" type="text" value="{_escape(','.join(str(x) for x in cfg.channels.discord.allowed_channels))}" />
              </div>
            </div>
          </div>

          <button type="submit">Save Settings</button>
          <footer>
            Config path: <code>{_escape(str(cfg_path))}</code>
          </footer>
        </form>
      </div>
      <div class="card">
        <h3>Advanced: Raw Config JSON</h3>
        <form method="post" action="/config/raw">
          <label for="config_json">config.json</label>
          <textarea id="config_json" name="config_json" spellcheck="false">{_escape(raw_json)}</textarea>
          <div class="hint">Edits replace the entire config. Invalid JSON will be rejected.</div>
          <button type="submit">Save Raw Config</button>
        </form>
      </div>
    </main>
  </body>
</html>
"""

    def _maybe_restart() -> None:
        if _is_true(os.getenv("ICRON_RESTART_ON_SAVE", "0")):
            console.print("[yellow]Restarting icron to apply settings...[/yellow]")
            # Exit the process to let Railway (or another supervisor) restart the service.
            import os as _os
            _os._exit(0)

    def _update_config(fields: dict[str, list[str]]) -> None:
        cfg = load_config()

        model = _get_field(fields, "model")
        if model:
            cfg.agents.defaults.model = model

        brave_api_key = _get_field(fields, "brave_api_key")
        if brave_api_key:
            cfg.tools.web.search.api_key = brave_api_key

        together_api_key = _get_field(fields, "together_api_key")
        if together_api_key:
            cfg.providers.together.api_key = together_api_key

        together_api_base = _get_field(fields, "together_api_base")
        cfg.providers.together.api_base = together_api_base or None

        openrouter_api_key = _get_field(fields, "openrouter_api_key")
        if openrouter_api_key:
            cfg.providers.openrouter.api_key = openrouter_api_key

        openrouter_api_base = _get_field(fields, "openrouter_api_base")
        cfg.providers.openrouter.api_base = openrouter_api_base or None

        telegram_enabled = "telegram_enabled" in fields
        cfg.channels.telegram.enabled = telegram_enabled

        telegram_token = _get_field(fields, "telegram_token")
        if telegram_token:
            cfg.channels.telegram.token = telegram_token

        allow_from_raw = _get_field(fields, "telegram_allow_from")
        cfg.channels.telegram.allow_from = [
            item for item in (x.strip() for x in allow_from_raw.split(",")) if item
        ]

        whatsapp_enabled = "whatsapp_enabled" in fields
        cfg.channels.whatsapp.enabled = whatsapp_enabled

        discord_enabled = "discord_enabled" in fields
        cfg.channels.discord.enabled = discord_enabled

        discord_token = _get_field(fields, "discord_token")
        if discord_token:
            cfg.channels.discord.token = discord_token

        discord_allow_from_raw = _get_field(fields, "discord_allow_from")
        cfg.channels.discord.allow_from = [
            item for item in (x.strip() for x in discord_allow_from_raw.split(",")) if item
        ]

        discord_allowed_channels_raw = _get_field(fields, "discord_allowed_channels")
        cfg.channels.discord.allowed_channels = [
            item for item in (x.strip() for x in discord_allowed_channels_raw.split(",")) if item
        ]

        save_config(cfg)
        _maybe_restart()

    def _update_config_raw(raw_json: str) -> None:
        if not raw_json.strip():
            raise ValueError("config_json is empty")
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}") from e
        cfg = Config.model_validate(convert_keys(data))
        save_config(cfg)
        _maybe_restart()

    def _test_provider(data: dict) -> dict:
        """Test provider API credentials by making a simple request."""
        import httpx
        
        provider = data.get("provider", "")
        api_key = data.get("api_key", "")
        api_base = data.get("api_base", "")
        
        if not api_key:
            return {"ok": False, "error": "API key is required"}
        
        # Default API bases for different providers
        default_bases = {
            "openrouter": "https://openrouter.ai/api/v1",
            "together": "https://api.together.xyz/v1",
            "anthropic": "https://api.anthropic.com/v1",
            "openai": "https://api.openai.com/v1",
            "gemini": "https://generativelanguage.googleapis.com/v1beta",
            "groq": "https://api.groq.com/openai/v1",
        }
        
        base_url = api_base or default_bases.get(provider, "")
        if not base_url:
            return {"ok": False, "error": f"Unknown provider: {provider}"}
        
        try:
            if provider == "anthropic":
                # Anthropic uses a different auth header
                response = httpx.get(
                    f"{base_url}/models",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                    },
                    timeout=10,
                )
            elif provider == "gemini":
                # Gemini uses query param for API key
                response = httpx.get(
                    f"{base_url}/models?key={api_key}",
                    timeout=10,
                )
            else:
                # OpenAI-compatible providers
                response = httpx.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10,
                )
            
            if response.status_code in (200, 201):
                return {"ok": True, "message": "Connection successful"}
            elif response.status_code == 401:
                return {"ok": False, "error": "Invalid API key"}
            elif response.status_code == 403:
                return {"ok": False, "error": "API key lacks required permissions"}
            else:
                return {"ok": False, "error": f"HTTP {response.status_code}: {response.text[:200]}"}
        except httpx.TimeoutException:
            return {"ok": False, "error": "Connection timed out"}
        except httpx.ConnectError as e:
            return {"ok": False, "error": f"Connection failed: {str(e)}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _test_channel(data: dict) -> dict:
        """Test channel connection by verifying credentials."""
        import httpx
        
        channel = data.get("channel", "")
        token = data.get("token", "")
        
        if not token:
            return {"ok": False, "error": "Token is required"}
        
        try:
            if channel == "discord":
                # Test Discord bot token
                response = httpx.get(
                    "https://discord.com/api/v10/users/@me",
                    headers={"Authorization": f"Bot {token}"},
                    timeout=10,
                )
                if response.status_code == 200:
                    user_data = response.json()
                    return {"ok": True, "message": f"Connected as {user_data.get('username', 'bot')}"}
                elif response.status_code == 401:
                    return {"ok": False, "error": "Invalid bot token"}
                else:
                    return {"ok": False, "error": f"HTTP {response.status_code}"}
                    
            elif channel == "telegram":
                # Test Telegram bot token
                response = httpx.get(
                    f"https://api.telegram.org/bot{token}/getMe",
                    timeout=10,
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        bot_name = data.get("result", {}).get("username", "bot")
                        return {"ok": True, "message": f"Connected as @{bot_name}"}
                    else:
                        return {"ok": False, "error": data.get("description", "Unknown error")}
                else:
                    return {"ok": False, "error": f"HTTP {response.status_code}"}
                    
            elif channel == "whatsapp":
                # WhatsApp uses bridge URL, just check if it's reachable
                bridge_url = data.get("bridge_url", "")
                if not bridge_url:
                    return {"ok": False, "error": "Bridge URL is required"}
                # Just check the URL is valid format
                return {"ok": True, "message": "Bridge URL configured (connection test requires running bridge)"}
                
            else:
                return {"ok": False, "error": f"Unknown channel: {channel}"}
                
        except httpx.TimeoutException:
            return {"ok": False, "error": "Connection timed out"}
        except httpx.ConnectError as e:
            return {"ok": False, "error": f"Connection failed: {str(e)}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _get_ui_dist() -> Path | None:
        candidates = [
            # Development: relative to source code location
            Path(__file__).resolve().parent.parent / "ui" / "dist",
            Path(__file__).resolve().parent.parent.parent / "ui" / "dist",
            # Docker: fixed app directory
            Path("/app/ui/dist"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    ui_dist = _get_ui_dist()
    ui_root = ui_dist.resolve() if ui_dist else None
    
    # Shared state for runtime status (populated after agent init)
    runtime_state = {
        "mcp": {"initialized": False, "totalTools": 0, "servers": []}
    }

    def start_web_server(host: str, web_port: int) -> ThreadingHTTPServer | None:
        import mimetypes

        class WebHandler(BaseHTTPRequestHandler):
            def _send_bytes(self, body: bytes, content_type: str, status: int = 200) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_text(self, text: str, status: int = 200) -> None:
                self._send_bytes(text.encode("utf-8"), "text/plain; charset=utf-8", status)

            def _send_html(self, html_text: str, status: int = 200) -> None:
                self._send_bytes(html_text.encode("utf-8"), "text/html; charset=utf-8", status)

            def _send_json(self, payload: str, status: int = 200) -> None:
                self._send_bytes(payload.encode("utf-8"), "application/json; charset=utf-8", status)

            def _send_file(self, file_path: Path, status: int = 200) -> None:
                try:
                    body = file_path.read_bytes()
                except Exception:
                    self._send_text("not found", 404)
                    return
                content_type, _ = mimetypes.guess_type(str(file_path))
                self._send_bytes(body, content_type or "application/octet-stream", status)

            def _read_body(self) -> str:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0:
                    return ""
                return self.rfile.read(length).decode("utf-8", errors="ignore")

            def _serve_app(self, path: str) -> bool:
                if not ui_dist or not ui_root:
                    self._send_text("GUI not built. Run: cd ui && npm install && npm run build", 404)
                    return True

                rel = path[len("/app"):].lstrip("/")
                target = (ui_dist / rel) if rel else (ui_dist / "index.html")
                try:
                    resolved = target.resolve()
                except Exception:
                    resolved = target
                if not str(resolved).startswith(str(ui_root)):
                    self._send_text("not found", 404)
                    return True
                if not target.exists() or target.is_dir():
                    target = ui_dist / "index.html"
                self._send_file(target)
                return True

            def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
                path = urlparse(self.path).path
                if path in ("/health", "/healthz", "/ready"):
                    self._send_text("ok", 200)
                    return
                if path == "/api/mcp/status":
                    self._send_json(json.dumps(runtime_state["mcp"]), 200)
                    return
                if path.startswith("/app"):
                    if self._serve_app(path):
                        return
                if path == "/api/config":
                    cfg = load_config()
                    payload = json.dumps(convert_to_camel(cfg.model_dump()), indent=2)
                    self._send_json(payload, 200)
                    return
                if path in ("/", "/ui"):
                    self.send_response(302)
                    self.send_header("Location", "/app")
                    self.end_headers()
                    return
                self._send_text("not found", 404)

            def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
                path = urlparse(self.path).path
                if path == "/api/config":
                    try:
                        body = self._read_body()
                        _update_config_raw(body)
                        self._send_json('{"ok": true}', 200)
                    except Exception as exc:
                        self._send_json(json.dumps({"ok": False, "error": str(exc)}), 400)
                    return
                if path == "/api/test/provider":
                    try:
                        body = self._read_body()
                        data = json.loads(body)
                        result = _test_provider(data)
                        self._send_json(json.dumps(result), 200)
                    except Exception as exc:
                        self._send_json(json.dumps({"ok": False, "error": str(exc)}), 400)
                    return
                if path == "/api/test/channel":
                    try:
                        body = self._read_body()
                        data = json.loads(body)
                        result = _test_channel(data)
                        self._send_json(json.dumps(result), 200)
                    except Exception as exc:
                        self._send_json(json.dumps({"ok": False, "error": str(exc)}), 400)
                    return
                if path in ("/config/raw",):
                    try:
                        body = self._read_body()
                        fields = parse_qs(body, keep_blank_values=True)
                        raw_json = _get_field(fields, "config_json")
                        _update_config_raw(raw_json)
                        self.send_response(303)
                        self.send_header("Location", "/?saved=1")
                        self.end_headers()
                    except Exception as exc:
                        self._send_html(_render_settings_page(error=str(exc)), 400)
                    return
                if path in ("/config", "/"):
                    try:
                        body = self._read_body()
                        fields = parse_qs(body, keep_blank_values=True)
                        _update_config(fields)
                        self.send_response(303)
                        self.send_header("Location", "/?saved=1")
                        self.end_headers()
                    except Exception as exc:
                        self._send_html(_render_settings_page(error=str(exc)), 400)
                    return
                self._send_text("not found", 404)

            def log_message(self, format: str, *args) -> None:  # noqa: A002 - matches base signature
                if os.getenv("ICRON_HTTP_LOG", "") == "1":
                    super().log_message(format, *args)

        class WebServer(ThreadingHTTPServer):
            daemon_threads = True
            allow_reuse_address = True

        try:
            server = WebServer((host, web_port), WebHandler)
        except OSError as exc:
            console.print(
                f"[yellow]Warning: Web server failed to start on {host}:{web_port}: {exc}[/yellow]"
            )
            return None

        thread = Thread(target=server.serve_forever, name="icron-web", daemon=True)
        thread.start()
        console.print(f"[green]✓[/green] Web UI: http://{host}:{web_port}/")
        return server

    http_enabled = os.getenv("ICRON_HTTP_ENABLED", "1").lower() not in {"0", "false", "no", "off"}
    web_server = start_web_server(config.gateway.host, port) if http_enabled else None
    
    # Create components
    bus = MessageBus()
    
    # Create provider using factory
    try:
        provider = create_provider(config)
    except ProviderConfigError as e:
        console.print(f"[yellow]Warning: {e}. Web UI is available for setup.[/yellow]")
        console.print("Set one in ~/.icron/config.json under providers.anthropic.api_key or providers.openrouter.api_key")

        async def run_without_agent():
            try:
                while True:
                    await asyncio.sleep(3600)
            except KeyboardInterrupt:
                console.print("\nShutting down...")
            finally:
                if web_server:
                    web_server.shutdown()
                    web_server.server_close()

        asyncio.run(run_without_agent())
        return
    
    # Create cron service first (callback set after agent creation)
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path)
    
    # Create agent with MCP support
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        max_iterations=config.agents.defaults.max_tool_iterations,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        mcp_servers=config.get_mcp_servers(),
        cron_service=cron,
        config=config,
    )
    
    # Set cron callback (needs agent)
    async def on_cron_job(job: CronJob) -> str | None:
        """Execute a cron job - handles both agent turns and system events."""
        from icron.bus.events import OutboundMessage
        
        # System events (reminders) deliver the message directly without agent processing
        if job.payload.kind == "system_event":
            if job.payload.deliver and job.payload.to:
                await bus.publish_outbound(OutboundMessage(
                    channel=job.payload.channel or "discord",
                    chat_id=job.payload.to,
                    content=job.payload.message
                ))
            return job.payload.message
        
        # Agent turns process through the agent
        response = await agent.process_direct(
            job.payload.message,
            session_key=f"cron:{job.id}",
        )
        # Optionally deliver response to channel
        if job.payload.deliver and job.payload.to:
            await bus.publish_outbound(OutboundMessage(
                channel=job.payload.channel or "discord",
                chat_id=job.payload.to,
                content=response or ""
            ))
        return response
    cron.on_job = on_cron_job
    
    # Create heartbeat service
    async def on_heartbeat(prompt: str) -> str:
        """Execute heartbeat through the agent."""
        return await agent.process_direct(prompt, session_key="heartbeat")
    
    heartbeat = HeartbeatService(
        workspace=config.workspace_path,
        on_heartbeat=on_heartbeat,
        interval_s=30 * 60,  # 30 minutes
        enabled=True
    )
    
    # Create channel manager
    channels = ChannelManager(config, bus)
    
    if channels.enabled_channels:
        console.print(f"[green]✓[/green] Channels enabled: {', '.join(channels.enabled_channels)}")
    else:
        console.print("[yellow]Warning: No channels enabled[/yellow]")
    
    cron_status = cron.status()
    if cron_status["jobs"] > 0:
        console.print(f"[green]✓[/green] Cron: {cron_status['jobs']} scheduled jobs")
    
    console.print(f"[green]✓[/green] Heartbeat: every 30m")
    
    # Display MCP status
    if config.tools.mcp.enabled:
        mcp_count = len(config.tools.mcp.servers)
        console.print(f"[green]✓[/green] MCP: {mcp_count} servers configured")
    
    async def run():
        try:
            # Initialize agent (including MCP)
            await agent.initialize()
            
            # Update runtime state with MCP status
            if agent.mcp_manager:
                runtime_state["mcp"] = agent.mcp_manager.get_status()
            
            await cron.start()
            await heartbeat.start()
            await asyncio.gather(
                agent.run(),
                channels.start_all(),
            )
        except KeyboardInterrupt:
            console.print("\nShutting down...")
            heartbeat.stop()
            cron.stop()
            agent.stop()
            await channels.stop_all()
            await agent.shutdown()
        finally:
            if web_server:
                web_server.shutdown()
                web_server.server_close()
    
    asyncio.run(run())




# ============================================================================
# Agent Commands
# ============================================================================


@app.command()
def agent(
    message: str = typer.Option(None, "--message", "-m", help="Message to send to the agent"),
    session_id: str = typer.Option("cli:default", "--session", "-s", help="Session ID"),
):
    """Interact with the agent directly."""
    from icron.config.loader import load_config
    from icron.bus.queue import MessageBus
    from icron.providers.factory import create_provider, ProviderConfigError
    from icron.agent.loop import AgentLoop
    
    config = load_config()
    
    bus = MessageBus()
    try:
        provider = create_provider(config)
    except ProviderConfigError as e:
        console.print(f"[red]Provider configuration error: {e}[/red]")
        console.print("Set your API key in [cyan]~/.icron/config.json[/cyan]")
        raise typer.Exit(1)
    
    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        mcp_servers=config.get_mcp_servers(),
        config=config,
    )
    
    if message:
        # Single message mode
        async def run_once():
            await agent_loop.initialize()
            try:
                response = await agent_loop.process_direct(message, session_id)
                console.print(f"\n{__logo__} {response}")
            finally:
                await agent_loop.shutdown()
        
        asyncio.run(run_once())
    else:
        # Interactive mode
        console.print(f"{__logo__} Interactive mode (Ctrl+C to exit)\n")
        
        async def run_interactive():
            await agent_loop.initialize()
            try:
                while True:
                    try:
                        user_input = console.input("[bold blue]You:[/bold blue] ")
                        if not user_input.strip():
                            continue
                        
                        response = await agent_loop.process_direct(user_input, session_id)
                        console.print(f"\n{__logo__} {response}\n")
                    except KeyboardInterrupt:
                        console.print("\nGoodbye!")
                        break
            finally:
                await agent_loop.shutdown()
        
        asyncio.run(run_interactive())


# ============================================================================
# Channel Commands
# ============================================================================


channels_app = typer.Typer(help="Manage channels")
app.add_typer(channels_app, name="channels")


@channels_app.command("status")
def channels_status():
    """Show channel status."""
    from icron.config.loader import load_config

    config = load_config()

    table = Table(title="Channel Status")
    table.add_column("Channel", style="cyan")
    table.add_column("Enabled", style="green")
    table.add_column("Configuration", style="yellow")

    # WhatsApp
    wa = config.channels.whatsapp
    table.add_row(
        "WhatsApp",
        "✓" if wa.enabled else "✗",
        wa.bridge_url
    )

    # Telegram
    tg = config.channels.telegram
    tg_config = f"token: {tg.token[:10]}..." if tg.token else "[dim]not configured[/dim]"
    table.add_row(
        "Telegram",
        "✓" if tg.enabled else "✗",
        tg_config
    )

    # Slack
    slack = config.channels.slack
    slack_config = "socket" if slack.app_token and slack.bot_token else "[dim]not configured[/dim]"
    table.add_row(
        "Slack",
        "✓" if slack.enabled else "✗",
        slack_config
    )

    console.print(table)


def _get_bridge_dir() -> Path:
    """Get the bridge directory, setting it up if needed."""
    import shutil
    import subprocess
    
    # User's bridge location
    user_bridge = Path.home() / ".icron" / "bridge"
    
    # Check if already built
    if (user_bridge / "dist" / "index.js").exists():
        return user_bridge
    
    # Check for npm
    if not shutil.which("npm"):
        console.print("[red]npm not found. Please install Node.js >= 18.[/red]")
        raise typer.Exit(1)
    
    # Find source bridge: first check package data, then source dir
    pkg_bridge = Path(__file__).parent.parent / "bridge"  # icron/bridge (installed)
    src_bridge = Path(__file__).parent.parent.parent / "bridge"  # repo root/bridge (dev)
    
    source = None
    if (pkg_bridge / "package.json").exists():
        source = pkg_bridge
    elif (src_bridge / "package.json").exists():
        source = src_bridge
    
    if not source:
        console.print("[red]Bridge source not found.[/red]")
        console.print("Try reinstalling: pip install --force-reinstall icron")
        raise typer.Exit(1)
    
    console.print(f"{__logo__} Setting up bridge...")
    
    # Copy to user directory
    user_bridge.parent.mkdir(parents=True, exist_ok=True)
    if user_bridge.exists():
        shutil.rmtree(user_bridge)
    shutil.copytree(source, user_bridge, ignore=shutil.ignore_patterns("node_modules", "dist"))
    
    # Install and build
    try:
        console.print("  Installing dependencies...")
        subprocess.run(["npm", "install"], cwd=user_bridge, check=True, capture_output=True)
        
        console.print("  Building...")
        subprocess.run(["npm", "run", "build"], cwd=user_bridge, check=True, capture_output=True)
        
        console.print("[green]✓[/green] Bridge ready\n")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Build failed: {e}[/red]")
        if e.stderr:
            console.print(f"[dim]{e.stderr.decode()[:500]}[/dim]")
        raise typer.Exit(1)
    
    return user_bridge


@channels_app.command("login")
def channels_login():
    """Link device via QR code."""
    import subprocess
    
    bridge_dir = _get_bridge_dir()
    
    console.print(f"{__logo__} Starting bridge...")
    console.print("Scan the QR code to connect.\n")
    
    try:
        subprocess.run(["npm", "start"], cwd=bridge_dir, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Bridge failed: {e}[/red]")
    except FileNotFoundError:
        console.print("[red]npm not found. Please install Node.js.[/red]")


# ============================================================================
# Cron Commands
# ============================================================================

cron_app = typer.Typer(help="Manage scheduled tasks")
app.add_typer(cron_app, name="cron")


@cron_app.command("list")
def cron_list(
    all: bool = typer.Option(False, "--all", "-a", help="Include disabled jobs"),
):
    """List scheduled jobs."""
    from icron.config.loader import get_data_dir
    from icron.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    jobs = service.list_jobs(include_disabled=all)
    
    if not jobs:
        console.print("No scheduled jobs.")
        return
    
    table = Table(title="Scheduled Jobs")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Schedule")
    table.add_column("Status")
    table.add_column("Next Run")
    
    import time
    for job in jobs:
        # Format schedule
        if job.schedule.kind == "every":
            sched = f"every {(job.schedule.every_ms or 0) // 1000}s"
        elif job.schedule.kind == "cron":
            sched = job.schedule.expr or ""
        else:
            sched = "one-time"
        
        # Format next run
        next_run = ""
        if job.state.next_run_at_ms:
            next_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(job.state.next_run_at_ms / 1000))
            next_run = next_time
        
        status = "[green]enabled[/green]" if job.enabled else "[dim]disabled[/dim]"
        
        table.add_row(job.id, job.name, sched, status, next_run)
    
    console.print(table)


@cron_app.command("add")
def cron_add(
    name: str = typer.Option(..., "--name", "-n", help="Job name"),
    message: str = typer.Option(..., "--message", "-m", help="Message for agent"),
    every: int = typer.Option(None, "--every", "-e", help="Run every N seconds"),
    cron_expr: str = typer.Option(None, "--cron", "-c", help="Cron expression (e.g. '0 9 * * *')"),
    at: str = typer.Option(None, "--at", help="Run once at time (ISO format)"),
    deliver: bool = typer.Option(False, "--deliver", "-d", help="Deliver response to channel"),
    to: str = typer.Option(None, "--to", help="Recipient for delivery"),
    channel: str = typer.Option(None, "--channel", help="Channel for delivery (e.g. 'telegram', 'whatsapp')"),
):
    """Add a scheduled job."""
    from icron.config.loader import get_data_dir
    from icron.cron.service import CronService
    from icron.cron.types import CronSchedule
    
    # Determine schedule type
    if every:
        schedule = CronSchedule(kind="every", every_ms=every * 1000)
    elif cron_expr:
        schedule = CronSchedule(kind="cron", expr=cron_expr)
    elif at:
        import datetime
        dt = datetime.datetime.fromisoformat(at)
        schedule = CronSchedule(kind="at", at_ms=int(dt.timestamp() * 1000))
    else:
        console.print("[red]Error: Must specify --every, --cron, or --at[/red]")
        raise typer.Exit(1)
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    job = service.add_job(
        name=name,
        schedule=schedule,
        message=message,
        deliver=deliver,
        to=to,
        channel=channel,
    )
    
    console.print(f"[green]✓[/green] Added job '{job.name}' ({job.id})")


@cron_app.command("remove")
def cron_remove(
    job_id: str = typer.Argument(..., help="Job ID to remove"),
):
    """Remove a scheduled job."""
    from icron.config.loader import get_data_dir
    from icron.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    if service.remove_job(job_id):
        console.print(f"[green]✓[/green] Removed job {job_id}")
    else:
        console.print(f"[red]Job {job_id} not found[/red]")


@cron_app.command("enable")
def cron_enable(
    job_id: str = typer.Argument(..., help="Job ID"),
    disable: bool = typer.Option(False, "--disable", help="Disable instead of enable"),
):
    """Enable or disable a job."""
    from icron.config.loader import get_data_dir
    from icron.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    job = service.enable_job(job_id, enabled=not disable)
    if job:
        status = "disabled" if disable else "enabled"
        console.print(f"[green]✓[/green] Job '{job.name}' {status}")
    else:
        console.print(f"[red]Job {job_id} not found[/red]")


@cron_app.command("run")
def cron_run(
    job_id: str = typer.Argument(..., help="Job ID to run"),
    force: bool = typer.Option(False, "--force", "-f", help="Run even if disabled"),
):
    """Manually run a job."""
    from icron.config.loader import get_data_dir
    from icron.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    async def run():
        return await service.run_job(job_id, force=force)
    
    if asyncio.run(run()):
        console.print(f"[green]✓[/green] Job executed")
    else:
        console.print(f"[red]Failed to run job {job_id}[/red]")


# ============================================================================
# Status Commands
# ============================================================================


@app.command()
def status():
    """Show icron status."""
    from icron.config.loader import load_config, get_config_path

    config_path = get_config_path()
    config = load_config()
    workspace = config.workspace_path

    console.print(f"{__logo__} icron Status\n")

    console.print(f"Config: {config_path} {'[green]✓[/green]' if config_path.exists() else '[red]✗[/red]'}")
    console.print(f"Workspace: {workspace} {'[green]✓[/green]' if workspace.exists() else '[red]✗[/red]'}")

    if config_path.exists():
        console.print(f"Model: {config.agents.defaults.model}")
        
        # Check API keys
        has_openrouter = bool(config.providers.openrouter.api_key)
        has_anthropic = bool(config.providers.anthropic.api_key)
        has_openai = bool(config.providers.openai.api_key)
        has_gemini = bool(config.providers.gemini.api_key)
        has_vllm = bool(config.providers.vllm.api_base)
        
        console.print(f"OpenRouter API: {'[green]✓[/green]' if has_openrouter else '[dim]not set[/dim]'}")
        console.print(f"Anthropic API: {'[green]✓[/green]' if has_anthropic else '[dim]not set[/dim]'}")
        console.print(f"OpenAI API: {'[green]✓[/green]' if has_openai else '[dim]not set[/dim]'}")
        console.print(f"Gemini API: {'[green]✓[/green]' if has_gemini else '[dim]not set[/dim]'}")
        vllm_status = f"[green]✓ {config.providers.vllm.api_base}[/green]" if has_vllm else "[dim]not set[/dim]"
        console.print(f"vLLM/Local: {vllm_status}")
        
        # MCP Status
        if config.tools.mcp.enabled:
            mcp_count = len(config.tools.mcp.servers)
            console.print(f"MCP: [green]✓ enabled ({mcp_count} servers)[/green]")
            for name in config.tools.mcp.servers:
                console.print(f"  - {name}")
        else:
            console.print("MCP: [dim]disabled[/dim]")


if __name__ == "__main__":
    app()
