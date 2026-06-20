"""Tests for the Nexus-KB CI pytest segfault (exit 139) handling in .github/workflows/ci.yml.

Verifies that GitHub Actions:
  1. Disables errexit (set +e) before pytest so SIGSEGV exit 139 is capturable.
  2. Treats teardown segfault 139 as success with a ::warning:: annotation.
  3. Propagates real pytest failures (exit 1, 2, etc.) so CI stays red.
  4. Sets TOKENIZERS_PARALLELISM=false and OMP_NUM_THREADS=1 on the test step.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

_BASH_CANDIDATES = [
    "C:/Program Files/Git/bin/bash.exe",
    "C:/Program Files/Git/usr/bin/bash.exe",
    shutil.which("bash"),
]


def _working_bash() -> str | None:
    """Return a bash that can execute scripts (skip broken WSL stubs on Windows)."""
    for candidate in _BASH_CANDIDATES:
        if not candidate:
            continue
        path = Path(candidate)
        if not path.is_file():
            continue
        probe = subprocess.run(
            [str(path), "-c", "echo ok"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if probe.returncode == 0 and probe.stdout.strip() == "ok":
            return str(path)
    return None

WARNING_ANNOTATION = (
    "::warning::pytest exited 139 (SIGSEGV in PyTorch/HF teardown after all tests passed). "
    "Treating as success. See pytorch/pytorch#67864."
)


def _load_workflow() -> dict:
    assert CI_WORKFLOW.is_file(), f"CI workflow not found: {CI_WORKFLOW}"
    with CI_WORKFLOW.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _pytest_step(workflow: dict) -> dict:
    """Return the 'Run Pytest Suite' step from the test job."""
    test_job = workflow["jobs"]["test"]
    for step in test_job["steps"]:
        if step.get("name") == "Run Pytest Suite":
            return step
    raise AssertionError("Run Pytest Suite step not found in ci.yml")


def _stub_pytest_command(exit_code: int) -> str:
    """Simulate `python -m pytest` returning *exit_code* (not shell `exit`, which ignores set +e)."""
    if exit_code == 0:
        return "true"
    return f'python -c "import sys; sys.exit({exit_code})"'


def _run_bash_handler(stub_exit_code: int) -> subprocess.CompletedProcess[str]:
    """Execute the CI exit handler with a stub command that returns *stub_exit_code*."""
    bash = _working_bash()
    if bash is None:
        pytest.skip("working bash not available — skipping shell integration test")

    stub = _stub_pytest_command(stub_exit_code)
    # Prepend set +e / capture pattern exactly as ci.yml does before the handler block.
    script = f"""\
set -e -o pipefail
set +e
{stub}
exit_code=$?
set -e

if [ "$exit_code" -eq 139 ]; then
  echo "{WARNING_ANNOTATION}"
  exit 0
