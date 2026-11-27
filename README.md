# APEX – Automated Personal Executive System

> **A local-first, MCP-powered AI executive platform for orchestrating intelligent agents across your tools, apps, and workflows.**

---

## What is APEX?

APEX is a modular AI assistant backend that acts as an executive layer between you and your digital environment. It runs locally on your machine, keeps your data private, and connects to any tool or service through the open **Model Context Protocol (MCP)** standard.

APEX is an autonomous operator — it decomposes high-level objectives, delegates tasks to specialised sub-agents, manages execution sandboxes, and synthesises results into coherent outputs.

---

## Key Features

- **MCP-Native** — Acts as both an MCP Host and Orchestrator; any MCP-compatible tool server plugs in instantly.
- **Local-First** — Runs fully on your machine; no cloud dependency required.
- **Multi-Model Routing** — Dynamically selects the best model (local or cloud) for each sub-task.
- **Secure Sandboxing** — Code execution, shell commands, and file operations run in permission-gated environments.
- **Composable Agents** — Modular agent architecture; add specialised agents without touching the core.
- **Persistent Memory** — Cross-session context retention via FAISS, BM25, and ColBERT backends.
- **Multi-Channel** — Telegram, Discord, Slack, Gmail, Twitter, WhatsApp, and more.
- **Evaluations** — Built-in evaluation harness for benchmarking agent and model performance.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  APEX Frontend                  │
│        (React + Vite + Tailwind CSS)            │
└───────────────────┬─────────────────────────────┘
                    │ HTTP / WebSocket
┌───────────────────▼─────────────────────────────┐
│              APEX Core Engine                   │
│  ┌────────────┐  ┌──────────┐  ┌─────────────┐ │
│  │  Agents    │  │ Memory   │  │  Scheduler  │ │
│  │  Engine    │  │ Manager  │  │  & Daemon   │ │
│  └────────────┘  └──────────┘  └─────────────┘ │
│  ┌────────────────────────────────────────────┐ │
│  │         MCP Orchestration Layer             │ │
│  │  (context propagation, tool discovery,     │ │
│  │   auth, lifecycle management)              │ │
│  └────────────────────────────────────────────┘ │
└───────────────────┬─────────────────────────────┘
                    │ MCP Protocol
┌───────────────────▼─────────────────────────────┐
│              MCP Tool Servers                   │
│  SQLite │ Git │ Browser │ Gmail │ Custom ...    │
└─────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.11–3.13
- [uv](https://docs.astral.sh/uv/) package manager

### Installation

```bash
# Clone the repository
git clone https://github.com/apex-ai/apex.git
cd apex

# Install dependencies and create virtual environment
uv sync

# Launch the APEX GUI
uv run apex gui
```

### First Run

```bash
# Initialise APEX with your config
uv run apex init

# Start the backend server
uv run apex serve

# Or launch the full desktop UI
uv run apex gui
```

---

## Configuration

APEX is configured via `~/.apex/config.toml`. On first run, `apex init` generates a starter config.

```toml
[model]
provider = "openai"        # openai | anthropic | local | litellm
model    = "gpt-4o"

[server]
host = "127.0.0.1"
port = 8000

[memory]
backend = "faiss"          # faiss | bm25 | colbert
```

Pre-built preset configs are available under `configs/apex/examples/`.

---

## MCP Integration

APEX natively implements the [Model Context Protocol](https://modelcontextprotocol.io). To connect an MCP server:

```toml
[[mcp.servers]]
name    = "filesystem"
command = "npx"
args    = ["-y", "@modelcontextprotocol/server-filesystem", "/your/path"]
```

APEX will auto-discover, authenticate, and expose the server's tools to all agents at runtime.

---

## Available Commands

| Command | Description |
|---------|-------------|
| `apex gui` | Launch the full desktop GUI |
| `apex serve` | Start the backend API server |
| `apex init` | Initialise config and workspace |
| `apex chat` | Interactive chat in the terminal |
| `apex run <preset>` | Execute a preset workflow |
| `apex eval` | Run evaluation benchmarks |
| `apex mine` | Start the local model mining daemon |

---

## Project Structure

```
apex/
├── src/apex/          # Core Python package
│   ├── agents/        # Agent implementations
│   ├── cli/           # CLI commands
│   ├── engine/        # Model routing & execution
│   ├── mcp/           # MCP host & orchestration
│   ├── memory/        # Persistent memory backends
│   ├── server/        # FastAPI backend
│   ├── scheduler/     # Task scheduling & daemon
│   └── tools/         # Built-in tool implementations
├── frontend/          # React/Vite UI
├── rust/              # Native Rust acceleration crates
├── configs/           # Default & example configurations
├── docs/              # Full documentation
├── examples/          # Example workflows & integrations
└── tests/             # Test suite
```

---

## Development

```bash
# Install dev dependencies
uv sync --extra dev

# Run tests
uv run pytest tests/

# Run linter
uv run ruff check src/

# Format code
uv run ruff format src/
```

---

## License

APEX is released under the [Apache 2.0 License](LICENSE).

---

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
