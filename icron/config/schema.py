"""Configuration schema using Pydantic."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class WhatsAppConfig(BaseModel):
    """WhatsApp channel configuration."""
    enabled: bool = False
    bridge_url: str = "ws://localhost:3001"
    allow_from: list[str] = Field(default_factory=list)  # Allowed phone numbers


class TelegramConfig(BaseModel):
    """Telegram channel configuration."""
    enabled: bool = False
    token: str = ""  # Bot token from @BotFather
    allow_from: list[str] = Field(default_factory=list)  # Allowed user IDs or usernames


class SlackDMConfig(BaseModel):
    """Slack DM policy configuration."""
    enabled: bool = True
    policy: str = "open"  # "open" or "allowlist"
    allow_from: list[str] = Field(default_factory=list)  # Allowed Slack user IDs


class SlackConfig(BaseModel):
    """Slack channel configuration."""
    enabled: bool = False
    mode: str = "socket"  # "socket" supported
    webhook_path: str = "/slack/events"
    bot_token: str = ""  # xoxb-...
    app_token: str = ""  # xapp-...
    user_token_read_only: bool = True
    group_policy: str = "open"  # "open", "mention", "allowlist"
    group_allow_from: list[str] = Field(default_factory=list)  # Allowed channel IDs if allowlist
    dm: SlackDMConfig = SlackDMConfig()


class DiscordConfig(BaseModel):
    """Discord channel configuration."""
    enabled: bool = False
    token: str = ""  # Discord bot token
    allow_from: list[str] = Field(default_factory=list)  # Allowed user IDs (strings to preserve precision)
    allowed_channels: list[str] = Field(default_factory=list)  # Allowed channel IDs (strings to preserve precision)


class FeishuConfig(BaseModel):
    """Feishu (Lark) channel configuration."""
    enabled: bool = False
    app_id: str = ""
    app_secret: str = ""
    verification_token: str = ""
    encrypt_key: str = ""


class ChannelsConfig(BaseModel):
    """Configuration for chat channels."""
    whatsapp: WhatsAppConfig = WhatsAppConfig()
    telegram: TelegramConfig = TelegramConfig()
    slack: SlackConfig = SlackConfig()
    discord: DiscordConfig = DiscordConfig()
    feishu: FeishuConfig = FeishuConfig()


class AgentDefaults(BaseModel):
    """Default agent configuration."""
    workspace: str = "~/.icron/workspace"
    model: str = "anthropic/claude-opus-4-5"
    max_tokens: int = 8192
    temperature: float = 0.7
    max_tool_iterations: int = 20


class AgentsConfig(BaseModel):
    """Agent configuration."""
    defaults: AgentDefaults = AgentDefaults()


class ProviderConfig(BaseModel):
    """LLM provider configuration."""
    api_key: str = ""
    api_base: str | None = None
    model: str | None = None


class ProvidersConfig(BaseModel):
    """Configuration for LLM providers."""
    anthropic: ProviderConfig = ProviderConfig()
    openai: ProviderConfig = ProviderConfig()
    openrouter: ProviderConfig = ProviderConfig()
    together: ProviderConfig = ProviderConfig()
    groq: ProviderConfig = ProviderConfig()
    zhipu: ProviderConfig = ProviderConfig()
    vllm: ProviderConfig = ProviderConfig()
    gemini: ProviderConfig = ProviderConfig()


class GatewayConfig(BaseModel):
    """Gateway/server configuration."""
    host: str = "127.0.0.1"  # Default to localhost for security
    port: int = 3883


class WebSearchConfig(BaseModel):
    """Web search tool configuration."""
    api_key: str = ""  # Brave Search API key
    max_results: int = 5


class WebToolsConfig(BaseModel):
    """Web tools configuration."""
    search: WebSearchConfig = WebSearchConfig()


class ExecToolConfig(BaseModel):
    """Shell exec tool configuration."""
    timeout: int = 60
    restrict_to_workspace: bool = True  # Block commands accessing paths outside workspace
    max_context_tokens: int = 100000  # Max tokens for conversation history sent to LLM


class MCPServerConfig(BaseModel):
    """
    MCP server configuration.

    Supports both stdio (local) and sse (remote) transports.

    Stdio example:
        {
            "command": "python",
            "args": ["/path/to/server.py"],
            "env": {"KEY": "value"}
        }

    SSE example:
        {
            "transport": "sse",
            "url": "https://mcp.example.com/server",
            "headers": {"Authorization": "Bearer token"}
        }
    """
    # Transport type: "stdio" (default) or "sse"
    transport: str = "stdio"

    # Stdio transport options
    command: str = "python"
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)

    # SSE transport options
    url: str = ""  # Required for SSE transport
    headers: dict[str, str] = Field(default_factory=dict)


class MCPConfig(BaseModel):
    """MCP (Model Context Protocol) configuration."""
    enabled: bool = False
    servers: dict[str, MCPServerConfig] = {}


class ToolsConfig(BaseModel):
    """Tools configuration."""
    web: WebToolsConfig = WebToolsConfig()
    exec: ExecToolConfig = ExecToolConfig()
    mcp: MCPConfig = MCPConfig()


class MemorySearchConfig(BaseModel):
    """Configuration for memory search."""
    hybrid_enabled: bool = True
    vector_weight: float = 0.7
    max_results: int = 10


class MemoryConfig(BaseModel):
    """Configuration for semantic memory system."""
    enabled: bool = True
    embedding_provider: str = "auto"  # auto, openai, gemini, ollama, local
    embedding_model: str | None = None  # Override default model
    search: MemorySearchConfig = MemorySearchConfig()


class Config(BaseSettings):
    """Root configuration for icron."""
    agents: AgentsConfig = AgentsConfig()
    channels: ChannelsConfig = ChannelsConfig()
    providers: ProvidersConfig = ProvidersConfig()
    gateway: GatewayConfig = GatewayConfig()
    tools: ToolsConfig = ToolsConfig()
    memory: MemoryConfig = MemoryConfig()
    
    @property
    def workspace_path(self) -> Path:
        """Get expanded workspace path."""
        return Path(self.agents.defaults.workspace).expanduser()
    
    def get_api_key(self) -> str | None:
        """Get API key in priority order: OpenRouter > Anthropic > OpenAI > Gemini > Zhipu > Groq > vLLM."""
        return (
            self.providers.openrouter.api_key or
            self.providers.anthropic.api_key or
            self.providers.openai.api_key or
            self.providers.gemini.api_key or
            self.providers.zhipu.api_key or
            self.providers.groq.api_key or
            self.providers.vllm.api_key or
            None
        )
    
    def get_api_base(self) -> str | None:
        """Get API base URL if using OpenRouter, Zhipu or vLLM."""
        if self.providers.openrouter.api_key:
            return self.providers.openrouter.api_base or "https://openrouter.ai/api/v1"
        if self.providers.zhipu.api_key:
            return self.providers.zhipu.api_base
        if self.providers.vllm.api_base:
            return self.providers.vllm.api_base
        return None

    def get_mcp_servers(self) -> dict[str, dict[str, Any]]:
        """Get MCP servers configuration."""
        if not self.tools.mcp.enabled:
            return {}

        result = {}
        for name, server in self.tools.mcp.servers.items():
            cfg: dict[str, Any] = {"transport": server.transport}

            if server.transport == "sse":
                cfg["url"] = server.url
                if server.headers:
                    cfg["headers"] = server.headers
            else:
                cfg["command"] = server.command
                cfg["args"] = server.args
                if server.env:
                    cfg["env"] = server.env

            result[name] = cfg
        return result

    class Config:
        env_prefix = "ICRON_"
        env_nested_delimiter = "__"
