"""Export a clean GitHub source folder and ZIP using only Python's stdlib."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = (
    ".gitignore", "LICENSE", "README.md", "README_MAC.md", "TEST_REPORT.md",
    "DRAG_IMPLEMENTATION.md", "THIRD_PARTY_NOTICES.md", "PUBLISHING.md",
    "requirements.txt", "requirements.lock.txt", "setup.sh", "start.sh",
    "ai_virtual_painter.py", "chinese_text.py", "config.py", "controls.py",
    "doctor.py", "drawing_objects.py", "flower_animation.py", "gesture_time.py",
    "hand_interaction.py", "hand_utils.py", "mac_camera.py", "mac_window.py",
    "painter_core.py", "particles.py", "preferences.py", "run_app.py", "ui.py",
    "ui_labels.py",
)
SOURCE_DIRS = ("scripts", "tests", "third_party", "upstream", "docs")
SOURCE_SUFFIXES = {".py", ".sh", ".m", ".md", ".txt", ".png"}


def source_files():
    files = [ROOT / name for name in ROOT_FILES]
    for directory in SOURCE_DIRS:
        files.extend(path for path in (ROOT / directory).rglob("*")
                     if path.is_file() and not any(part.startswith(".") or part == "__pycache__"
                                                  for part in path.relative_to(ROOT).parts)
                     and (path.suffix in SOURCE_SUFFIXES or path.name.endswith("-LICENSE")))
    for path in files:
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"源码缺失或是符号链接：{path.relative_to(ROOT)}")
    return sorted(files)


def main():
    files = source_files()
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    name = "air-painter-mac-source-" + datetime.now().strftime("%Y-%m-%d")
    if (dist / name).exists() or (dist / (name + ".zip")).exists():
        name += "-" + datetime.now().strftime("%H%M%S-%f")
    export, archive = dist / name, dist / (name + ".zip")
    with tempfile.TemporaryDirectory(prefix=".source-", dir=dist) as temporary:
        folder = Path(temporary) / "air-painter-mac"
        folder.mkdir()
        hashes = []
        for source in files:
            relative = source.relative_to(ROOT)
            target = folder / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            hashes.append(f"{digest}  {relative.as_posix()}")
        (folder / "SOURCE_MANIFEST.sha256").write_text("\n".join(hashes) + "\n")
        with ZipFile(archive, "w", ZIP_DEFLATED, compresslevel=9) as package:
            for path in sorted(folder.rglob("*")):
                if path.is_file():
                    package.write(path, path.relative_to(Path(temporary)))
        # Keep a ready-to-upload source folder alongside the archive.
        Path(temporary).rename(export)
    checksum = archive.with_name(archive.name + ".sha256")
    checksum.write_text(f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n")
    print(json.dumps(dict(archive=str(archive), source_folder=str(export / "air-painter-mac"),
                         checksum=str(checksum), source_files=len(files),
                         archive_bytes=archive.stat().st_size), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
