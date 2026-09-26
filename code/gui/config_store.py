"""config/system.yaml laden, ändern und speichern - Kommentare und Formatierung bleiben erhalten."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import yaml
from ruamel.yaml import YAML
from ruamel.yaml.comments import Comment, CommentedMap, CommentedSeq

from common.config import DEFAULT_CONFIG


class ConfigStore:
    def __init__(self, path: str | Path = DEFAULT_CONFIG):
        self.path = Path(path)
        self._yaml = YAML()
        self._yaml.preserve_quotes = True
        self._yaml.width = 120
        self._yaml.representer.add_representer(
            type(None), lambda r, d: r.represent_scalar("tag:yaml.org,2002:null", "null"))
        self.data: CommentedMap = CommentedMap()
        self.dirty = False
        self.reload()

    def reload(self) -> None:
        """Re-read the file. The dict object stays the same, so modules keep their reference."""
        with open(self.path, encoding="utf-8") as f:
            fresh = self._yaml.load(f)
        self.data.clear()
        self.data.update(fresh)
        setattr(self.data, Comment.attrib, getattr(fresh, Comment.attrib))  # top-level comments
        self.dirty = False

    def save(self) -> None:
        buf = io.StringIO()
        self._yaml.dump(self.data, buf)
        yaml.safe_load(buf.getvalue())    # sanity check before overwriting
        self.path.write_text(buf.getvalue(), encoding="utf-8")
        self.dirty = False

    # -- editing helpers -----------------------------------------------------------
    def set(self, path: list, value: Any) -> None:
        """Set a value by key path, e.g. ["robot", "poses", "inspection"]."""
        node = self.data
        for k in path[:-1]:
            node = node[k]
        if isinstance(value, list):
            value = flow_seq(value)
        node[path[-1]] = value
        self.dirty = True

    def get(self, path: list) -> Any:
        node = self.data
        for k in path:
            node = node[k]
        return node


def flow_seq(values: list) -> CommentedSeq:
    """List written inline as [a, b, c] - like the lists in system.yaml."""
    seq = CommentedSeq(values)
    seq.fa.set_flow_style()
    return seq


def eol_comment(mapping: Any, key: Any) -> str:
    """End-of-line comment of `key` in a ruamel mapping ('' if none)."""
    try:
        tokens = mapping.ca.items.get(key)
        if tokens and len(tokens) > 2 and tokens[2] is not None:
            return tokens[2].value.strip().lstrip("#").strip().split("\n")[0]
    except AttributeError:
        pass
    return ""


def format_value(v: Any) -> str:
    """Scalar or list as YAML text for display/editing."""
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(format_value(x) for x in v) + "]"
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return v
    return str(v)


def parse_value(text: str, old: Any) -> Any:
    """Parse edited text with YAML rules; keep float type if the old value was float."""
    value = yaml.safe_load(text) if text.strip() else None
    if isinstance(old, float) and isinstance(value, int) and not isinstance(value, bool):
        return float(value)
    if isinstance(old, (list, tuple)) and not isinstance(value, list):
        raise ValueError("Liste erwartet, z. B. [1.0, 2.0]")
    if isinstance(old, (int, float)) and not isinstance(old, bool) and not isinstance(value, (int, float)):
        raise ValueError("Zahl erwartet")
    return value
