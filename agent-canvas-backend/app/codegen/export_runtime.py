import textwrap


EXPORT_RUNTIME_PY = textwrap.dedent(
    r'''
    import asyncio
    import json
    import operator
    import sys
    import textwrap
    from typing import Annotated, Any, TypedDict


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


    def merge_dicts(left: dict | None, right: dict | None) -> dict:
        merged = dict(left or {})
        for key, value in (right or {}).items():
            existing = merged.get(key)
            if isinstance(existing, dict) and isinstance(value, dict):
                merged[key] = merge_dicts(existing, value)
            else:
                merged[key] = value
        return merged


    class AgentState(TypedDict, total=False):
        query: str
        messages: Annotated[list[Any], operator.add]
        current_output: str
        node_results: Annotated[dict, merge_dicts]
        metadata: Annotated[dict, merge_dicts]
        runtime: Annotated[dict, merge_dicts]
        session_id: str | None
        artifacts: Annotated[dict, merge_dicts]
        trace: Annotated[list[dict], operator.add]


    def append_trace(node_id: str, label: str, status: str = "ok", **extra: Any) -> dict[str, Any]:
        return {"trace": [{"node_id": node_id, "label": label, "status": status, **extra}]}


    async def maybe_await(value: Any) -> Any:
        if hasattr(value, "__await__"):
            return await value
        return value


    def make_runtime(run_id: str | None = None) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "session": {},
            "tool_results": {},
            "nlp": {},
            "artifacts": {},
            "scratch": {},
        }


    def path_value(value: Any, key: str | None) -> Any:
        if not key:
            return None
        for part in str(key).split("."):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
            if value is None:
                return None
        return value


    def state_value(state: AgentState, key: str | None) -> Any:
        if not key:
            return None
        direct = path_value(state, key)
        if direct is not None:
            return direct
        return path_value(state.get("node_results", {}), key)


    def assign_path(target: dict[str, Any], key: str, value: Any) -> None:
        cursor = target
        parts = str(key).split(".")
        for part in parts[:-1]:
            next_value = cursor.get(part)
            if not isinstance(next_value, dict):
                next_value = {}
                cursor[part] = next_value
            cursor = next_value
        cursor[parts[-1]] = value


    def typed_value(value: Any, value_type: str | None) -> Any:
        if value_type == "number":
            try:
                number = float(value)
            except (TypeError, ValueError):
                return value
            return int(number) if number.is_integer() else number
        if value_type == "bool":
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in {"1", "true", "yes", "on"}
        if value_type == "json":
            try:
                return json.loads(value)
            except (TypeError, json.JSONDecodeError):
                return value
        return value


    def values_to_state(values: Any) -> dict[str, Any]:
        if isinstance(values, dict):
            return values
        if not isinstance(values, list):
            return {}
        updates: dict[str, Any] = {}
        for row in values:
            if not isinstance(row, dict):
                continue
            key = row.get("key")
            if not key:
                continue
            assign_path(updates, key, typed_value(row.get("value"), row.get("type")))
        return updates


    def tool_value(tool: dict[str, Any], snake_key: str, camel_key: str) -> Any:
        return tool.get(snake_key) or tool.get(camel_key)


    def tool_args(state: AgentState, config: dict[str, Any], tool_args_key: str | None) -> dict[str, Any]:
        if tool_args_key:
            value = state_value(state, tool_args_key)
            if isinstance(value, dict):
                return value
        value = config.get("tool_args") or config.get("toolArgs") or {}
        return value if isinstance(value, dict) else {}


    def runtime_result_key(key: str) -> str:
        return "tool_result" if key in {"tool_results", "runtime.tool_results"} else key


    def read_runtime(runtime: dict[str, Any], section: str, key: str | None = None) -> Any:
        section_value = runtime.get(section, {})
        if key is None:
            return section_value
        return path_value(section_value, key)


    class OutputLimitExceeded(Exception):
        pass


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


    def _short_error(message: str) -> str:
        text = textwrap.shorten(message.replace("\n", " "), width=800, placeholder=" ...")
        return text or "Code execution failed"


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
    '''
).lstrip()