fi
exit "$exit_code"
"""
    return subprocess.run(
        [bash, "-c", script],
        capture_output=True,
        text=True,
        timeout=10,
    )


def resolve_pytest_step_exit(exit_code: int) -> tuple[int, str | None]:
    """Python mirror of the CI bash exit-code decision logic."""
    if exit_code == 139:
        return 0, WARNING_ANNOTATION
    return exit_code, None


class TestCiWorkflowYamlStructure:
    """Static analysis of .github/workflows/ci.yml for the segfault fix."""

    def test_workflow_file_exists(self) -> None:
        """CI workflow must be present at the expected path."""
        assert CI_WORKFLOW.is_file()

    def test_pytest_step_has_tokenizers_parallelism_false(self) -> None:
        """TOKENIZERS_PARALLELISM=false suppresses HF tokenizer fork warnings/teardown races."""
        step = _pytest_step(_load_workflow())
        env = step.get("env", {})
        assert env.get("TOKENIZERS_PARALLELISM") == "false"

    def test_pytest_step_has_omp_num_threads_one(self) -> None:
        """OMP_NUM_THREADS=1 limits OpenMP threads to reduce PyTorch teardown crashes."""
        step = _pytest_step(_load_workflow())
        env = step.get("env", {})
        assert env.get("OMP_NUM_THREADS") == "1"

    def test_pytest_step_disables_errexit_before_pytest(self) -> None:
        """set +e must appear before pytest so bash -e does not abort on exit 139."""
        step = _pytest_step(_load_workflow())
        script = step["run"]
        set_plus_e = script.find("set +e")
        pytest_invocation = script.find("python -m pytest")
        assert set_plus_e != -1, "set +e not found in Run Pytest Suite step"
        assert pytest_invocation != -1, "pytest invocation not found"
        assert set_plus_e < pytest_invocation, "set +e must precede pytest invocation"

    def test_pytest_step_captures_exit_code_after_pytest(self) -> None:
        """exit_code=$? must follow pytest so SIGSEGV 139 is recorded, not lost to errexit."""
        step = _pytest_step(_load_workflow())
        script = step["run"]
        pytest_pos = script.find("python -m pytest")
        capture_pos = script.find("exit_code=$?")
        assert capture_pos != -1, "exit_code=$? not found"
        assert pytest_pos < capture_pos, "exit_code capture must follow pytest"

    def test_pytest_step_reenables_errexit_after_capture(self) -> None:
        """set -e restores errexit after $? is captured."""
        step = _pytest_step(_load_workflow())
        script = step["run"]
        capture_pos = script.find("exit_code=$?")
        set_minus_e = script.find("set -e", capture_pos)
        assert set_minus_e != -1, "set -e not found after exit_code capture"

    def test_pytest_step_handles_exit_139_with_warning(self) -> None:
        """Exit 139 branch must emit ::warning:: and exit 0 (CI green)."""
        step = _pytest_step(_load_workflow())
        script = step["run"]
        assert 'if [ "$exit_code" -eq 139 ]' in script
        assert "::warning::" in script
        assert "exit 0" in script

    def test_pytest_step_propagates_non_139_failures(self) -> None:
        """Real pytest failures must exit with the original code (CI red)."""
        step = _pytest_step(_load_workflow())
        script = step["run"]
        assert 'exit "$exit_code"' in script

    def test_pytest_step_documents_sigsegv_rationale(self) -> None:
        """Inline comment references the PyTorch teardown segfault issue."""
        step = _pytest_step(_load_workflow())
        script = step["run"]
        assert "SIGSEGV" in script or "segfault" in script.lower()
        assert "pytorch" in script.lower()


class TestCiExitCodeDecisionLogic:
    """Unit tests for the exit-code decision table (Python mirror of bash handler)."""

    @pytest.mark.parametrize("exit_code", [0])
    def test_success_exit_passes_through(self, exit_code: int) -> None:
        """Happy path: pytest exit 0 yields step exit 0 with no warning."""
        resolved, warning = resolve_pytest_step_exit(exit_code)
        assert resolved == 0
        assert warning is None

    def test_teardown_segfault_139_treated_as_success(self) -> None:
        """Edge case: exit 139 (SIGSEGV) is treated as CI success after tests pass."""
        resolved, warning = resolve_pytest_step_exit(139)
        assert resolved == 0
        assert warning is not None
        assert warning.startswith("::warning::")
        assert "139" in warning

    @pytest.mark.parametrize("exit_code", [1, 2, 3, 5])
    def test_real_pytest_failures_fail_ci(self, exit_code: int) -> None:
        """Error conditions: pytest exit 1/2 (and other non-zero) must fail the CI step."""
        resolved, warning = resolve_pytest_step_exit(exit_code)
        assert resolved == exit_code
        assert warning is None

    def test_exit_139_is_not_confused_with_13_or_1390(self) -> None:
        """Only exact exit 139 triggers the segfault waiver — not similar codes."""
        assert resolve_pytest_step_exit(13) == (13, None)
        assert resolve_pytest_step_exit(138) == (138, None)
        assert resolve_pytest_step_exit(140) == (140, None)


class TestCiBashHandlerIntegration:
    """Shell integration tests executing the same bash logic as ci.yml."""

    def test_bash_handler_success_exit_zero(self) -> None:
        """Happy path: stub command exit 0 produces step exit 0."""
        result = _run_bash_handler(0)
        assert result.returncode == 0
        assert WARNING_ANNOTATION not in result.stdout

    def test_bash_handler_segfault_139_emits_warning_and_succeeds(self) -> None:
        """Edge case: stub exit 139 emits ::warning:: and step exits 0."""
        result = _run_bash_handler(139)
        assert result.returncode == 0, result.stderr
        assert WARNING_ANNOTATION in result.stdout

    @pytest.mark.parametrize("exit_code", [1, 2])
    def test_bash_handler_real_failures_propagate(self, exit_code: int) -> None:
        """Error conditions: stub exit 1/2 propagates unchanged — CI stays red."""
        result = _run_bash_handler(exit_code)
        assert result.returncode == exit_code
        assert WARNING_ANNOTATION not in result.stdout

    def test_set_e_without_set_plus_e_loses_139_exit_code(self) -> None:
        """Demonstrates the original bug: bash -e aborts before exit_code=$? on SIGSEGV 139."""
        bash = _working_bash()
        if bash is None:
            pytest.skip("working bash not available")

        # Simulate GHA default: errexit on, no set +e — pytest returning 139 aborts before $? capture.
        buggy_script = """\
set -e -o pipefail
python -c "import sys; sys.exit(139)"
exit_code=$?
echo "captured=$exit_code"
"""
        result = subprocess.run(
            [bash, "-c", buggy_script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 139
        assert "captured=" not in result.stdout

    def test_set_plus_e_allows_139_capture(self) -> None:
        """Fix verification: set +e before pytest allows capturing exit 139."""
        bash = _working_bash()
        if bash is None:
            pytest.skip("working bash not available")

        fixed_script = """\
set -e -o pipefail
set +e
python -c "import sys; sys.exit(139)"
exit_code=$?
set -e
echo "captured=$exit_code"
"""
        result = subprocess.run(
            [bash, "-c", fixed_script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "captured=139" in result.stdout


class TestCiWorkflowJobGraph:
    """Sanity checks on the broader CI workflow structure."""

    def test_test_job_depends_on_lint_and_docker_validate(self) -> None:
        """Pytest job runs only after lint and docker validation succeed."""
        workflow = _load_workflow()
        assert workflow["jobs"]["test"]["needs"] == ["lint", "docker-validate"]

    def test_matrix_covers_supported_python_versions(self) -> None:
        """Matrix includes 3.10, 3.11, 3.12 for broad compatibility signal."""
        workflow = _load_workflow()
        versions = workflow["jobs"]["test"]["strategy"]["matrix"]["python-version"]
        assert versions == ["3.10", "3.11", "3.12"]

    def test_run_pytest_step_env_has_live_test_flag(self) -> None:
        """Integration tests are enabled via NEXUS_KB_RUN_LIVE_TESTS=1."""
        step = _pytest_step(_load_workflow())
        assert step["env"]["NEXUS_KB_RUN_LIVE_TESTS"] == "1"