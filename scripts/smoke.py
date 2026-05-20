"""
Smoke test — generates YAML config templates and Markdown docs for every test
model and writes them to smoke_output/ so you can inspect the real output.

Usage:
    pdm run smoke               # via the PDM script alias
    pdm run python scripts/smoke.py   # directly
    python scripts/smoke.py     # with the project installed in your venv
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

# Allow running from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
os.environ.setdefault("PSYPLUS_SUPPRESS_ENV_WARNING", "true")

from pydantic_settings import BaseSettings

from psyplus import YamlSettingsPlus
from tests.models.nested import MultiNestedModel, NestedModel
from tests.models.readme_example import MyAppConfig
from tests.models.simple import SimpleModel

OUT_DIR = Path(__file__).resolve().parent.parent / "smoke_output"

MODELS: list[type[BaseSettings]] = [
    SimpleModel,
    NestedModel,
    MultiNestedModel,
    MyAppConfig,
]

PREVIEW_LINES = 30


def _rule(char: str = "─", width: int = 60) -> str:
    return char * width


def _preview(text: str, n: int = PREVIEW_LINES) -> str:
    lines = text.splitlines()
    snippet = "\n".join(lines[:n])
    if len(lines) > n:
        snippet += f"\n  … ({len(lines) - n} more lines)"
    return textwrap.indent(snippet, "  ")


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    print(f"\nSmoke output → {OUT_DIR}\n")

    for model_cls in MODELS:
        name = model_cls.__name__
        handler = YamlSettingsPlus(model_cls)

        yaml_text = handler.render_yaml()
        md_text = handler.render_markdown()

        yaml_path = OUT_DIR / f"{name}.yaml"
        md_path = OUT_DIR / f"{name}.md"

        yaml_path.write_text(yaml_text)
        md_path.write_text(md_text)

        print(_rule())
        print(f"  {name}")
        print(_rule())
        print(f"  YAML  → {yaml_path.name}  ({len(yaml_text.splitlines())} lines)")
        print(f"  MD    → {md_path.name}  ({len(md_text.splitlines())} lines)")
        print()
        print(_preview(yaml_text))
        print()

    print(_rule("═"))
    print(f"  Done. {len(MODELS)} models written to {OUT_DIR}")
    print(_rule("═"))


if __name__ == "__main__":
    main()
