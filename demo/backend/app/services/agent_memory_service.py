"""Project-scoped durable memory snapshots for autonomous sandbox agents.

The application database remains authoritative. Before an agent run, this
service materializes only the upstream history visible to that node into a
read-only-style sandbox bundle. The prompt receives a compact working memory;
the agent can retrieve exact older details from the archive or SQLite index.
"""

from __future__ import annotations

import asyncio
import os
import re
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import dataclass
from typing import Dict, List, Tuple

from app.core.config import settings
from app.infra.asset_manager import AssetManager
from app.utils.context_compressor import estimate_tokens, get_compressor


MEMORY_ROOT = ".mm_agent/memory"
MEMORY_RULE_PATH = ".claude/rules/mm_agent_memory.md"
STEP_HEADER_RE = re.compile(
    r"^> ## Step (?P<node_id>[^:]+): (?P<title>.+)$", re.MULTILINE
)


QUERY_SCRIPT = r'''#!/usr/bin/env python3
"""Query the project-scoped agent memory snapshot without loading it all."""
import argparse
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("memory.sqlite3")


def clip(text, offset, max_chars):
    text = text or ""
    part = text[offset:offset + max_chars]
    if offset:
        part = f"[continued from character {offset}]\n" + part
    if offset + max_chars < len(text):
        part += f"\n\n[more available; use --offset {offset + max_chars}]"
    return part


def main():
    parser = argparse.ArgumentParser(description="List, search, or read project memory")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="list indexed workflow steps")
    search = sub.add_parser("search", help="search titles and exact historical text")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=8)
    show = sub.add_parser("show", help="read one exact step by node id")
    show.add_argument("node_id")
    show.add_argument("--offset", type=int, default=0)
    show.add_argument("--max-chars", type=int, default=16000)
    args = parser.parse_args()

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        if args.command == "list":
            rows = conn.execute(
                "SELECT node_id, title, estimated_tokens FROM memory_entries ORDER BY position"
            )
            for row in rows:
                print(f"{row['node_id']}\t{row['title']}\t~{row['estimated_tokens']} tokens")
            return

        if args.command == "search":
            needle = f"%{args.query.lower()}%"
            limit = max(1, args.limit)
            try:
                fts_query = '"' + args.query.replace('"', '""') + '"'
                rows = conn.execute(
                    """SELECT e.node_id, e.title, e.content
                       FROM memory_fts AS f
                       JOIN memory_entries AS e ON e.position = f.position
                       WHERE memory_fts MATCH ?
                       ORDER BY e.position DESC LIMIT ?""",
                    (fts_query, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []
            if not rows:
                rows = conn.execute(
                    """SELECT node_id, title, content FROM memory_entries
                       WHERE lower(node_id) LIKE ? OR lower(title) LIKE ? OR lower(content) LIKE ?
                       ORDER BY position DESC LIMIT ?""",
                    (needle, needle, needle, limit),
                ).fetchall()
            for row in rows:
                compact = " ".join(row["content"].split())[:700]
                print(f"## {row['node_id']}: {row['title']}\n{compact}\n")
            if not rows:
                print("No matching memory entries.")
            return

        row = conn.execute(
            "SELECT node_id, title, content FROM memory_entries WHERE node_id = ?",
            (args.node_id,),
        ).fetchone()
        if row is None:
            raise SystemExit(f"Unknown node id: {args.node_id}")
        print(clip(row["content"], max(0, args.offset), max(1, args.max_chars)))


if __name__ == "__main__":
    main()
'''


@dataclass(frozen=True)
class MemoryEntry:
    position: int
    node_id: str
    title: str
    line_start: int
    line_end: int
    content: str

    @property
    def estimated_tokens(self) -> int:
        return estimate_tokens(self.content)


@dataclass(frozen=True)
class AgentMemoryBundle:
    manifest: Dict[str, str]
    working_summary: str
    entry_count: int


