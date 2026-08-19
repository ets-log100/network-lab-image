#!/usr/bin/env python3
"""Unit tests for generic LOG100 networking utilities."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.linkemu = load_module("linkemu", ROOT / "images/link/linkemu.py")
        cls.netprobe = load_module("netprobe", ROOT / "images/toolbox/netprobe.py")

    def test_parse_maps(self) -> None:
        value = "5201=server:5201,8080=web:8080"
        self.assertEqual(
            list(self.linkemu.parse_maps(value)),
            [(5201, "server", 5201), (8080, "web", 8080)],
        )

    def test_probe_summary(self) -> None:
        result = self.netprobe.summarize(5, [10.0, 12.0, 11.0, 13.0])
        self.assertEqual(result["received"], 4)
        self.assertEqual(result["lost"], 1)
        self.assertAlmostEqual(result["loss_percent"], 20.0)
        self.assertAlmostEqual(result["rtt_avg_ms"], 11.5)
        self.assertAlmostEqual(result["jitter_mean_abs_ms"], 5.0 / 3.0)

    def test_delay_stays_non_negative(self) -> None:
        conditions = self.linkemu.Conditions(5.0, 20.0, 10.0, 0.0, 123)
        model = self.linkemu.DelayModel(conditions)
        self.assertTrue(all(model.delay_seconds() >= 0 for _ in range(100)))


if __name__ == "__main__":
    unittest.main()
