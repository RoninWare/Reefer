"""Package the pinned Reef Glass release from Git and verified local LFS images."""
import hashlib
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / "upstream/reef_glass_roku_screensaver"
REV = "270f1b06c4b5e5f4279dc12815e16121388659c6"
PREFIX = "roku/reefglass/"


def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args])


def content(path):
    data = git("show", f"{REV}:{path}")
    if data.startswith(b"version https://git-lfs.github.com/spec/v1"):
        digest = re.search(rb"oid sha256:([0-9a-f]{64})", data)[1].decode()
        data = (REPO / path).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f"Missing or incorrect LFS content for {path}. Run git lfs pull.")
    return data


def main():
    paths = git("ls-tree", "-r", "--name-only", REV, PREFIX).decode().splitlines()
    entries = {p[len(PREFIX):]: p for p in paths if p != PREFIX + "source/dev.brs"}
    entries.update({name: name for name in ("LICENSE", "LICENSE-ART", "CREDITS.md")})
    out = ROOT / "baseline/reefglass-1.1.3.zip"
    out.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as staging:
        temp = Path(staging) / out.name
        with zipfile.ZipFile(temp, "w") as archive:
            for name, path in sorted(entries.items()):
                data = content(path)
                if name == "manifest":
                    data = re.sub(rb"^title=.*\n", b"", data, flags=re.M)
                    data += b"run_screensaver=RunScreenSaver\nrun_screensaver_settings=RunScreenSaverSettings\nhidden=1\n"
                info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data, zipfile.ZIP_DEFLATED, compresslevel=6)
        temp.replace(out)
    print(hashlib.sha256(out.read_bytes()).hexdigest(), out.relative_to(ROOT))


if __name__ == "__main__":
    main()
