"""Static run-route graphs (invariant 10; DECISIONS §2, §11.6).

The module node set and dependency edges are a pure function of (pathway,
depth), compiled from the verified catalog routes. There are no data-selected
edges: nodes raise typed terminal errors and the engine finalizes failure at
the graph boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..config import Settings
from ..contracts import Depth
from ..methodology.bundle import DeployVBundle


@dataclass(frozen=True)
class RouteGraph:
    pathway: str
    depth: str
    nodes: tuple[str, ...]
    edges: frozenset[tuple[str, str]]
    stages: tuple[tuple[str, int], ...]


@lru_cache(maxsize=4)
def _bundle(root: Path) -> DeployVBundle:
    return DeployVBundle(root)


def route_from_plan(plan: dict) -> RouteGraph:
    nodes = tuple(node["module_id"] for node in plan["nodes"])
    edges = frozenset(
        (dependency, node["module_id"]) for node in plan["nodes"] for dependency in node["dependencies"]
    )
    stages = tuple((node["module_id"], node["stage"]) for node in plan["nodes"])
    return RouteGraph(pathway=plan["pathway"], depth=plan["depth"], nodes=nodes, edges=edges, stages=stages)


@lru_cache(maxsize=32)
def compiled_route(pathway: str, depth: str, root: Path | None = None) -> RouteGraph:
    bundle = _bundle(root or Settings().deploy_v_root)
    plan = bundle.compile(pathway, Depth(depth), None)
    return route_from_plan(plan)
