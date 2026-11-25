"""Check the repository's Markdown: links, heading anchors and pasteable shell blocks.

Run from the repository root:  uv run python tools/check_docs.py
"""

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

SHELL_FENCES = {"sh", "bash", "zsh", "shell"}
LINK = re.compile(r"\]\(([^)\s]+)\)")
HEADING = re.compile(r"#{1,6}\s+(.*?)\s*#*$")
SCHEME = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*:")
SOURCE_LINE = re.compile(r"L\d+(-L\d+)?")


def lines_with_fences(text):
    """Yield (line number, line, fence language or None) for each line outside a fence marker."""
    language = None
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            language = None if language is not None else stripped[3:].strip().lower()
            continue
        yield number, line, language


def slug(heading):
    """The anchor GitHub gives a heading: lower case, punctuation dropped, spaces to hyphens."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading).strip().lower()
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def anchors(path):
    found, counts = set(), {}
    for _, line, language in lines_with_fences(path.read_text(encoding="utf-8")):
        match = HEADING.match(line) if language is None else None
        if match:
            name = slug(match.group(1))
            seen = counts.get(name, 0)
            counts[name] = seen + 1
            found.add(name if seen == 0 else f"{name}-{seen}")
    return found


def check(files):
    """Return (problems, number of relative links checked) for the given Markdown files."""
    problems, checked = [], 0
    for path in files:
        for number, line, language in lines_with_fences(path.read_text(encoding="utf-8")):
            where = f"{path}:{number}"
            if language is not None:
                if language in SHELL_FENCES and line.lstrip().startswith("#"):
                    problems.append(f"{where}: comment line in a shell block; the default "
                                    "macOS shell rejects it when pasted")
                continue
            for target in LINK.findall(line):
                if SCHEME.match(target) or target.startswith("<"):
                    continue
                checked += 1
                relative, _, fragment = target.partition("#")
                destination = (path.parent / unquote(relative)).resolve() if relative else path.resolve()
                if not destination.exists():
                    problems.append(f"{where}: link to a missing file: {target}")
                elif fragment and destination.suffix != ".md" and SOURCE_LINE.fullmatch(fragment):
                    problems.append(f"{where}: link to a source line, which goes stale: {target}")
                elif fragment and destination.suffix == ".md" and fragment.lower() not in anchors(destination):
                    problems.append(f"{where}: link to a missing heading: {target}")
    return problems, checked


def main():
    listed = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "*.md"],
                            capture_output=True, text=True, check=True).stdout.splitlines()
    files = [Path(name) for name in listed if Path(name).is_file()]
    problems, checked = check(files)
    for problem in problems:
        print(problem)
    print(f"{len(files)} Markdown files, {checked} relative links checked, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
