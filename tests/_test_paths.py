"""Helpers that translate a pytest test node id into filesystem paths.

Used by ``tests/conftest.py`` to organise per-test evidence under
``reports/evidence/<sanitised_test_id>/<timestamp>/``.

Why this lives in its own module
--------------------------------
``conftest.py`` is already large and primarily concerned with fixture
plumbing. The string-munging logic for sanitising nodeids is small,
pure, easy to unit-test, and has no pytest dependencies - so it earns
its own file (Single Responsibility).
"""

from __future__ import annotations

import re
import time
from pathlib import Path

# Characters that the major filesystems (NTFS, APFS, ext4) all reject or
# treat specially. We replace each with a single underscore so the
# resulting path is portable and round-trippable.
_UNSAFE = re.compile(r"[\\/:\*\?\"<>\|\s\[\]]+")


def sanitise_nodeid(nodeid: str) -> str:
    """Convert ``tests/test_x.py::test_y[chromium-foo]`` into ``test_y_chromium-foo``.

    * Strips the module path before ``::`` (the file location is implicit
      from the conftest).
    * Replaces filesystem-unsafe characters with ``_``.
    * Collapses runs of underscores so we don't get ``foo___bar``.
    """
    after_module = nodeid.split("::", 1)[-1]
    cleaned = _UNSAFE.sub("_", after_module)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "unnamed_test"


def evidence_dir_for(reports_root: Path, nodeid: str, timestamp: float | None = None) -> Path:
    """Return ``reports_root/evidence/<sanitised>/<YYYYMMDD_HHMMSS>``.

    Does NOT create the directory - the caller decides when (typically in
    a fixture setup so the directory only appears for tests that actually
    run).
    """
    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime(timestamp))
    return reports_root / "evidence" / sanitise_nodeid(nodeid) / ts
