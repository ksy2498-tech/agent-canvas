import re
from typing import Any

from app.engine.nodes._common import append_trace
from app.engine.state import AgentState


def build_nlp_node(config: dict[str, Any]):
    async def node(state: AgentState) -> AgentState:
        input_key = config.get("input_key") or config.get("inputKey") or "current_output"
        text = _state_value(state, input_key) or state.get("query", "")
        engine = str(config.get("engine", "kiwi")).lower()
        analysis_type = config.get("analysis_type") or config.get("analysisType") or "morpheme"
        tokens = _analyze_tokens(str(text), engine)
        nouns = [item["form"] for item in tokens if str(item.get("pos", "")).startswith("N")]
        result = {
            "engine": engine,
            "analysis_type": analysis_type,
            "input_key": input_key,
            "text": str(text),
            "tokens": tokens,
            "nouns": nouns,
        }
        output_key = config.get("output_key") or config.get("outputKey") or "nlp_result"
        return {
            output_key: result,
            "nlp_result": result,
            **append_trace(
                state,
                config.get("_node_id", "nlp"),
                config.get("_label", "NLP"),
                engine=engine,
                analysis_type=analysis_type,
                input_key=input_key,
                token_count=len(tokens),
                noun_count=len(nouns),
            ),
        }

    return node


def _analyze_tokens(text: str, engine: str) -> list[dict[str, Any]]:
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
            ]
        except Exception:
            pass
    return [{"form": token, "pos": "UNK"} for token in re.findall(r"\w+", text)]


def _state_value(state: AgentState, key: str | None) -> Any:
    if not key:
        return None
    direct = _path_value(state, key)
    if direct is not None:
        return direct
    return _path_value(state.get("node_results", {}), key)


def _path_value(value: Any, key: str | None) -> Any:
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
