"""Create a standalone ZIP containing a validated Skill and its license."""

from __future__ import annotations

import argparse
from pathlib import Path
import zipfile

from validate_skills import NAME, REPO_ROOT, SKIP_DIRS, validate_skill


def package_skill(directory: Path, output: Path) -> Path:
    errors = validate_skill(directory)
    if errors:
        raise ValueError("; ".join(errors))
    directory = directory.resolve()
    output = output.resolve()
    if output.is_relative_to(directory):
        raise ValueError("output directory must be outside the Skill directory")
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"{directory.name}.zip"
    # Refuse silent replacement of an existing downloadable artifact.
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(directory.rglob("*")):
            relative = path.relative_to(directory)
            if any(part in SKIP_DIRS for part in relative.parts) or not path.is_file():
                continue
            bundle.write(path, Path(directory.name) / relative)
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill", help="directory name under skills/")
    parser.add_argument("--output", type=Path, default=Path("dist"))
    args = parser.parse_args()
    if not NAME.fullmatch(args.skill):
        parser.error("skill must be a lowercase directory name, without path separators")
    try:
        archive = package_skill(REPO_ROOT / "skills" / args.skill, args.output)
    except (ValueError, FileExistsError) as exc:
        parser.exit(1, f"FAIL: {exc}\n")
    print(f"PASS: created {archive.name} in the requested output directory")


if __name__ == "__main__":
    main()