class AgentMemoryService:
    """Materialize searchable, project-scoped memory into content-addressed files."""

    def __init__(self, assets: AssetManager):
        self.assets = assets

    async def materialize(self, history: str) -> AgentMemoryBundle:
        files, working_summary, entry_count = await asyncio.to_thread(
            self._build_files, history or ""
        )
        hashes = await asyncio.gather(
            *(self.assets.save_bytes(content) for content in files.values())
        )
        manifest = {
            path: blob_hash for path, blob_hash in zip(files.keys(), hashes)
        }
        return AgentMemoryBundle(
            manifest=manifest,
            working_summary=working_summary,
            entry_count=entry_count,
        )

    def _build_files(self, history: str) -> Tuple[Dict[str, bytes], str, int]:
        entries = self._parse_entries(history)
        index = self._build_index(entries)
        summary = self._build_working_summary(entries)
        database = self._build_database(entries)
        readme = self._build_readme(len(entries))
        archive = history or "(No upstream history available.)"

        files = {
            MEMORY_RULE_PATH: self._build_agent_rule(len(entries)).encode("utf-8"),
            f"{MEMORY_ROOT}/README.md": readme.encode("utf-8"),
            f"{MEMORY_ROOT}/index.md": index.encode("utf-8"),
            f"{MEMORY_ROOT}/working_memory.md": summary.encode("utf-8"),
            f"{MEMORY_ROOT}/project_history.md": archive.encode("utf-8"),
            f"{MEMORY_ROOT}/memory.sqlite3": database,
            f"{MEMORY_ROOT}/query_memory.py": QUERY_SCRIPT.encode("utf-8"),
        }
        return files, summary, len(entries)

    @staticmethod
    def _parse_entries(history: str) -> List[MemoryEntry]:
        matches = list(STEP_HEADER_RE.finditer(history))
        entries: List[MemoryEntry] = []
        for position, match in enumerate(matches, start=1):
            start = match.start()
            end = matches[position].start() if position < len(matches) else len(history)
            # Keep the exact archive slice in SQLite as well. Formatting can be
            # normalized at display time, but durable memory must not be lossy.
            content = history[start:end].strip()
            entries.append(
                MemoryEntry(
                    position=position,
                    node_id=match.group("node_id").strip(),
                    title=match.group("title").strip(),
                    line_start=history.count("\n", 0, start) + 1,
                    line_end=history.count("\n", 0, end) + 1,
                    content=content,
                )
            )

        meaningful = history.strip()
        if not entries and meaningful and not meaningful.startswith("(No upstream"):
            entries.append(
                MemoryEntry(
                    position=1,
                    node_id="context",
                    title="Upstream context",
                    line_start=1,
                    line_end=max(1, history.count("\n") + 1),
                    content=history,
                )
            )
        return entries

    @staticmethod
    def _build_index(entries: List[MemoryEntry]) -> str:
        lines = [
            "# Project Memory Index",
            "",
            "Exact upstream history is stored in `project_history.md` and `memory.sqlite3`.",
            "Load only the steps relevant to the current task.",
            "",
            "| Position | Node | Title | Archive lines | Est. tokens |",
            "|---:|---|---|---:|---:|",
        ]
        for entry in entries:
            safe_title = entry.title.replace("|", "\\|")
            lines.append(
                f"| {entry.position} | `{entry.node_id}` | {safe_title} | "
                f"{entry.line_start}-{entry.line_end} | {entry.estimated_tokens} |"
            )
        if not entries:
            lines.append("| - | - | No upstream workflow steps | - | 0 |")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _build_working_summary(entries: List[MemoryEntry]) -> str:
        if not entries:
            return "No upstream workflow history is available."

        index_lines = [
            f"- {entry.node_id}: {entry.title} (~{entry.estimated_tokens} tokens)"
            for entry in entries
        ]
        recent = entries[-3:]
        recent_details = "\n\n".join(entry.content for entry in recent)
        draft = (
            f"{len(entries)} upstream workflow steps are preserved in durable memory.\n\n"
            "Step index:\n"
            + "\n".join(index_lines)
            + "\n\nRecent detailed context:\n"
            + recent_details
        )
        return get_compressor().compact_text(
            draft, settings.AGENT_WORKING_MEMORY_TOKENS
        )

    @staticmethod
    def _build_database(entries: List[MemoryEntry]) -> bytes:
        fd, path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        try:
            # sqlite3.Connection.__exit__ commits/rolls back but does not close
            # the handle. Windows refuses to unlink an open database, so wrap
            # the connection in closing() and release it before reading/deleting.
            with closing(sqlite3.connect(path)) as conn:
                conn.execute(
                    """CREATE TABLE memory_entries (
                       position INTEGER PRIMARY KEY,
                       node_id TEXT NOT NULL,
                       title TEXT NOT NULL,
                       line_start INTEGER NOT NULL,
                       line_end INTEGER NOT NULL,
                       estimated_tokens INTEGER NOT NULL,
                       content TEXT NOT NULL
                    )"""
                )
                conn.executemany(
                    """INSERT INTO memory_entries
                       (position, node_id, title, line_start, line_end, estimated_tokens, content)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    [
                        (
                            entry.position,
                            entry.node_id,
                            entry.title,
                            entry.line_start,
                            entry.line_end,
                            entry.estimated_tokens,
                            entry.content,
                        )
                        for entry in entries
                    ],
                )
                conn.execute("CREATE INDEX idx_memory_node_id ON memory_entries(node_id)")
                try:
                    conn.execute(
                        """CREATE VIRTUAL TABLE memory_fts USING fts5(
                           position UNINDEXED, node_id, title, content
                        )"""
                    )
                    conn.executemany(
                        """INSERT INTO memory_fts (position, node_id, title, content)
                           VALUES (?, ?, ?, ?)""",
                        [
                            (entry.position, entry.node_id, entry.title, entry.content)
                            for entry in entries
                        ],
                    )
                except sqlite3.OperationalError:
                    # Minimal Python builds may omit FTS5. The bundled query
                    # tool transparently falls back to substring search.
                    pass
                conn.commit()
            with open(path, "rb") as database_file:
                return database_file.read()
        finally:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass

    @staticmethod
    def _build_readme(entry_count: int) -> str:
        return f"""# Agent Project Memory

This project-scoped snapshot contains {entry_count} upstream workflow steps.
The application database is authoritative; these files are rebuilt before each run.

Use selective retrieval so old details do not crowd out the current task:

```bash
python3 .mm_agent/memory/query_memory.py list
python3 .mm_agent/memory/query_memory.py search "keyword"
python3 .mm_agent/memory/query_memory.py show "NODE_ID"
```

`working_memory.md` is the bounded rolling checkpoint. `project_history.md`
and `memory.sqlite3` preserve exact history. Treat `.mm_agent` as read-only
infrastructure and save task outputs outside this directory.
"""

    @staticmethod
    def _build_agent_rule(entry_count: int) -> str:
        return f"""# MM-Agent durable project memory

There are {entry_count} exact upstream workflow steps under `.mm_agent/memory/`.
When information from an earlier step is missing or uncertain, use
`query_memory.py list`, `search`, and `show` to retrieve only relevant entries.
Never guess merely because an old detail was compacted out of the conversation.
Treat `.mm_agent` as read-only and save task deliverables outside it.

## Compact Instructions

When compacting, preserve the current goal, validated decisions, changed files,
test status, unresolved errors, and the existence of the searchable memory paths.
Do not copy the complete archive into the summary; retrieve it selectively.
"""
