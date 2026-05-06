from __future__ import annotations

import asyncio
import json
import sys
import textwrap
from typing import Any

MAX_OUTPUT_BYTES = 1_000_000


SANDBOX_SCRIPT = r"""
import asyncio
import inspect
import json
import sys

SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "round": round,
    "str": str,
    "sum": sum,
    "set": set,
}


async def maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


async def main():
    payload = json.loads(sys.stdin.read() or "{}")
    namespace = {"__builtins__": SAFE_BUILTINS}
    exec(payload.get("code") or "async def run(state, mcp, runtime):\n    return {}", namespace)
    fn_name = payload.get("function_name") or "run"
    fn = namespace.get(fn_name)
    if not callable(fn):
        raise ValueError(f"Code must define {fn_name}(...)" )
    state = payload.get("state") or {}
    runtime = payload.get("runtime") or {}
    mcp = {}
    argc = len(inspect.signature(fn).parameters)
    if argc >= 3:
        result = await maybe_await(fn(state, mcp, runtime))
    else:
        result = await maybe_await(fn(state, mcp))
    if not isinstance(result, dict):
        raise ValueError("Code function must return a dict")
    print(json.dumps({"result": result, "runtime": runtime}, ensure_ascii=False, default=str))


if __name__ == "__main__":
    asyncio.run(main())
"""


async def run_user_code_subprocess(
    *,
    code: str,
    state: dict[str, Any],
    runtime: dict[str, Any],
    function_name: str = "run",
    timeout_seconds: float = 5.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = json.dumps(
        {
            "code": code,
            "state": state,
            "runtime": runtime,
            "function_name": function_name,
        },
        ensure_ascii=False,
        default=str,
    )
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",
        "-c",
        SANDBOX_SCRIPT,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_task = asyncio.create_task(_read_limited(proc.stdout, MAX_OUTPUT_BYTES))
    stderr_task = asyncio.create_task(_read_limited(proc.stderr, MAX_OUTPUT_BYTES))
    try:
        assert proc.stdin is not None
        proc.stdin.write(payload.encode())
        await proc.stdin.drain()
        proc.stdin.close()
        stdout, stderr = await asyncio.wait_for(
            asyncio.gather(stdout_task, stderr_task),
            timeout=timeout_seconds,
        )
        await asyncio.wait_for(proc.wait(), timeout=1)
    except asyncio.TimeoutError as exc:
        await _kill_process(proc, stdout_task, stderr_task)
        raise TimeoutError(f"Code execution timed out after {timeout_seconds:g}s") from exc
    except OutputLimitExceeded as exc:
        await _kill_process(proc, stdout_task, stderr_task)
        raise RuntimeError(str(exc)) from exc
    if proc.returncode != 0:
        message = stderr.decode(errors="replace").strip() or stdout.decode(errors="replace").strip()
        raise RuntimeError(_short_error(message))
    try:
        output = json.loads(stdout.decode() or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError("Code execution did not return valid JSON") from exc
    result = output.get("result")
    updated_runtime = output.get("runtime")
    if not isinstance(result, dict):
        raise RuntimeError("Code execution result must be a dict")
    return result, updated_runtime if isinstance(updated_runtime, dict) else runtime


def _short_error(message: str) -> str:
    text = textwrap.shorten(message.replace("\n", " "), width=800, placeholder=" ...")
    return text or "Code execution failed"


class OutputLimitExceeded(Exception):
    pass


async def _read_limited(stream: asyncio.StreamReader | None, limit: int) -> bytes:
    if stream is None:
        return b""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await stream.read(65536)
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > limit:
            raise OutputLimitExceeded(f"Code execution output exceeded {limit} bytes")
        chunks.append(chunk)


async def _kill_process(proc: asyncio.subprocess.Process, *tasks: asyncio.Task) -> None:
    for task in tasks:
        task.cancel()
    if proc.returncode is None:
        proc.kill()
    try:
        await asyncio.wait_for(proc.wait(), timeout=1)
    except asyncio.TimeoutError:
        pass
    await asyncio.gather(*tasks, return_exceptions=True)
