from __future__ import annotations

import os
import socket
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from executor.sandbox import ExecutionResult, run_code_in_sandbox

ROOT = Path(__file__).resolve().parent.parent


def test_valid_build123d_code_executes_successfully(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_step_path = str(output_dir / "valid.step").replace("\\", "/")
    code = textwrap.dedent(
        """
        from build123d import Solid, export_step
        part = Solid.make_box(10, 20, 30)
        export_step(part, "OUTPUT_PATH")
        """
    ).replace("OUTPUT_PATH", safe_step_path)

    result = run_code_in_sandbox(code, str(output_dir), timeout_seconds=30)

    assert result.success is True
    assert result.timed_out is False
    assert result.step_path is not None
    assert Path(result.step_path).exists()
    assert Path(result.step_path).stat().st_size > 0
    assert result.stderr == ""


def test_syntax_error_returns_failure_without_crashing_process() -> None:
    code = "from build123d import Solid\npart = (\n"
    result = run_code_in_sandbox(code, timeout_seconds=10)

    assert result.success is False
    assert result.timed_out is False
    assert result.step_path is None
    assert result.traceback is not None and result.traceback != ""
    assert result.exception is not None


def test_infinite_loop_times_out_and_returns_failure() -> None:
    code = "while True:\n    pass\n"
    result = run_code_in_sandbox(code, timeout_seconds=3)

    assert result.success is False
    assert result.timed_out is True
    assert result.step_path is None
    assert result.stderr != "" or result.traceback is not None


def test_disallowed_import_is_blocked() -> None:
    code = "import os\nprint('blocked')\n"
    result = run_code_in_sandbox(code, timeout_seconds=10)
    assert result.success is False
    assert result.exception is not None
    assert "ImportError" in result.exception or "blocked" in (result.stderr or "") or "disallowed" in (result.stderr or "")


def test_file_write_outside_output_dir_is_blocked(tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    code = f"open(r'{outside}', 'w').write('x')\n"
    result = run_code_in_sandbox(code, output_dir=str(tmp_path / 'allowed'), timeout_seconds=10)

    assert result.success is False
    assert result.exception is not None
    assert not outside.exists()


def test_network_call_is_blocked() -> None:
    code = "import socket\nsocket.socket().connect(('localhost', 1))\n"
    result = run_code_in_sandbox(code, timeout_seconds=10)

    assert result.success is False
    assert result.exception is not None


def test_parent_env_secrets_not_visible_to_sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FAKE_SECRET_KEY", "should-not-leak")
    output_dir = tmp_path / "out"
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "secret_check.txt"
    code = textwrap.dedent(
        f"""
        try:
            __import__('os').environ.get('FAKE_SECRET_KEY', 'absent')
            value = 'leaked'
        except Exception:
            value = 'absent'
        with open(r'{result_path}', 'w') as fh:
            fh.write(value)
        """
    )

    result = run_code_in_sandbox(code, str(output_dir), timeout_seconds=10)

    assert result.success is True
    assert result_path.read_text() == "absent"


def test_eval_based_import_bypass_is_blocked() -> None:
    code = "eval(\"__import__('os').listdir('/')\")"
    result = run_code_in_sandbox(code, timeout_seconds=10)

    assert result.success is False


def test_aliased_import_bypass_is_blocked() -> None:
    code = "grab = __import__\nmod = grab('o' + 's')\nmod.listdir('/')"
    result = run_code_in_sandbox(code, timeout_seconds=10)

    assert result.success is False


@pytest.mark.xfail(
    reason="Known V1 gap: Python-level namespace restrictions cannot prevent module globals or object.__subclasses__() from reaching imports already loaded by build123d itself without breaking the library runtime.",
    strict=True,
)
def test_module_globals_bypass_is_blocked() -> None:
    code = (
        "import build123d\n"
        "fn = build123d.export_step\n"
        "fn.__globals__.get('os', None) and fn.__globals__['os'].listdir('C:\\\\')\n"
    )
    # Importing build123d in an isolated child can cold-start OpenCascade on
    # Windows; allow the payload to reach the actual module-global check.
    result = run_code_in_sandbox(code, timeout_seconds=30)

    assert result.success is False

@pytest.mark.xfail(
    reason="Known V1 gap: object graph traversal (subclasses-walk) reaches "
           "already-loaded classes via pure attribute access, with no import "
           "statement, eval/exec call, or named reference to os/subprocess — "
           "outside the scope of the current runtime import hook.",
    strict=True,
)
def test_subclasses_walk_bypass_is_blocked() -> None:
    code = (
        "leak = [c for c in ().__class__.__base__.__subclasses__() "
        "if 'Popen' in c.__name__]\n"
        "leak[0](['id']) if leak else None\n"
    )
    result = run_code_in_sandbox(code, timeout_seconds=10)
    assert result.success is False

def test_reflection_builtins_are_not_available() -> None:
    code = "dir()\n"
    result = run_code_in_sandbox(code, timeout_seconds=10)
    assert result.success is False

def test_non_solid_geometry_is_rejected() -> None:
    """A flat 2D face is valid geometry build123d will happily export.
    The executor now re-imports the STEP output and rejects it because it
    contains no solids, while leaving broader geometry validation to Milestone
    5's evaluation harness."""
    code = textwrap.dedent(
        """
        from build123d import Rectangle, export_step
        flat_face = Rectangle(10, 10)
        export_step(flat_face, "OUTPUT_PATH")
        """
    ).replace("OUTPUT_PATH", "flat_face.step")

    # build123d import and STEP export can cold-start OpenCascade; a short
    # timeout is too tight for this geometry-validation case on Windows.
    result = run_code_in_sandbox(code, timeout_seconds=60)

    assert result.success is False
    assert result.step_path is None
    assert result.exception == "GeometryValidationError"
    assert result.traceback is not None
    assert "contains no solids" in result.traceback