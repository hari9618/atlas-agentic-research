"""Prepare the hero media from the delivered asset folder.

Delivered: an empty-branch poster, a 5 s landing video whose FIRST frame is that
poster and whose LAST frame is the perched still, and the perched still itself. The
hero plays the video once and lets it rest on its last frame, so the "freeze" never
swaps media and the join cannot show.

Outputs (public/hero/):
  poster.webp   — what shows before playback (the empty branch)
  still.webp    — the perched still, for visitors who prefer reduced motion
  landing.webm  — VP9, served first (small)
  landing.mp4   — H.264 fallback (Safari), re-encoded with +faststart so it streams

Why there is no dark-theme video: a dark variant was derived by re-matting the sage
backdrop, but the wings' motion blur is tens of pixels wide and cannot be separated
from a light backdrop cleanly — it left pale halos. The video is shown unaltered in a
framed panel in both themes instead.

Usage (from apps/web):  python scripts/build_hero_media.py <assets-dir>
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

OUT = Path("public/hero")


def main(src: Path) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    Image.open(src / "00-empty-branch-poster-1920x1080.webp").save(OUT / "poster.webp")
    Image.open(src / "01-macaw-sage-2560x1440.webp").save(OUT / "still.webp")
    shutil.copyfile(src / "03-macaw-landing-1920x1080.webm", OUT / "landing.webm")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src / "03-macaw-landing-1920x1080.mp4"),
                    "-c:v", "libx264", "-preset", "slow", "-crf", "21", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", "-an", str(OUT / "landing.mp4")], check=True)
    for p in sorted(OUT.glob("*")):
        print(f"{p}: {p.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
