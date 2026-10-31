"""Explicit, resumable, checksum-verified model acquisition.

Run once before starting the two long-lived services. Downloads ONNX weights
converted from official ZhengPeng7/BiRefNet_lite. Never executes HF remote code.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import os
import shutil
import sys
from pathlib import Path

from app.config import Settings


def digest(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def download(settings: Settings, *, verify_only: bool = False) -> None:
    target = settings.model_path
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_path = target.with_suffix(target.suffix + ".lock")
    # Two deploy commands must never overwrite the same temporary file concurrently.
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if target.exists() and digest(target) == settings.model_sha256:
            print(f"READY: verified cached model at {target}")
            return
        if verify_only:
            raise SystemExit(f"Missing or unverified model at {target}")
        from huggingface_hub import hf_hub_download

        print(f"Downloading {settings.model_repo}@{settings.model_revision}/{settings.model_filename}")
        source = Path(hf_hub_download(repo_id=settings.model_repo, filename=settings.model_filename,
                                      revision=settings.model_revision,
                                      cache_dir=os.getenv("HF_HUB_CACHE", "/models/.hf-hub")))
        actual = digest(source)
        if actual != settings.model_sha256:
            raise RuntimeError(f"Downloaded file SHA256 mismatch: {actual}; expected {settings.model_sha256}")
        temporary = target.with_suffix(target.suffix + ".partial")
        try:
            shutil.copyfile(source, temporary)
            if digest(temporary) != settings.model_sha256:
                raise RuntimeError("Copied model failed verification")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        print(f"READY: model cached at {target}; sha256={actual}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    try:
        download(Settings.from_env(), verify_only=args.verify_only)
    except Exception as exc:
        print(f"MODEL ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
