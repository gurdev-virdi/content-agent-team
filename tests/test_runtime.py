import tempfile
import unittest
from pathlib import Path

from scripts import runtime
from scripts.mission_control import app as mission_app


class RuntimeConfigTests(unittest.TestCase):
    def test_project_root_resolves_from_nested_script_path(self):
        nested = runtime.PROJECT_DIR / "scripts" / "mission_control" / "app.py"
        self.assertEqual(runtime.find_project_root(nested), runtime.PROJECT_DIR)

    def test_env_file_values_are_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("TEST_MODE=true\nCLAUDE_BIN=/tmp/claude\n")
            env = runtime.load_env(root)
            self.assertEqual(env["TEST_MODE"], "true")
            self.assertEqual(runtime.claude_bin(env), "/tmp/claude")

    def test_team_paths_are_derived_from_project_dir(self):
        team = {"id": "demo", "name": "Demo", "project_dir": str(runtime.PROJECT_DIR)}
        paths = runtime.team_paths(team)
        self.assertEqual(paths.pending, runtime.PROJECT_DIR / "output" / "pending")
        self.assertEqual(paths.logs, runtime.PROJECT_DIR / "logs")


class MissionControlTests(unittest.TestCase):
    def test_default_team_status_is_resilient(self):
        status = mission_app.get_system_status("animals-thriving")
        self.assertEqual(status["team"]["id"], "animals-thriving")
        self.assertIn("daemon", status)
        self.assertIn("kill_switch", status)


if __name__ == "__main__":
    unittest.main()
