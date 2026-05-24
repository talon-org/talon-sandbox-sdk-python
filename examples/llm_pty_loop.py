"""LLM PTY loop — stream terminal output, feed to LLM."""
import asyncio

from talon_sandbox import Sandbox


async def main() -> None:
    async with await Sandbox.create(image="ubuntu:22.04") as sb:
        pty = await sb.terminal.open(rows=40, cols=120)

        output_chunks: list[bytes] = []

        pty.on("data", lambda chunk: output_chunks.append(chunk))
        pty.on("exit", lambda code: print(f"Terminal exited: {code}"))

        await pty.write("ls -la /\n")
        await asyncio.sleep(0.5)

        await pty.write("echo 'done'\n")
        await asyncio.sleep(0.5)

        await pty.close()

        full_output = b"".join(output_chunks).decode(errors="replace")
        print("Terminal output:")
        print(full_output)
        # In a real LLM loop: llm.feed(full_output)


if __name__ == "__main__":
    asyncio.run(main())
