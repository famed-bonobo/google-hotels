"""Builds synthetic Google answers from {path: value} maps, so tests state only the positions a parser reads.

Real answers are not stored in this repository: they carry reviewers' and photographers' names, which this library
never returns and which must not be published.
"""

from __future__ import annotations

import json
from typing import Any

Path = tuple[int | str, ...]


def nested(values: dict[Path, Any]) -> Any:
    """A nest of lists (int steps) and dicts (str steps) holding each value at its path, None everywhere else."""
    root: Any = None
    for path, value in values.items():
        root = _place(root, path, value)
    return root


def _place(node: Any, path: Path, value: Any) -> Any:
    if not path:
        return value
    step, rest = path[0], path[1:]
    if isinstance(step, str):
        node = node if isinstance(node, dict) else {}
        node[step] = _place(node.get(step), rest, value)
        return node
    node = node if isinstance(node, list) else []
    node.extend([None] * (step + 1 - len(node)))
    node[step] = _place(node[step], rest, value)
    return node


def framed_answer(rpc_id: str, payload: Any) -> str:
    """A batchexecute HTTP answer carrying `payload` for `rpc_id`, framed as Google frames it."""
    row = json.dumps([['wrb.fr', rpc_id, json.dumps(payload), None, None, None, 'generic']])
    return f')]}}\'\n\n{len(row)}\n{row}\n25\n[["e",4,null,null,123]]\n'
