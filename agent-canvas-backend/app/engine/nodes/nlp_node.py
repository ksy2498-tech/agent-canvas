import re
from typing import Any

from app.engine.nodes._common import append_trace
from app.engine.state import AgentState


def build_nlp_node(config: dict[str, Any]):
    async def node(state: AgentState) -> AgentState:
        text = state.get(config.get("input_key", "current_output")) or state.get("query", "")
        engine = config.get("engine", "kiwi").lower()
        if engine == "kiwi":
            try:
                from kiwipiepy import Kiwi

                kiwi = Kiwi()
                tokens = [
                    {"form": token.form, "tag": token.tag, "start": token.start, "len": token.len}
                    for token in kiwi.tokenize(text)
                ]
            except Exception:
                tokens = [{"form": token, "tag": "UNK"} for token in re.findall(r"\w+", text)]
        else:
            tokens = [{"form": token, "tag": "UNK"} for token in re.findall(r"\w+", text)]
        result = {"engine": engine, "tokens": tokens}
        output_key = config.get("output_key", "nlp_result")
        return {
            output_key: result,
            "nlp_result": result,
            **append_trace(state, config.get("_node_id", "nlp"), config.get("_label", "NLP"), token_count=len(tokens)),
        }

    return node

