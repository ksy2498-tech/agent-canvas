import re
from typing import Any

from app.engine.nodes._common import append_trace, runtime_from_config, write_runtime
from app.engine.nodes.state_path import assign_path, state_value
from app.engine.state import AgentState


def build_nlp_node(config: dict[str, Any]):
    async def node(state: AgentState, run_config: dict[str, Any] | None = None) -> AgentState:
        input_key = config.get("input_key") or config.get("inputKey") or "current_output"
        text = state_value(state, input_key) or state.get("query", "")
        engine = str(config.get("engine", "kiwi")).lower()
        analysis_type = config.get("analysis_type") or config.get("analysisType") or "morpheme"
        result_target = config.get("result_target") or config.get("resultTarget") or "runtime"
        output_key = config.get("output_key") or config.get("outputKey") or "nlp_result"
        summary_key = config.get("summary_key") or config.get("summaryKey") or "metadata.nlp_summary"
        tokens, fallback_reason = _analyze_tokens(str(text), engine)
        nouns = [item["form"] for item in tokens if str(item.get("pos", "")).startswith("N")]
        result = {
            "engine": engine,
            "analysis_type": analysis_type,
            "input_key": input_key,
            "text": str(text),
            "tokens": tokens,
            "nouns": nouns,
            "fallback": fallback_reason is not None,
            "fallback_reason": fallback_reason,
        }
        updates: AgentState = {}
        if result_target in {"runtime", "both"}:
            runtime = runtime_from_config(run_config)
            write_runtime(runtime, "nlp", output_key, result)
        if result_target in {"state", "both"}:
            assign_path(updates, output_key, result)
        if result_target == "runtime" and summary_key:
            assign_path(updates, summary_key, _summary(result))
        updates.update(
            append_trace(
                state,
                config.get("_node_id", "nlp"),
                config.get("_label", "NLP"),
                engine=engine,
                analysis_type=analysis_type,
                input_key=input_key,
                result_target=result_target,
                result_key=output_key,
                token_count=len(tokens),
                noun_count=len(nouns),
                fallback=fallback_reason is not None,
            )
        )
        return updates

    return node


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "engine": result.get("engine"),
        "analysis_type": result.get("analysis_type"),
        "input_key": result.get("input_key"),
        "token_count": len(result.get("tokens") or []),
        "noun_count": len(result.get("nouns") or []),
        "nouns_sample": (result.get("nouns") or [])[:10],
        "fallback": result.get("fallback"),
        "fallback_reason": result.get("fallback_reason"),
    }


def _analyze_tokens(text: str, engine: str) -> tuple[list[dict[str, Any]], str | None]:
    if engine == "kiwi":
        try:
            from kiwipiepy import Kiwi

            kiwi = Kiwi()
            return [
                {
                    "form": token.form,
                    "pos": token.tag,
                    "start": token.start,
                    "len": token.len,
                }
                for token in kiwi.tokenize(text)
            ], None
        except Exception as exc:
            return _regex_tokens(text), f"Kiwi unavailable: {exc}"
    return _regex_tokens(text), f"Unsupported engine `{engine}`; used regex fallback"


def _regex_tokens(text: str) -> list[dict[str, Any]]:
    return [{"form": token, "pos": "UNK"} for token in re.findall(r"\w+", text)]
