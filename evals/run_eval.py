"""Run the tool-selection eval: original vs slim vs strip-all tools, scored per request."""

import argparse
import hashlib
import json
import posixpath
import sys
from pathlib import Path
from statistics import mean
from typing import Any

import anthropic
from anthropic.types import ToolParam
from jsonschema.validators import validator_for

EVALS = Path(__file__).parent
CACHE = EVALS / ".cache"
VARIANTS = ("original", "slim", "strip-all")
NAME_MAPS = ("properties", "$defs", "definitions", "patternProperties")  # keys are names

ROOTS = {"filesystem": "/project", "desktop-commander": "/project"}
PATH_KEYS = ("path", "paths", "source", "destination", "file_path")

PRICES = {  # $ per million tokens: input, output, cache read (cache write = 1.25 x input)
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
    "claude-sonnet-5-5": (2.00, 10.00, 0.10),
}


def strip_descriptions(schema: Any) -> Any:
    """Copy of a JSON schema with every `description` keyword removed."""
    if isinstance(schema, list):
        return [strip_descriptions(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key in NAME_MAPS:
            out[key] = {name: strip_descriptions(sub) for name, sub in value.items()}
        elif key != "description":
            out[key] = strip_descriptions(value)
    return out


def load_tools(server: str, variant: str) -> list[ToolParam]:
    """The tool list for one server and variant, in Claude API format."""
    folder = "slim" if variant == "slim" else "snapshots"
    path = EVALS / folder / f"{server}.json"
    tools: list[ToolParam] = []
    for t in json.loads(path.read_text(encoding="utf-8")):
        tool: ToolParam = {
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["inputSchema"],
        }
        if variant == "strip-all":
            tool = {"name": t["name"], "input_schema": strip_descriptions(t["inputSchema"])}
        tools.append(tool)
    return tools


def load_dataset(server: str) -> list[dict[str, Any]]:
    """The eval requests for one server, one dict per JSONL line."""
    lines = (EVALS / "datasets" / f"{server}.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def load_context(server: str) -> str:
    """The fixed system prompt for one server, the same for every variant."""
    contexts = json.loads((EVALS / "datasets" / "context.json").read_text(encoding="utf-8"))
    return contexts[server]


def cache_key(model: str, tools: list[ToolParam], system: str, request: str, run: int) -> str:
    """A stable hash of everything that decides one API answer."""
    data = json.dumps([model, tools, system, request, run], sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()


def ask(
    client: anthropic.Anthropic,
    model: str,
    tools: list[ToolParam],
    system: str,
    request: str,
    run: int,
) -> dict[str, Any]:
    """Claude's response to one request, from the cache or the API."""
    path = CACHE / f"{cache_key(model, tools, system, request, run)}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        output_config={"effort": "medium"},
        tools=tools,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": request}],
    )
    answer = response.to_dict()
    CACHE.mkdir(exist_ok=True)
    path.write_text(json.dumps(answer, indent=2), encoding="utf-8")
    return answer


def first_call(answer: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """The first tool Claude called, as (name, input), or None if it called none."""
    for block in answer["content"]:
        if block["type"] == "tool_use":
            return block["name"], block["input"]
    return None


def absolute(value: Any, root: str) -> Any:
    """`value` with relative paths made absolute against `root` (URLs left alone)."""
    if isinstance(value, list):
        return [absolute(item, root) for item in value]
    if isinstance(value, str) and "://" not in value:
        return posixpath.normpath(posixpath.join(root, value))
    return value


def matches(expected: Any, actual: Any) -> bool:
    """True if `actual` has every expected value; extra dict keys and list order don't count."""
    if isinstance(expected, dict) and isinstance(actual, str):
        try:
            actual = json.loads(actual)
        except json.JSONDecodeError:
            return False
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and matches(value, actual[key]) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and sorted(map(json.dumps, expected)) == sorted(
            map(json.dumps, actual)
        )
    return expected == actual


def normalize(server: str, args: dict[str, Any]) -> dict[str, Any]:
    """`args` with local paths made absolute, for servers that work on files."""
    root = ROOTS.get(server)
    if root is None:
        return args
    return {
        key: absolute(value, root) if key in PATH_KEYS else value for key, value in args.items()
    }


def valid(args: dict[str, Any], schema: Any) -> bool:
    """True if `args` pass the tool's input schema."""
    return validator_for(schema)(schema).is_valid(args)


def score(
    case: dict[str, Any],
    call: tuple[str, dict[str, Any]] | None,
    tools: list[ToolParam],
    server: str,
) -> dict[str, bool]:
    """Tool, argument and false-call scores for one answer."""
    expected = case["expected_tool"]
    if call is None:
        return {"tool_ok": expected is None, "args_ok": False, "false_call": False}
    name, args = call
    accepted = expected if isinstance(expected, list) else [expected]
    if name not in accepted:
        return {"tool_ok": False, "args_ok": False, "false_call": expected is None}
    schema = next(t["input_schema"] for t in tools if t["name"] == name)
    args_ok = valid(args, schema) and (
        name != accepted[0] or matches(case["expected_args"], normalize(server, args))
    )
    return {"tool_ok": True, "args_ok": args_ok, "false_call": False}


def run_server(
    client: anthropic.Anthropic,
    model: str,
    server: str,
    variant: str,
    runs: int,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Score every request for one server and variant, `runs` times."""
    tools, system = load_tools(server, variant), load_context(server)
    rows: list[dict[str, Any]] = []
    for run in range(1, runs + 1):
        for case in load_dataset(server)[:limit]:
            answer = ask(client, model, tools, system, case["request"], run)
            result = score(case, first_call(answer), tools, server)
            rows.append(
                {
                    "server": server,
                    "variant": variant,
                    "run": run,
                    "id": case["id"],
                    "difficulty": case["difficulty"],
                    "usage": answer["usage"],
                    **result,
                }
            )
    return rows


def cost(model: str, usage: dict[str, Any]) -> float:
    """Dollar cost of one API call, from its usage numbers."""
    price_in, price_out, price_read = PRICES[model]
    tokens = (
        usage["input_tokens"] * price_in
        + usage.get("cache_creation_input_tokens", 0) * price_in * 1.25
        + usage.get("cache_read_input_tokens", 0) * price_read
        + usage["output_tokens"] * price_out
    )
    return tokens / 1_000_000


def rate(rows: list[dict[str, Any]], key: str) -> list[float]:
    """For each run, the share of `rows` where `key` is true."""
    runs = sorted({r["run"] for r in rows})
    return [mean(r[key] for r in rows if r["run"] == run) for run in runs]


def percent(values: list[float]) -> str:
    """Mean as a percent, plus the min-max spread when runs differ."""
    if not values:
        return "-"
    text = f"{mean(values):.0%}"
    if max(values) > min(values):
        text += f" ({min(values):.0%}-{max(values):.0%})"
    return text


def summarize(model: str, rows: list[dict[str, Any]]) -> str:
    """A Markdown results table with one line per server and variant."""
    lines = [
        "| Server | Variant | Prompt tokens | Tool acc. | Arg valid | False calls | Cost |",
        "|---|---|---|---|---|---|---|",
    ]
    for server, variant in dict.fromkeys((r["server"], r["variant"]) for r in rows):
        group = [r for r in rows if r["server"] == server and r["variant"] == variant]
        usage = group[0]["usage"]
        prompt = usage["cache_creation_input_tokens"] + usage["cache_read_input_tokens"]
        tool_cases = [r for r in group if r["difficulty"] != "no_tool"]
        no_tool = [r for r in group if r["difficulty"] == "no_tool"]
        dollars = sum(cost(model, r["usage"]) for r in group)
        lines.append(
            f"| {server} | {variant} | {prompt:,} | {percent(rate(group, 'tool_ok'))} "
            f"| {percent(rate(tool_cases, 'args_ok'))} | {percent(rate(no_tool, 'false_call'))} "
            f"| ${dollars:.3f} |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("servers", nargs="*", help="servers to run (default: every dataset)")
    parser.add_argument("--model", default="claude-haiku-5-5", choices=sorted(PRICES))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--limit", type=int, help="only the first N requests (a cheap test)")
    args = parser.parse_args()
    servers = args.servers or sorted(p.stem for p in (EVALS / "datasets").glob("*.jsonl"))
    client = anthropic.Anthropic()
    rows: list[dict[str, Any]] = []
    for server in servers:
        for variant in VARIANTS:
            new = run_server(client, args.model, server, variant, args.runs, args.limit)
            print(f"{server} {variant}: {len(new)} answers", flush=True)
            rows += new
    table = summarize(args.model, rows)
    print(table)
    if args.limit is None:
        out = EVALS / "results" / f"{args.model}.md"
        out.parent.mkdir(exist_ok=True)
        out.write_text(f"# Eval results: {args.model}\n\n{table}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
