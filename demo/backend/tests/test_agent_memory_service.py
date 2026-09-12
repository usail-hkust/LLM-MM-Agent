import hashlib
import os
import sqlite3
import subprocess
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from app.core.config import settings
from app.services.agent_memory_service import AgentMemoryService, MEMORY_ROOT
from app.utils.context_compressor import estimate_tokens


class FakeAssetManager:
    def __init__(self):
        self.blobs = {}

    async def save_bytes(self, data: bytes) -> str:
        blob_hash = hashlib.sha256(data).hexdigest()
        self.blobs[blob_hash] = data
        return blob_hash


class AgentMemoryServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_database_connection_closes_before_temporary_file_is_deleted(self):
        events = []
        # Initialize tempfile's platform-specific directory probe before
        # intercepting unlink calls for the database-under-test.
        tempfile.gettempdir()
        real_connect = sqlite3.connect
        real_unlink = os.unlink

        class TrackingConnection:
            def __init__(self, path):
                self.connection = real_connect(path)

            def __getattr__(self, name):
                return getattr(self.connection, name)

            def close(self):
                self.connection.close()
                events.append("connection_closed")

        def checked_unlink(path):
            self.assertIn("connection_closed", events)
            events.append("file_deleted")
            real_unlink(path)

        with patch(
            "app.services.agent_memory_service.sqlite3.connect", TrackingConnection
        ), patch("app.services.agent_memory_service.os.unlink", checked_unlink):
            database = AgentMemoryService._build_database([])

        self.assertTrue(database.startswith(b"SQLite format 3"))
        self.assertEqual(events, ["connection_closed", "file_deleted"])

    async def test_materializes_exact_archive_searchable_database_and_summary(self):
        old_detail = "OLD-DECISION: use a robust median estimator"
        history = "\n".join(
            [
                "> ## Step 1.1: Problem Analysis",
                "> *(Completed at 2026-09-12 09:00)*",
                ">",
                f"> {old_detail}",
                ">",
                "> ----------------------------------------",
                "> ## Step 2.1-0: Model Design (Iter 1)",
                "> *(Completed at 2026-09-12 09:10)*",
                ">",
                "> RECENT-DECISION: validate with blocked folds",
            ]
        )
        assets = FakeAssetManager()
        service = AgentMemoryService(assets)

        bundle = await service.materialize(history)

        self.assertEqual(bundle.entry_count, 2)
        self.assertEqual(
            assets.blobs[bundle.manifest[f"{MEMORY_ROOT}/project_history.md"]].decode(),
            history,
        )
        self.assertIn("1.1: Problem Analysis", bundle.working_summary)
        self.assertIn("RECENT-DECISION", bundle.working_summary)
        self.assertLessEqual(
            estimate_tokens(bundle.working_summary),
            settings.AGENT_WORKING_MEMORY_TOKENS,
        )

        database = assets.blobs[bundle.manifest[f"{MEMORY_ROOT}/memory.sqlite3"]]
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_dir = Path(temp_dir)
            db_path = memory_dir / "memory.sqlite3"
            script_path = memory_dir / "query_memory.py"
            db_path.write_bytes(database)
            script_path.write_bytes(
                assets.blobs[bundle.manifest[f"{MEMORY_ROOT}/query_memory.py"]]
            )

            with closing(sqlite3.connect(db_path)) as conn:
                rows = conn.execute(
                    "SELECT node_id, title, content FROM memory_entries ORDER BY position"
                ).fetchall()
            self.assertEqual([row[0] for row in rows], ["1.1", "2.1-0"])
            self.assertIn(old_detail, rows[0][2])

            result = subprocess.run(
                ["python3", str(script_path), "search", "median"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("OLD-DECISION", result.stdout)

    async def test_empty_history_still_builds_a_valid_memory_bundle(self):
        assets = FakeAssetManager()
        bundle = await AgentMemoryService(assets).materialize(
            "(No upstream history available.)"
        )

        self.assertEqual(bundle.entry_count, 0)
        self.assertEqual(
            bundle.working_summary, "No upstream workflow history is available."
        )
        self.assertEqual(len(bundle.manifest), 7)


if __name__ == "__main__":
    unittest.main()
