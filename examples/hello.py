"""Hello world example — create a sandbox, run a command, kill it."""
import asyncio

from talon_sandbox import Sandbox


async def main() -> None:
    async with await Sandbox.create(
        image="talon-alpine",
        resources={"cpu": 1, "memory": "2GiB"},
        network="allowlist",
        timeout="10m",
    ) as sb:
        print(f"Sandbox {sb.id} is {sb.state}")
        result = await sb.run("node --version")
        print(f"Node: {result.stdout.strip()}")
        assert result.exit_code == 0


if __name__ == "__main__":
    asyncio.run(main())
