"""Release contract for the standalone Homeclaw HACS repository."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "custom_components" / "homeclaw" / "manifest.json"
HACS = ROOT / "hacs.json"


class HacsReleaseContractTest(unittest.TestCase):
    def test_repository_is_hacs_installable(self) -> None:
        self.assertTrue(HACS.is_file(), "hacs.json is required at the repository root")
        hacs = json.loads(HACS.read_text(encoding="utf-8"))
        self.assertEqual("Homeclaw", hacs["name"])
        self.assertTrue(hacs["render_readme"])

    def test_manifest_points_to_public_release_repository(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual("0.13.0", manifest["version"])
        self.assertEqual(
            "https://github.com/astyrrian1/homeclaw-ha",
            manifest["documentation"],
        )
        self.assertEqual(
            "https://github.com/astyrrian1/homeclaw-ha/issues",
            manifest["issue_tracker"],
        )

    def test_panel_exposes_v13_usefulness_contract(self) -> None:
        coordinator = (ROOT / "custom_components" / "homeclaw" / "coordinator.py").read_text()
        panel = (
            ROOT / "custom_components" / "homeclaw" / "frontend" / "homeclaw-panel.js"
        ).read_text()
        self.assertIn("/v1/situations?limit=100", coordinator)
        self.assertIn("/v1/cognition/value-funnel", coordinator)
        self.assertIn("/v1/reflections?limit=100", coordinator)
        self.assertIn("/v1/memory/backfills?limit=20", coordinator)
        self.assertIn("What Homeclaw added", panel)
        self.assertIn("Automatically qualified memory", panel)
        self.assertIn("90-day usefulness backfill", panel)
        self.assertIn("routeIdentity(data.inference_routes?.realtime)", panel)


if __name__ == "__main__":
    unittest.main()
