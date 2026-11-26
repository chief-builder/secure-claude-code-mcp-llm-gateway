"""Guard the import path that lets components import each other.

The four component directories are added to the path by the project's editable
install. They come after installed packages, so a dependency that shipped a module
called `gateway` or `exchange` would silently replace the lab's own. These tests
turn that, and a mistyped directory, into a failure.
"""

import importlib.util
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIRECTORIES = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["hatch"]["build"]["dev-mode-dirs"]


def modules():
    return [path for directory in DIRECTORIES for path in sorted((ROOT / directory).glob("*.py"))]


def test_every_listed_directory_exists():
    assert DIRECTORIES and all((ROOT / directory).is_dir() for directory in DIRECTORIES)


def test_module_names_are_unique_across_components():
    names = [path.stem for path in modules()]
    assert len(names) == len(set(names))


def test_every_component_module_resolves_to_its_own_file():
    for path in modules():
        found = importlib.util.find_spec(path.stem)
        assert found is not None and Path(found.origin) == path, f"{path.stem} resolves to {found and found.origin}"
