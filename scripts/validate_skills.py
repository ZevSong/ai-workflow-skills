"""Validate repository-owned Skill files without invoking an agent or network."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})(.*)$")
LINK = re.compile(r"!?\[[^\]\n]*\]\((<[^>\n]+>|[^\s)]+)(?:\s+[\"'][^\n]*?[\"'])?\)")
MACHINE_PATH = re.compile(
    r"(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/]|\\\\[A-Za-z0-9._-]+\\|file://|/(?:Users|home|mnt|tmp)/)"
)
SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules"}


def markdown_body(text: str) -> tuple[str, bool]:
    """Omit fenced examples and inline code when checking Markdown links."""
    marker = ""
    width = 0
    body = []
    for line in text.splitlines():
        match = FENCE.match(line)
        if match:
            run, tail = match.groups()
            if not marker:
                marker, width = run[0], len(run)
            elif run[0] == marker and len(run) >= width and not tail.strip():
                marker = ""
            continue
        if not marker:
            body.append(line)
    return re.sub(r"(`+).*?\1", "", "\n".join(body)), not marker


def markdown_errors(path: Path, boundary: Path) -> list[str]:
    label = path.relative_to(boundary).as_posix()
    text = path.read_text(encoding="utf-8-sig")
    errors = []
    if MACHINE_PATH.search(text):
        errors.append(f"{label}: machine-specific absolute path")
    body, closed = markdown_body(text)
    if not closed:
        errors.append(f"{label}: unclosed code fence")
    for match in LINK.finditer(body):
        target = match.group(1).strip("<>")
        # Generation templates may contain explicitly variable destinations.
        if "{{" in target:
            continue
        parts = urlsplit(target)
        if parts.scheme in {"http", "https", "mailto"}:
            continue
        if parts.scheme or parts.netloc or target.startswith(("/", "\\")):
            errors.append(f"{label}: non-relative local link {target}")
            continue
        if not parts.path:
            continue
        destination = (path.parent / unquote(parts.path)).resolve()
        if not destination.is_relative_to(boundary.resolve()):
            errors.append(f"{label}: link escapes standalone directory: {target}")
        elif not destination.exists():
            errors.append(f"{label}: missing link target: {target}")
    return errors


def validate_skill(directory: Path) -> list[str]:
    directory = directory.resolve()
    errors = []
    for name in ("SKILL.md", "README.md", "LICENSE"):
        if not (directory / name).is_file():
            errors.append(f"{directory.name}: missing {name}")
    examples = directory / "examples"
    if not examples.is_dir() or not any(examples.rglob("*.md")):
        errors.append(f"{directory.name}: examples must include Markdown input/behavior documentation")
    entry = directory / "SKILL.md"
    if entry.is_file():
        text = entry.read_text(encoding="utf-8-sig")
        match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", text, re.S)
        try:
            meta = yaml.safe_load(match.group(1)) if match else None
            if not isinstance(meta, dict):
                raise ValueError("missing YAML frontmatter mapping")
            name = meta.get("name", "")
            if not isinstance(name, str) or not NAME.fullmatch(name) or len(name) > 64:
                errors.append(f"{directory.name}: invalid Skill name")
            elif name != directory.name:
                errors.append(f"{directory.name}: name must match directory")
            description = meta.get("description")
            if not isinstance(description, str) or not 1 <= len(description.strip()) <= 1024:
                errors.append(f"{directory.name}: description must contain 1-1024 characters")
            if "compatibility" in meta and (
                not isinstance(meta["compatibility"], str) or not 1 <= len(meta["compatibility"]) <= 500
            ):
                errors.append(f"{directory.name}: invalid compatibility field")
            if "metadata" in meta and (
                not isinstance(meta["metadata"], dict)
                or not all(isinstance(k, str) and isinstance(v, str) for k, v in meta["metadata"].items())
            ):
                errors.append(f"{directory.name}: metadata must map strings to strings")
        except (yaml.YAMLError, ValueError) as exc:
            errors.append(f"{directory.name}: invalid frontmatter ({exc})")
    for path in directory.rglob("*"):
        relative = path.relative_to(directory)
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        if path.is_symlink():
            errors.append(f"{relative.as_posix()}: symlinks are not included in standalone distribution")
        elif path.is_file() and path.suffix == ".md":
            errors.extend(markdown_errors(path, directory))
            if "assets" not in relative.parts and re.search(r"\{\{[^\n]+?\}\}", path.read_text(encoding="utf-8-sig")):
                errors.append(f"{relative.as_posix()}: unresolved template variable outside assets")
    config = directory / "agents" / "openai.yaml"
    if config.exists():
        try:
            data = yaml.safe_load(config.read_text(encoding="utf-8-sig"))
            if not isinstance(data, dict):
                raise ValueError("expected mapping")
            policy = data.get("policy", {})
            if not isinstance(policy, dict):
                raise ValueError("policy must be a mapping")
            if "allow_implicit_invocation" in policy and not isinstance(policy["allow_implicit_invocation"], bool):
                raise ValueError("allow_implicit_invocation must be a boolean")
            interface = data.get("interface", {})
            if not isinstance(interface, dict):
                raise ValueError("interface must be a mapping")
            short = interface.get("short_description")
            if short is not None and (not isinstance(short, str) or not 25 <= len(short) <= 64):
                raise ValueError("short_description must contain 25-64 characters")
        except (yaml.YAMLError, ValueError) as exc:
            errors.append(f"{directory.name}: invalid agents/openai.yaml ({exc})")
    return errors


def validate_repository(root: Path) -> list[str]:
    errors = []
    skills = root / "skills"
    if not skills.is_dir():
        return ["missing skills directory"]
    directories = sorted(path for path in skills.iterdir() if path.is_dir())
    if not directories:
        errors.append("no skills found")
    for directory in directories:
        errors.extend(validate_skill(directory))
    # Root docs can refer to other repository files; Skills cannot.
    for path in root.glob("*.md"):
        errors.extend(markdown_errors(path, root))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", type=Path, help="validate one standalone Skill directory")
    args = parser.parse_args()
    errors = validate_skill(args.skill) if args.skill else validate_repository(REPO_ROOT)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: Skill metadata, local file links, fences, standalone boundaries, and portable paths")
    print("Scope: static files only; no remote-link, Markdown-anchor, Mermaid-rendering, or agent-execution validation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
