from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExecutionResult:
    success: bool
    step_path: str | None
    stdout: str
    stderr: str
    exception: str | None
    traceback: str | None
    timed_out: bool


_BLOCKED_IMPORTS = {
    "os",
    "subprocess",
    "socket",
    "sys",
    "importlib",
    "urllib",
    "urllib3",
    "requests",
    "http",
    "http.client",
    "ftplib",
    "ssl",
    "pathlib",
}

_ALLOWED_IMPORTS = {
    "math",
    "statistics",
    "typing",
    "itertools",
    "functools",
    "collections",
    "dataclasses",
    "enum",
    "copy",
    "re",
    "decimal",
    "json",
    "traceback",
    "uuid",
    "datetime",
    "time",
    "warnings",
    "inspect",
}


def _parse_exception_name(stderr: str) -> str | None:
    if not stderr:
        return None
    for line in reversed(stderr.splitlines()):
        stripped = line.strip()
        if not stripped or stripped.startswith("Traceback") or stripped.startswith("File "):
            continue
        if stripped.startswith("PermissionError"):
            return "PermissionError"
        if stripped.startswith("ImportError"):
            return "ImportError"
        if stripped.startswith("TimeoutExpired"):
            return "TimeoutExpired"
        if stripped.startswith("OSError"):
            return "OSError"
        if stripped.startswith("SyntaxError"):
            return "SyntaxError"
        if stripped.startswith("Exception"):
            return "Exception"
        if ":" in stripped:
            return stripped.split(":", 1)[0]
        return stripped
    return None


