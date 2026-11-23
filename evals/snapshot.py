"""Save every eval server's tool definitions to evals/snapshots/<name>.json."""

import asyncio
import json
from pathlib import Path

from slimproof.core.audit import tool_definitions
from slimproof.core.configs import load_servers

EVALS = Path(__file__).parent


async def main() -> None:
    servers, _ = load_servers(EVALS / "servers.json")
    out = EVALS / "snapshots"
    out.mkdir(exist_ok=True)
    for name, server in servers.items():
        tools = await tool_definitions(server)
        (out / f"{name}.json").write_text(json.dumps(tools, indent=2) + "\n", encoding="utf-8")
        print(f"{name}: {len(tools)} tools")


if __name__ == "__main__":
    asyncio.run(main())
