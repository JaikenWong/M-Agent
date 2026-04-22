from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from magent_tui.workspace_tools import WorkspaceToolset


class WorkspaceToolsetTest(unittest.TestCase):
    def test_write_read_list(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tools = WorkspaceToolset.for_agent(root, "PM", "PM")
            tools.write_text_file("docs/a.md", "hello")
            self.assertEqual(tools.read_text_file("docs/a.md"), "hello")
            listing = tools.list_workspace_files(".")
            self.assertIn("docs/", listing)
            self.assertIn("docs/a.md", listing)

    def test_path_escape_not_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tools = WorkspaceToolset.for_agent(root, "PM", "PM")
            with self.assertRaises(ValueError):
                tools.write_text_file("../escape.txt", "x")

