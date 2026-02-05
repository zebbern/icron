#!/usr/bin/env bash
set -euo pipefail

# Optional install (useful on platforms that mount source but skip image builds).
if [[ "${NANOBOT_SKIP_INSTALL:-}" != "1" ]]; then
  install_needed=0
  if [[ "${NANOBOT_FORCE_INSTALL:-}" == "1" ]]; then
    install_needed=1
  elif ! python -m pip show nanobot-ai >/dev/null 2>&1; then
    install_needed=1
  fi

  if [[ "$install_needed" == "1" ]]; then
    python -m pip install --upgrade pip
    python -m pip install -e .
  fi
fi

# Prepare config/workspace directories
# Prefer Railway volume at /Nano if present and envs not set.
if [[ -d "/Nano" ]]; then
  export NANOBOT_DATA_DIR="${NANOBOT_DATA_DIR:-/Nano/.nanobot}"
  export NANOBOT_WORKSPACE="${NANOBOT_WORKSPACE:-/Nano/workspace}"
fi

CONFIG_DIR="${NANOBOT_DATA_DIR:-$HOME/.nanobot}"
WORKSPACE_DIR="${NANOBOT_WORKSPACE:-$HOME/.nanobot/workspace}"
CONFIG_FILE="${CONFIG_DIR}/config.json"
mkdir -p "$CONFIG_DIR"
mkdir -p "$WORKSPACE_DIR"

# Setup memory persistence for Railway volume at /Nano
# If workspace is not under /Nano, symlink memory to /Nano/memory.
if [[ -d "/Nano" ]]; then
  echo "Setting up Railway persistent memory at /Nano..."
  mkdir -p /Nano/memory
  if [[ "$WORKSPACE_DIR" != /Nano/* ]]; then
    rm -rf "$WORKSPACE_DIR/memory"
    ln -s /Nano/memory "$WORKSPACE_DIR/memory"
    echo "OK Memory persistence configured: $WORKSPACE_DIR/memory -> /Nano/memory"
  else
    mkdir -p "$WORKSPACE_DIR/memory"
    echo "OK Memory persistence configured: $WORKSPACE_DIR/memory"
  fi
fi

# Create config.json from environment variables (basic example).
# Set these env vars in Railway: TOGETHER_API_KEY (or TOGETHERAI_API_KEY), OPENROUTER_API_KEY, TELEGRAM_TOKEN, TELEGRAM_ALLOW_FROM (comma-separated), MODEL
WRITE_CONFIG="${NANOBOT_WRITE_CONFIG:-auto}"
should_write=0
if [[ "$WRITE_CONFIG" == "1" || "$WRITE_CONFIG" == "true" || "$WRITE_CONFIG" == "yes" ]]; then
  should_write=1
elif [[ "$WRITE_CONFIG" == "auto" && ! -f "$CONFIG_FILE" ]]; then
  should_write=1
fi

if [[ "$should_write" == "1" ]]; then
  ALLOW_FROM_JSON=$(python - <<'PY'
import json
import os

raw = os.getenv("TELEGRAM_ALLOW_FROM", "")
items = [item.strip() for item in raw.split(",") if item.strip()]
print(json.dumps(items))
PY
)
  TOGETHER_KEY="${TOGETHER_API_KEY:-${TOGETHERAI_API_KEY:-}}"
  TOGETHER_BASE="${TOGETHER_API_BASE:-}"
  cat > "$CONFIG_FILE" <<EOF
{
  "litellmSettings": {
    "allowedOpenAIParams": ["tools", "tool_choice"],
    "dropParams": false
  },
  "providers": {
    "openrouter": {
      "apiKey": "${OPENROUTER_API_KEY:-}"
    },
    "together": {
      "apiKey": "${TOGETHER_KEY}",
      "apiBase": "${TOGETHER_BASE}"
    }
  },
  "agents": {
    "defaults": {
      "model": "${MODEL:-moonshotai/Kimi-K2.5}",
      "workspace": "${WORKSPACE_DIR}"
    }
  },
  "channels": {
    "telegram": {
      "enabled": ${TELEGRAM_ENABLED:-true},
      "token": "${TELEGRAM_TOKEN:-}",
      "allowFrom": ${ALLOW_FROM_JSON}
    },
    "whatsapp": {
      "enabled": ${WHATSAPP_ENABLED:-false}
    }
  },
  "tools": {
    "web": {
      "search": {
        "apiKey": "${WEBSEARCH_API_KEY:-}"
      }
    }
  }
}
EOF
  echo "wrote config to $CONFIG_FILE"
elif [[ -f "$CONFIG_FILE" ]]; then
  echo "using existing config at $CONFIG_FILE"
else
  echo "no config found at $CONFIG_FILE"
fi

if [[ "${NANOBOT_PRINT_CONFIG:-}" == "1" && -f "$CONFIG_FILE" ]]; then
  ls -l "$CONFIG_FILE"
  cat "$CONFIG_FILE"
fi

# Run the CLI entrypoint you want. Options:
# - For persistent gateway (connects to chat channels): nanobot gateway
# - For interactive/testing agent single run: nanobot agent -m "Hello"
# Start as gateway by default for background bot:
GATEWAY_ARGS=()
if [[ -n "${NANOBOT_PORT:-}" ]]; then
  GATEWAY_ARGS+=(--port "${NANOBOT_PORT}")
elif [[ -n "${PORT:-}" ]]; then
  GATEWAY_ARGS+=(--port "${PORT}")
fi
if [[ "${NANOBOT_VERBOSE:-}" == "1" ]]; then
  GATEWAY_ARGS+=(--verbose)
fi

exec python -m nanobot gateway "${GATEWAY_ARGS[@]}"