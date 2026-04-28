import io
import re
import zipfile
from typing import Any


def generate_zip(graph: Any, nodes: list[Any], edges: list[Any]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("agent.py", _agent_py(graph, nodes, edges))
        archive.writestr(".env.example", _env_example(nodes))
        archive.writestr("requirements.txt", _requirements(nodes))
        archive.writestr("README.md", _readme(graph))
    return buffer.getvalue()


def _agent_py(graph: Any, nodes: list[Any], edges: list[Any]) -> str:
    node_defs = []
    for node in nodes:
        name = _snake(node.label or node.id)
        node_defs.append(
            f"""
async def {name}(state: AgentState) -> AgentState:
    # Generated placeholder for {node.node_type}: {node.label}
    state = dict(state)
    state.setdefault("trace", []).append({{"node_id": "{node.id}", "label": "{node.label}", "status": "ok"}})
    return state
"""
        )
    node_adds = "\n".join(f'    graph.add_node("{node.id}", {_snake(node.label or node.id)})' for node in nodes)
    edge_adds = "\n".join(
        f'    graph.add_edge("{edge.source_node_id}", "{edge.target_node_id}")'
        for edge in edges
        if not edge.condition_label
    )
    first = next((node for node in nodes if node.node_type.lower() == "start"), nodes[0] if nodes else None)
    start_edge = f'    graph.add_edge(START, "{first.id}")' if first else "    graph.add_edge(START, END)"
    end_edges = ""
    if nodes and not edges:
        end_edges = "\n".join(f'    graph.add_edge("{node.id}", END)' for node in nodes)
    return (
        f"""import asyncio
import operator
import os
from typing import Annotated, Any, Optional, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

load_dotenv()


class AgentState(TypedDict, total=False):
    query: str
    messages: Annotated[list[BaseMessage], operator.add]
    nlp_result: Optional[dict]
    current_output: str
    metadata: dict
    session_id: Optional[str]
    artifact_refs: dict
    db_result: Optional[Any]
    http_result: Optional[Any]
    trace: Annotated[list[dict], operator.add]

{''.join(node_defs)}

def build_graph():
    graph = StateGraph(AgentState)
{node_adds or '    pass'}
{start_edge}
{edge_adds}
{end_edges}
    return graph.compile()


async def main(query: str):
    app = build_graph()
    state = {{
        "query": query,
        "messages": [HumanMessage(content=query)],
        "current_output": query,
        "metadata": {{}},
        "artifact_refs": {{}},
        "trace": [],
    }}
    result = await app.ainvoke(state)
    print(result.get("current_output", ""))


if __name__ == "__main__":
    asyncio.run(main(input("Query: ")))
"""
    )


def _env_example(nodes: list[Any]) -> str:
    lines = []
    for node in nodes:
        if node.node_type.lower() in {"llm", "llmnode"}:
            lines.append(f"{_snake(node.label).upper()}_API_KEY=your-key-here")
    return "\n".join(lines) + ("\n" if lines else "")


def _requirements(nodes: list[Any]) -> str:
    return "\n".join(
        [
            "langchain",
            "langgraph",
            "langchain-openai",
            "python-dotenv",
            "httpx",
            "mcp",
        ]
    ) + "\n"


def _readme(graph: Any) -> str:
    return f"# {graph.name}\n\nGenerated LangGraph agent export.\n\n```bash\npip install -r requirements.txt\npython agent.py\n```\n"


def _snake(value: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    if not name or name[0].isdigit():
        name = f"node_{name}"
    return name
