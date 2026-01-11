import ast
import pathlib
import sys


def _iter_python_files(root: pathlib.Path) -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for p in root.rglob("*.py"):
        # results folder is not part of repo runtime deps
        sp = str(p)
        if "RESULT_TASKS" in sp:
            continue
        # ignore archived/legacy code and demo app
        if "\\Old\\" in sp or "/Old/" in sp:
            continue
        if "\\Тестовый проект\\" in sp or "/Тестовый проект/" in sp:
            continue
        if "\\node_modules\\" in sp or "/node_modules/" in sp:
            continue
        files.append(p)
    return files


def _collect_top_level_names(root: pathlib.Path) -> set[str]:
    """
    Names that are likely 'local' to the repo and should not be treated as pip deps.
    """
    local: set[str] = set()

    # Any python file in the repo can be imported as a module if its folder is on sys.path.
    # So we treat ALL file stems as "local module names" to reduce false positives.
    for p in root.rglob("*.py"):
        sp = str(p)
        if "RESULT_TASKS" in sp:
            continue
        if "\\Old\\" in sp or "/Old/" in sp:
            continue
        if "\\Тестовый проект\\" in sp or "/Тестовый проект/" in sp:
            continue
        if "\\node_modules\\" in sp or "/node_modules/" in sp:
            continue
        local.add(p.stem)

    # Also include directory names (sometimes used as packages / import roots)
    for d in root.iterdir():
        if d.is_dir():
            local.add(d.name)

    return local


def _collect_import_roots(files: list[pathlib.Path]) -> set[str]:
    mods: set[str] = set()
    for p in files:
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(txt)
        except Exception:
            continue

        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    mods.add(a.name.split(".")[0])
            elif isinstance(n, ast.ImportFrom):
                # ignore relative imports: from .x import y
                if n.level != 0:
                    continue
                if n.module:
                    mods.add(n.module.split(".")[0])
    return mods


def main() -> int:
    root = pathlib.Path(__file__).resolve().parent

    files = _iter_python_files(root)
    mods = _collect_import_roots(files)

    stdlib = set(getattr(sys, "stdlib_module_names", ()))
    # fallback for older python: keep stdlib empty, we will still filter locals

    local = _collect_top_level_names(root)

    third_party = sorted(
        m
        for m in mods
        if m
        and m not in stdlib
        and m not in local
        # ignore typing_extensions (optional backport); we decide later
        and m not in {"typing_extensions"}
    )

    print("ROOT:", root)
    print("PY_FILES:", len(files))
    print("TOTAL_IMPORT_ROOTS:", len(mods))
    print("THIRD_PARTY_CANDIDATES:", len(third_party))
    print("---")
    for m in third_party:
        print(m)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


