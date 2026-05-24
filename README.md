# talon-sandbox

Python SDK v2 for Talon Sandbox — run code in isolated environments.

## Install

```bash
pip install talon-sandbox
```

## Quick start

```python
from talon_sandbox import Sandbox

# Async
async with await Sandbox.create(
    image="node:20-bookworm",
    resources={"cpu": 2, "memory": "4GiB"},
    network="allowlist",
    timeout="30m",
) as sb:
    result = await sb.run("node --version")
    print(result.stdout)

# Sync (no await needed)
sb = Sandbox.create(image="node:20-bookworm")
print(sb.id)
```

## Configuration

```bash
export TALON_SANDBOX_SERVER=https://api.example.com
export TALON_SANDBOX_API_KEY=ask_...
```

Or programmatically:

```python
from talon_sandbox import configure
configure(server="https://api.example.com", api_key="ask_...")
```

## License

Proprietary. Copyright (c) 2026 Talon Sandbox. All rights reserved.
