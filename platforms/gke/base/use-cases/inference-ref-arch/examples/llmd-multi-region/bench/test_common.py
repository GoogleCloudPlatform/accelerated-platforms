#!/usr/bin/env python3
#
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for _common.py."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

UTC = timezone.utc


class CommonTest(unittest.TestCase):
    def test_parse_rfc3339_and_epoch_seconds(self) -> None:
        self.assertEqual(
            _common.parse_rfc3339("2026-10-30T12:00:00.25Z"),
            _common.parse_rfc3339("2026-10-30T14:00:00.25+02:00"),
        )
        self.assertEqual(
            _common.parse_rfc3339("2026-10-30T07:28:19.123456789Z").microsecond,
            123457,
        )
        naive = datetime(2026, 10, 30, 5, 48)
        aware = datetime(2026, 10, 30, 7, 48, tzinfo=timezone(timedelta(hours=2)))
        self.assertEqual(_common.parse_rfc3339(naive), naive.replace(tzinfo=UTC))
        self.assertEqual(_common.epoch_seconds(aware), _common.epoch_seconds(naive))
        self.assertAlmostEqual(
            _common.epoch_seconds("2026-10-30T02:00:00.000000123Z") or 0.0,
            (_common.epoch_seconds("2026-10-30T02:00:00Z") or 0.0) + 123e-9,
            places=6,
        )
        self.assertEqual(_common.epoch_seconds(12.5), 12.5)
        self.assertIsNone(_common.epoch_seconds(None))
        self.assertIsNone(_common.epoch_seconds(""))
        self.assertIsNone(_common.epoch_seconds(True))
        self.assertIsNone(_common.epoch_seconds(["bad"]))
        self.assertIsNone(_common.epoch_seconds("30 Oct 2026", strict=False))
        with self.assertRaisesRegex(ValueError, "invalid RFC 3339 timestamp"):
            _common.parse_rfc3339("30/10/2026")
        with self.assertRaisesRegex(ValueError, "invalid RFC 3339 timestamp"):
            _common.epoch_seconds("Oct 30 2026")

    def test_load_json_and_formatters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = os.path.join(tmp, "missing.json")
            self.assertEqual(_common.load_json(missing, {"ok": True}), {"ok": True})
            present = os.path.join(tmp, "doc.json")
            with open(present, "w", encoding="utf-8") as f:
                f.write('{"n": 3}')
            self.assertEqual(_common.load_json(present), {"n": 3})

        self.assertEqual(_common.fmt_num(None), "-")
        self.assertEqual(_common.fmt_num(float("nan")), "-")
        self.assertEqual(_common.fmt_num(True, bool_yn=True), "yes")
        self.assertEqual(_common.fmt_num(False, bool_yn=True), "no")
        self.assertEqual(_common.fmt_num(3.14159, 2), "3.14")
        self.assertEqual(_common.fmt_duration(None), "–")
        self.assertEqual(_common.fmt_duration(360), "6:00")
        self.assertEqual(_common.fmt_duration(-75), "-1:15")
        self.assertEqual(_common.fmt_duration(3661, split_hours=True), "1:01:01")
        self.assertEqual(_common.fmt_duration(-3661, split_hours=True), "-1:01:01")
        self.assertEqual(
            _common.md_table(["a", "b"], [[1, 2.5]], cell_fmt=_common.fmt_num),
            "| a | b |\n|---|---|\n| 1 | 2.5 |",
        )


if __name__ == "__main__":
    unittest.main()
