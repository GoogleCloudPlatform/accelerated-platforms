#!/usr/bin/env python3
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Entrypoint for the 4-Act Red Team vs. Blue Team Mission Control console."""

import sys
from pathlib import Path

UI_PACKAGE_DIR = str(Path(__file__).resolve().parent)
if UI_PACKAGE_DIR not in sys.path:
    sys.path.insert(0, UI_PACKAGE_DIR)

from server import MissionControlHandler, run_server

__all__ = ["MissionControlHandler", "main", "run_server"]


def main() -> None:
    run_server()


if __name__ == "__main__":
    main()
