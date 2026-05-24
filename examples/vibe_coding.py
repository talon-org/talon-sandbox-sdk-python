"""Vibe coding: create sandbox, spawn dev server, expose port, print URL."""
import asyncio

from talon_sandbox import Sandbox


async def main() -> None:
    sb = await Sandbox.create(
        image="node:20-bookworm",
        resources={"cpu": 2, "memory": "4GiB"},
        env={"NODE_ENV": "development"},
        ttl="6h",
    )

    # Write a minimal HTTP server
    await sb.fs.write_text(
        "/workspace/server.js",
        """\
const http = require('http');
http.createServer((_, res) => res.end('Hello from sandbox!')).listen(5173);
console.log('Listening on 5173');
""",
    )

    # Spawn the server (long-running)
    proc = await sb.spawn("node /workspace/server.js")
    proc.on("stdout", lambda line: print(f"[server] {line}"))

    # Give it a moment to start
    await asyncio.sleep(1)

    # Expose port 5173
    url = await sb.expose(5173)
    print(f"Preview URL: {url}")

    # Wait for the process
    await proc.wait()
    await sb.kill()


if __name__ == "__main__":
    asyncio.run(main())