def _sandbox_child_script() -> str:
    return '''
import builtins as _real_builtins
import io
import json
import os
import sys
import traceback
from pathlib import Path

sandbox_root = Path(os.environ["SANDBOX_ROOT"]).resolve()
real_open = open
real_io_open = io.open
real_import = __import__

BLOCKED_IMPORTS = {"os", "subprocess", "socket", "sys", "importlib", "urllib", "urllib3", "requests", "http", "http.client", "ftplib", "ssl", "pathlib"}
ALLOWED_IMPORTS = {
    "build123d", "OCP", "math", "statistics", "typing", "itertools", "functools", "collections",
    "dataclasses", "enum", "copy", "re", "decimal", "json", "traceback", "uuid", "datetime", "time",
    "warnings", "inspect", "numpy", "scipy", "PIL", "ezdxf", "genericpath", "ntpath", "linecache",
    "xml", "platform", "pathlib", "builtins"
}


def _sandbox_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level != 0:
        raise ImportError("Relative imports are not allowed in the sandbox.")
    if name is None:
        raise ImportError("Empty import is not allowed in the sandbox.")
    top = name.split(".", 1)[0]
    if name in BLOCKED_IMPORTS or top in BLOCKED_IMPORTS:
        raise ImportError(f"Import of '{name}' is not allowed in the sandbox.")
    if name.startswith("build123d") or name.startswith("OCP") or top in ALLOWED_IMPORTS or name in ALLOWED_IMPORTS:
        return real_import(name, globals, locals, fromlist, level)
    raise ImportError(f"Import of '{name}' is not allowed in the sandbox.")


def _is_allowed_path(path_value):
    if path_value is None:
        return False
    try:
        if not str(path_value):
            return False
        candidate = Path(path_value).expanduser().resolve(strict=False)
        if not candidate.is_absolute():
            candidate = (sandbox_root / candidate).resolve(strict=False)
        candidate.relative_to(sandbox_root)
        return True
    except Exception:
        return False


def _is_runtime_resource_path(path_value):
    if path_value is None:
        return False
    try:
        candidate = Path(path_value).expanduser().resolve(strict=False)
    except Exception:
        return False

    runtime_roots = [
        Path(sys.executable).resolve().parent.parent,
        Path(sys.base_prefix).resolve(),
        Path(sys.exec_prefix).resolve(),
        Path.home() / ".cache",
    ]
    for root in runtime_roots:
        try:
            candidate.relative_to(root)
            return True
        except Exception:
            pass

    windows_font_roots = [
        Path("C:/Windows/Fonts"),
        Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts",
    ]
    for root in windows_font_roots:
        try:
            candidate.relative_to(root)
            return True
        except Exception:
            pass

    return False


def _is_library_read(mode):
    if mode is None:
        return False
    text_mode = str(mode).lower()
    return ("r" in text_mode and "w" not in text_mode and "a" not in text_mode and "x" not in text_mode and "+" not in text_mode)


def _guarded_open(path, mode="r", *args, **kwargs):
    if _is_allowed_path(path):
        return real_open(path, mode, *args, **kwargs)
    if _is_runtime_resource_path(path) and _is_library_read(mode):
        return real_open(path, mode, *args, **kwargs)
    raise PermissionError(f"File access outside sandbox output directory is prohibited: {path}")


def _guarded_io_open(file, mode="r", *args, **kwargs):
    if _is_allowed_path(file):
        return real_io_open(file, mode, *args, **kwargs)
    if _is_runtime_resource_path(file) and _is_library_read(mode):
        return real_io_open(file, mode, *args, **kwargs)
    raise PermissionError(f"File access outside sandbox output directory is prohibited: {file}")


try:
    import resource
    limit_bytes = int(os.environ.get("SANDBOX_MEMORY_MB", "512")) * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
except Exception:
    pass

real_path_open = Path.open


def _guarded_path_open(self, *args, **kwargs):
    mode = args[0] if args else kwargs.get("mode", "r")
    if _is_allowed_path(self):
        return real_path_open(self, *args, **kwargs)
    if _is_runtime_resource_path(self) and _is_library_read(mode):
        return real_path_open(self, *args, **kwargs)
    raise PermissionError(f"File access outside sandbox output directory is prohibited: {self}")


Path.open = _guarded_path_open
_real_builtins.open = _guarded_open
io.open = _guarded_io_open

SAFE_BUILTINS = {
    "__import__": _sandbox_import,
    "__build_class__": _real_builtins.__build_class__,
    "print": print,
    "len": len,
    "range": range,
    "str": str,
    "int": int,
    "float": float,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "sorted": sorted,
    "min": min,
    "max": max,
    "sum": sum,
    "abs": abs,
    "round": round,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "type": type,
    "bool": bool,
    "object": object,
    "slice": slice,
    "bytes": bytes,
    "memoryview": memoryview,
    "hash": hash,
    "iter": iter,
    "next": next,
    "any": any,
    "all": all,
    "repr": repr,
    "ord": ord,
    "chr": chr,
    "format": format,
    "open": _guarded_open,
    "Exception": Exception,
    "TypeError": TypeError,
    "ValueError": ValueError,
    "RuntimeError": RuntimeError,
    "ImportError": ImportError,
    "AttributeError": AttributeError,
    "KeyError": KeyError,
    "IndexError": IndexError,
    "ZeroDivisionError": ZeroDivisionError,
    "FileNotFoundError": FileNotFoundError,
    "PermissionError": PermissionError,
    "OSError": OSError,
    "AssertionError": AssertionError,
    "StopIteration": StopIteration,
    "NotImplementedError": NotImplementedError,
    "OverflowError": OverflowError,
    "NameError": NameError,
}

stdout_buffer = io.StringIO()
stderr_buffer = io.StringIO()
original_stdout = sys.stdout
original_stderr = sys.stderr
sys.stdout = stdout_buffer
sys.stderr = stderr_buffer

payload = {}
user_code = json.loads(os.environ["SANDBOX_CODE"])

try:
    namespace = {"__builtins__": SAFE_BUILTINS}
    exec(compile(user_code, "<sandbox>", "exec"), namespace, namespace)
    step_files = sorted(sandbox_root.glob("*.step"))
    step_path = str(step_files[0]) if step_files else None
    if step_path is not None:
        from build123d import import_step as _import_step

        imported = _import_step(step_path)
        if len(imported.solids()) == 0:
            validation_message = "Exported geometry contains no solids - not a valid part."
            payload = {
                "success": False,
                "step_path": None,
                "stdout": stdout_buffer.getvalue(),
                "stderr": stderr_buffer.getvalue() or validation_message,
                "exception": "GeometryValidationError",
                "traceback": validation_message,
                "timed_out": False,
            }
        else:
            payload = {
                "success": True,
                "step_path": step_path,
                "stdout": stdout_buffer.getvalue(),
                "stderr": stderr_buffer.getvalue(),
                "exception": None,
                "traceback": None,
                "timed_out": False,
            }
    else:
        payload = {
            "success": True,
            "step_path": step_path,
            "stdout": stdout_buffer.getvalue(),
            "stderr": stderr_buffer.getvalue(),
            "exception": None,
            "traceback": None,
            "timed_out": False,
        }
except BaseException as exc:
    payload = {
        "success": False,
        "step_path": None,
        "stdout": stdout_buffer.getvalue(),
        "stderr": stderr_buffer.getvalue() or traceback.format_exc(),
        "exception": type(exc).__name__,
        "traceback": traceback.format_exc(),
        "timed_out": False,
    }
finally:
    sys.stdout = original_stdout
    sys.stderr = original_stderr
    print(json.dumps(payload))
'''


