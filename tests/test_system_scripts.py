from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = REPO_ROOT / "install.sh"
DOCKER_LOGS_EXAMPLE = REPO_ROOT / "examples" / "allowed_scripts" / "docker_logs.sh"

# These scripts target macOS/Linux; CI covers bash execution on both.
requires_bash = pytest.mark.skipif(os.name == "nt", reason="bash scripts tested in CI on macOS/Linux")


def _bash() -> str:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash not available")
    return bash


def _run_script(script_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [_bash(), str(script_path), *args],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "LC_ALL": "C"},
    )


def _extract_script(script_name: str, marker: str) -> str:
    lines = INSTALL_SH.read_text().splitlines()
    start = None
    body: list[str] = []
    prefix = f'cat > "$BRIDGE_ROOT/scripts/{script_name}" <<\'{marker}\''

    for index, line in enumerate(lines):
        if line == prefix:
            start = index + 1
            break

    if start is None:
        raise AssertionError(f"Could not find {script_name} in install.sh")

    for line in lines[start:]:
        if line == marker:
            return "\n".join(body) + "\n"
        body.append(line)

    raise AssertionError(f"Could not find closing marker {marker} for {script_name}")


@pytest.fixture()
def docker_logs_script(tmp_path: Path) -> Path:
    script_path = tmp_path / "docker_logs.sh"
    script_path.write_text(_extract_script("docker_logs.sh", "DL"))
    script_path.chmod(0o755)
    return script_path


def test_docker_logs_example_matches_install_template() -> None:
    assert DOCKER_LOGS_EXAMPLE.read_text() == _extract_script("docker_logs.sh", "DL")


@requires_bash
def test_docker_logs_usage_missing_container(docker_logs_script: Path) -> None:
    result = _run_script(docker_logs_script)

    assert result.returncode == 2
    assert "Usage:" in result.stderr
    assert "CONTAINER" in result.stderr


@requires_bash
def test_docker_logs_rejects_invalid_lines(docker_logs_script: Path) -> None:
    result = _run_script(docker_logs_script, "my-container", "abc")

    assert result.returncode == 2
    assert "LINES must be a positive number" in result.stderr


@requires_bash
@pytest.mark.skipif(shutil.which("docker") is None, reason="docker CLI not installed")
def test_docker_logs_errors_when_daemon_unavailable(docker_logs_script: Path) -> None:
    result = subprocess.run(
        [_bash(), str(docker_logs_script), "missing-container"],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "DOCKER_HOST": "unix:///tmp/cowork-bridge-no-docker.sock", "LC_ALL": "C"},
    )

    assert result.returncode == 1
    assert "Docker daemon is not running" in result.stderr


@requires_bash
@pytest.mark.skipif(shutil.which("docker") is None, reason="docker CLI not installed")
def test_docker_logs_errors_when_container_missing(docker_logs_script: Path) -> None:
    if subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
        pytest.skip("Docker daemon is not running")

    result = _run_script(docker_logs_script, "cowork-bridge-nonexistent-container")

    assert result.returncode == 1
    assert "does not exist" in result.stderr
    assert "Existing containers:" in result.stderr


@requires_bash
@pytest.mark.skipif(shutil.which("docker") is None, reason="docker CLI not installed")
def test_docker_logs_prints_tail_when_container_exists(docker_logs_script: Path) -> None:
    if subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
        pytest.skip("Docker daemon is not running")

    name = "cowork-bridge-docker-logs-test"
    subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)
    create = subprocess.run(
        ["docker", "run", "-d", "--name", name, "alpine", "sleep", "300"],
        capture_output=True,
        text=True,
    )
    if create.returncode != 0:
        pytest.skip(f"could not create test container: {create.stderr.strip()}")

    try:
        result = _run_script(docker_logs_script, name, "5")
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)

    assert result.returncode == 0, result.stderr
    assert f"=== DOCKER LOGS: {name} (last 5 lines) ===" in result.stdout
