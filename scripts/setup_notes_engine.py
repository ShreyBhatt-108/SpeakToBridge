"""Install the pinned official CPU-only llama.cpp completion runtime for packaging."""

from __future__ import annotations
import argparse, hashlib, json, urllib.request, zipfile
from pathlib import Path

URL = "https://github.com/ggml-org/llama.cpp/releases/download/b11723/llama-b11723-bin-win-cpu-x64.zip"
SHA256 = "d2c028bca1b948cb12a23008b6e37c37bea51459c0cb4fbed7a989133c244db0"
REQUIRED = {
    "llama-completion.exe",
    "llama-completion-impl.dll",
    "llama-common.dll",
    "llama.dll",
    "ggml.dll",
    "ggml-base.dll",
    "libomp.dll",
    "LICENSE-LLVM-OpenMP",
}


def setup(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    archive = output.parent / "llama-b11723-bin-win-cpu-x64.zip"
    if (
        not archive.is_file()
        or hashlib.file_digest(archive.open("rb"), "sha256").hexdigest() != SHA256
    ):
        temporary = archive.with_suffix(".zip.part")
        with (
            urllib.request.urlopen(URL, timeout=60) as response,  # nosec B310
            temporary.open("wb") as target,
        ):
            while chunk := response.read(1024 * 1024):
                target.write(chunk)
        with temporary.open("rb") as handle:
            if hashlib.file_digest(handle, "sha256").hexdigest() != SHA256:
                raise RuntimeError("Notes runtime checksum mismatch")
        temporary.replace(archive)
    files = {}
    with zipfile.ZipFile(archive) as bundle:
        available = set(bundle.namelist())
        if not REQUIRED.issubset(available):
            raise RuntimeError("Required notes runtime files missing")
        names = REQUIRED | {
            name
            for name in available
            if name.startswith("ggml-cpu-") and name.endswith(".dll")
        }
        for name in sorted(names):
            if Path(name).name != name:
                raise ValueError("Unsafe notes runtime archive member")
            data = bundle.read(name)
            (output / name).write_bytes(data)
            files[name] = hashlib.sha256(data).hexdigest()
    with urllib.request.urlopen(  # nosec B310
        "https://raw.githubusercontent.com/ggml-org/llama.cpp/b11723/LICENSE",
        timeout=30,
    ) as response:
        (output / "LICENSE-llama.cpp").write_bytes(response.read())
    (output / "runtime-manifest.json").write_text(
        json.dumps(
            dict(version="b11723", archive_sha256=SHA256, files=files), indent=2
        ),
        encoding="utf-8",
    )
    print("CPU notes runtime ready:", output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    setup(parser.parse_args().output)
