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
    image="talon-alpine",
    resources={"cpu": 2, "memory": "4GiB"},
    network="allowlist",
    timeout="30m",
) as sb:
    result = await sb.run("node --version")
    print(result.stdout)

# Sync (no await needed)
sb = Sandbox.create(image="talon-alpine")
print(sb.id)
```

## Configuration

SDK 默认连接官方托管端点 `https://api.sandbox.talon.net.cn`，只需配置 API key 即可：

```bash
export TALON_SANDBOX_API_KEY=ask_...
```

Or programmatically:

```python
from talon_sandbox import configure
configure(api_key="ask_...")
```

自部署用户可通过环境变量或显式参数覆盖端点（优先级：env > 显式参数 > `configure()` 全局 > 默认）：

```bash
export TALON_SANDBOX_SERVER=http://localhost:18080
export TALON_SANDBOX_API_KEY=ask_...
```

## License

Proprietary. Copyright (c) 2026 Talon Sandbox. All rights reserved.
