#!/usr/bin/env python3
"""Creates BringYourOwnRecipe.app in the project directory.

Usage:
    python make_app.py          # or: uv run make_app.py
"""

import os
import shutil
import stat
import struct
import subprocess
import tempfile
import zlib

PROJECT = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(PROJECT, ".venv")
APP = os.path.join(PROJECT, "BringYourOwnRecipe.app")


# ── Icon ─────────────────────────────────────────────────────────────────────


def _png(size: int) -> bytes:
    """Render a shopping-bag icon (orange bg, white bag) as a PNG."""
    W = H = size
    orange = bytes([0xFF, 0x69, 0x00])
    white = bytes([0xFF, 0xFF, 0xFF])

    # Bag body: rounded rectangle
    bx1, bx2 = W * 0.18, W * 0.82
    by1, by2 = H * 0.38, H * 0.84
    br = W * 0.07

    # Handle: arc = upper half of an annulus centred on top edge of body
    hcx = W * 0.5
    hcy = H * 0.38  # circle centre sits on bag-top edge
    h_r2 = (W * 0.175) ** 2  # outer radius²
    h_r1 = (W * 0.105) ** 2  # inner radius²

    def in_rrect(x, y):
        if not (bx1 <= x <= bx2 and by1 <= y <= by2):
            return False
        if x < bx1 + br and y < by1 + br:
            return (x - (bx1 + br)) ** 2 + (y - (by1 + br)) ** 2 <= br * br
        if x > bx2 - br and y < by1 + br:
            return (x - (bx2 - br)) ** 2 + (y - (by1 + br)) ** 2 <= br * br
        if x < bx1 + br and y > by2 - br:
            return (x - (bx1 + br)) ** 2 + (y - (by2 - br)) ** 2 <= br * br
        if x > bx2 - br and y > by2 - br:
            return (x - (bx2 - br)) ** 2 + (y - (by2 - br)) ** 2 <= br * br
        return True

    rows: list[bytes] = []
    for y in range(H):
        row = bytearray()
        for x in range(W):
            d2 = (x - hcx) ** 2 + (y - hcy) ** 2
            in_handle = h_r1 <= d2 <= h_r2 and y <= hcy
            row += white if (in_rrect(x, y) or in_handle) else orange
        rows.append(bytes(row))

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return (
            struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFF_FFFF)
        )

    raw = bytearray()
    for row in rows:
        raw.append(0)  # filter = None
        raw.extend(row)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def _make_icns(dest: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        iconset = os.path.join(tmp, "AppIcon.iconset")
        os.makedirs(iconset)
        for size in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                px = size * scale
                name = f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png"
                with open(os.path.join(iconset, name), "wb") as f:
                    f.write(_png(px))
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", dest], check=True)


# ── Launcher script ───────────────────────────────────────────────────────────

LAUNCHER = f"""\
#!/bin/bash
osascript - "{PROJECT}" "{VENV}" <<'APPLESCRIPT'
on run argv
    set proj to item 1 of argv
    set venv to item 2 of argv
    tell application "Terminal"
        activate
        do script "cd " & quoted form of proj & " && source " & quoted form of venv & "/bin/activate && byor"
    end tell
end run
APPLESCRIPT
"""

INFO_PLIST = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
    <key>CFBundleExecutable</key>        <string>launch</string>
    <key>CFBundleIconFile</key>          <string>AppIcon</string>
    <key>CFBundleIdentifier</key>        <string>com.lukegre.bringyourownrecipe</string>
    <key>CFBundleName</key>              <string>BringYourOwnRecipe</string>
    <key>CFBundleDisplayName</key>       <string>BringYourOwnRecipe</string>
    <key>CFBundlePackageType</key>       <string>APPL</string>
    <key>CFBundleShortVersionString</key><string>1.0</string>
    <key>CFBundleVersion</key>           <string>1</string>
    <key>NSHighResolutionCapable</key>   <true/>
</dict></plist>
"""


# ── Build ─────────────────────────────────────────────────────────────────────


def main() -> None:
    if os.path.exists(APP):
        shutil.rmtree(APP)

    macos_dir = os.path.join(APP, "Contents", "MacOS")
    res_dir = os.path.join(APP, "Contents", "Resources")
    os.makedirs(macos_dir)
    os.makedirs(res_dir)

    with open(os.path.join(APP, "Contents", "Info.plist"), "w") as f:
        f.write(INFO_PLIST)

    launcher = os.path.join(macos_dir, "launch")
    with open(launcher, "w") as f:
        f.write(LAUNCHER)
    os.chmod(launcher, os.stat(launcher).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print("Rendering icon…")
    _make_icns(os.path.join(res_dir, "AppIcon.icns"))

    print(f"Created  {APP}")
    print("Open it: open BringYourOwnRecipe.app")
    print("To install: cp -r BringYourOwnRecipe.app /Applications/")


if __name__ == "__main__":
    main()