def run_code_in_sandbox(
    code: str,
    output_dir: str | None = None,
    timeout_seconds: float = 30.0,
    memory_limit_mb: int = 512,
) -> ExecutionResult:
    """Execute Python build123d code in a subprocess with strict sandbox restrictions."""
    sandbox_dir = Path(output_dir).resolve() if output_dir is not None else Path(tempfile.mkdtemp(prefix="sandbox_"))
    sandbox_dir.mkdir(parents=True, exist_ok=True)

    env = {
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT") or os.environ.get("WINDIR", "C:/Windows"),
        "TEMP": os.environ.get("TEMP") or os.environ.get("TMP", ""),
        "TMP": os.environ.get("TMP") or os.environ.get("TEMP", ""),
        "USERPROFILE": os.environ.get("USERPROFILE") or os.environ.get("HOME", ""),
        "HOME": os.environ.get("HOME") or os.environ.get("USERPROFILE", ""),
        "LOCALAPPDATA": os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local"),
        "APPDATA": os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming"),
        "PROGRAMDATA": os.environ.get("PROGRAMDATA") or "C:/ProgramData",
        "SANDBOX_ROOT": str(sandbox_dir),
        "SANDBOX_CODE": json.dumps(code),
        "SANDBOX_MEMORY_MB": str(int(memory_limit_mb)),
    }
    env = {key: value for key, value in env.items() if value not in (None, "")}

    try:
        completed = subprocess.run(
            [sys.executable, "-I", "-c", _sandbox_child_script()],
            capture_output=True,
            text=True,
            timeout=float(timeout_seconds),
            cwd=str(sandbox_dir),
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        stdout_value = exc.stdout or ""
        stderr_value = exc.stderr or ""
        return ExecutionResult(
            success=False,
            step_path=None,
            stdout=stdout_value,
            stderr=stderr_value or f"Execution timed out after {timeout_seconds} seconds.",
            exception="TimeoutExpired",
            traceback=f"TimeoutExpired: execution exceeded {timeout_seconds} seconds",
            timed_out=True,
        )

    payload = {}
    try:
        lines = [line.strip() for line in (completed.stdout or "").splitlines() if line.strip()]
        if lines:
            payload = json.loads(lines[-1])
    except json.JSONDecodeError:
        payload = {}

    if not payload:
        payload = {
            "success": False,
            "step_path": None,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "exception": _parse_exception_name(completed.stderr),
            "traceback": completed.stderr if completed.stderr else None,
            "timed_out": False,
        }

    if completed.returncode != 0 and payload.get("success") is not False:
        payload["success"] = False
        payload["exception"] = payload.get("exception") or _parse_exception_name(completed.stderr)
        payload["traceback"] = payload.get("traceback") or completed.stderr or None

    return ExecutionResult(
        success=bool(payload.get("success")),
        step_path=payload.get("step_path"),
        stdout=payload.get("stdout") or completed.stdout,
        stderr=payload.get("stderr") or completed.stderr,
        exception=payload.get("exception"),
        traceback=payload.get("traceback"),
        timed_out=bool(payload.get("timed_out", False)),
    )
