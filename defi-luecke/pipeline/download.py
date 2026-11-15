"""Small download helper shared by the fetch modules."""

from __future__ import annotations

import logging
from pathlib import Path

import requests

log = logging.getLogger(__name__)

CONNECT_TIMEOUT_S = 15
READ_TIMEOUT_S = 120


class DownloadError(Exception):
    """Download failed. The message is German and shown to the user."""


def download_file(url: str, dest: Path) -> Path:
    """Stream ``url`` to ``dest`` (via a ``.part`` file). Skips nothing: callers check first."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    log.info("Lade herunter: %s", url)
    try:
        with requests.get(url, stream=True, timeout=(CONNECT_TIMEOUT_S, READ_TIMEOUT_S)) as resp:
            resp.raise_for_status()
            with part.open("wb") as fh:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    fh.write(chunk)
    except requests.RequestException as exc:
        part.unlink(missing_ok=True)
        raise DownloadError(
            f"Download fehlgeschlagen: {url}\n  Ursache: {exc}\n"
            f"  Manueller Schritt: Datei im Browser herunterladen und unter {dest} ablegen "
            "(siehe data/raw/SOURCES.md)."
        ) from exc
    part.replace(dest)
    log.info("Gespeichert: %s (%.1f MB)", dest, dest.stat().st_size / 1e6)
    return dest
