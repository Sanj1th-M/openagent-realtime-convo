from __future__ import annotations

import tomllib
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_pytest_configuration_is_strict_and_scoped_to_tests() -> None:
    with (REPOSITORY_ROOT / "pyproject.toml").open("rb") as config_file:
        configuration = tomllib.load(config_file)

    pytest_config = configuration["tool"]["pytest"]["ini_options"]

    assert pytest_config["testpaths"] == ["tests"]
    assert "--strict-config" in pytest_config["addopts"]
    assert "--strict-markers" in pytest_config["addopts"]


def test_gitignore_excludes_local_credentials() -> None:
    ignored_patterns = (REPOSITORY_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert ".env" in ignored_patterns
    assert "*.pem" in ignored_patterns
    assert "*.key" in ignored_patterns
