#!/usr/bin/env python3
"""Download the GSI geoid model「日本のジオイド2011」into ``$DATA_DIR/geoid/``.

Fetches the GSIGEO2011 ASCII grid (used by the ellipsoidal-height branch of
:class:`topobathy.datum.geoid.GeoidModel`) directly from GSI — **no login** — and
unzips the ``gsigeo2011_ver2_2.asc`` grid to ``$DATA_DIR/geoid/``. The T.P.
conversion of M7001 does not need this; it is only for producing/consuming
**ellipsoidal** heights (GNSS / ERS).

The GSI server negotiates TLS the legacy way, which OpenSSL 3 blocks by default, so
we enable ``OP_LEGACY_SERVER_CONNECT`` explicitly.

Source (public direct download): https://www.gsi.go.jp/buturisokuchi/grageo_reference.html

Usage:
    python scripts/get_gsigeo.py
"""

from __future__ import annotations

import io
import os
import ssl
import sys
import urllib.request
import zipfile
from pathlib import Path

# GSIGEO2011 Ver.2.2 (2023-06-02–2025-03-31) ASCII grid, direct GSI download.
URL = "https://www.gsi.go.jp/common/000275008.zip"
ASC_NAME = "gsigeo2011_ver2_2.asc"


def _ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
    return ctx


def main() -> int:
    data_dir = os.environ.get("DATA_DIR")
    if not data_dir:
        sys.exit("ERROR: DATA_DIR unset")
    out_dir = Path(data_dir) / "geoid"
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / ASC_NAME
    if dest.is_file():
        print(f"already present: {dest}")
        return 0

    print(f"downloading {URL} ...", flush=True)
    req = urllib.request.Request(URL, headers={"User-Agent": "topobathy/0.1"})
    with urllib.request.urlopen(
        req, timeout=120, context=_ssl_ctx()
    ) as r:  # noqa: S310
        blob = r.read()
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        member = next(n for n in zf.namelist() if n.endswith(ASC_NAME))
        with zf.open(member) as src, dest.open("wb") as out:
            out.write(src.read())
    print(f"wrote {dest} ({dest.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
