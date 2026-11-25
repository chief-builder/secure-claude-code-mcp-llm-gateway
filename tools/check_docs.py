"""Check the repository's Markdown: links, heading anchors and pasteable shell blocks.

Run:  uv run python tools/check_docs.py

Checked: inline links `[text](target)`, with or without a title or angle brackets.
Not checked: reference-style links, HTML links, links inside indented code blocks,
and web links. A `#` line inside a here-document in a shell block is reported even
though it would paste correctly; keep such lines out of shell blocks.
"""

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

SHELL_FENCES = {"sh", "bash", "zsh", "shell"}
# The target of an inline link, with optional angle brackets and an optional "title".
LINK = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
INLINE_CODE = re.compile(r"`[^`]*`")
FENCE = re.compile(r"(`{3,}|~{3,})\s*[{.]*([\w-]*)")
HEADING = re.compile(r"#{1,6}\s+(.*?)\s*#*$")
SCHEME = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*:")
SOURCE_LINE = re.compile(r"[Ll]\d+")


def lines_with_fences(text):
    """Yield (line number, line, fence language or None) for each line that is not a fence marker.

    A final (number, None, language) is yielded if a fence is still open at the end.
    """
    marker = language = opened = None
    for number, line in enumerate(text.splitlines(), 1):
        fence = FENCE.match(line.strip())
        if fence and marker is None:
            marker, language, opened = fence.group(1)[0], fence.group(2).lower(), number
            continue
        if fence and fence.group(1)[0] == marker and not fence.group(2):
            marker = language = None
            continue
        yield number, line, language
    if marker is not None:
        yield opened, None, language


def slug(heading):
    """The anchor GitHub gives a heading: lower case, punctuation dropped, spaces to hyphens."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading).strip().lower()
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def anchors(path):
    found, counts = set(), {}
    for _, line, language in lines_with_fences(path.read_text(encoding="utf-8")):
        match = HEADING.match(line) if language is None and line is not None else None
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
            if line is None:
                problems.append(f"{where}: code block is never closed, so the rest of the file is unchecked")
                continue
            if language is not None:
                if language in SHELL_FENCES and line.lstrip().startswith("#"):
                    problems.append(f"{where}: comment line in a shell block; the default "
                                    "macOS shell rejects it when pasted")
                continue
            for target in LINK.findall(INLINE_CODE.sub("", line)):
                if SCHEME.match(target) or target.startswith("<"):
                    continue
                checked += 1
                relative, _, fragment = target.partition("#")
                destination = (path.parent / unquote(relative)).resolve() if relative else path.resolve()
                if not destination.exists():
                    problems.append(f"{where}: link to a missing file: {target}")
                elif fragment and destination.suffix != ".md" and SOURCE_LINE.match(fragment):
                    problems.append(f"{where}: link to a source line, which goes stale: {target}")
                elif fragment and destination.suffix == ".md" and fragment.lower() not in anchors(destination):
                    problems.append(f"{where}: link to a missing heading: {target}")
    return problems, checked


def main():
    # Always check the whole repository, whatever directory this is run from.
    root = Path(__file__).resolve().parent.parent
    listed = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "-co", "--exclude-standard", "*.md"],
                            capture_output=True, text=True, check=True).stdout.split("\0")
    files = [root / name for name in listed if name and (root / name).is_file()]
    problems, checked = check(files)
    for problem in problems:
        print(problem.replace(f"{root}/", "", 1))
    print(f"{len(files)} Markdown files, {checked} relative links checked, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
