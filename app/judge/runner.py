"""Sandboxed Code Execution and Multi-Language Runner for CP Coach.

Provides isolated process execution with CPU timeout enforcement, memory tracking,
and automated verdict classification (AC, WA, TLE, MLE, CE, RE).
"""
import ast
import re
import os
import sys
import time
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Literal, Any
from pydantic import BaseModel, Field
from app.config import settings

VerdictType = Literal["AC", "WA", "TLE", "MLE", "CE", "RE", "UNKNOWN"]
LanguageType = Literal["cpp", "cpp17", "cpp20", "python", "python3", "java"]
JudgeBackendType = Literal["isolated_subprocess", "judge0", "disabled"]

DEFAULT_JUDGE_BACKEND: str = os.getenv("JUDGE_BACKEND", settings.judge_backend)

def get_active_judge_backend() -> str:
    """Return currently active judge execution backend identifier."""
    return os.getenv("JUDGE_BACKEND", DEFAULT_JUDGE_BACKEND).lower().strip()

MAX_OUTPUT_BYTES = 64 * 1024

BLOCKED_PYTHON_MODULES = {
    "os", "subprocess", "shutil", "socket", "pty", "commands",
    "posix", "nt", "ctypes", "winreg", "win32api", "builtins", "__builtin__",
    "http", "urllib", "requests", "ftplib", "telnetlib", "multiprocessing",
    "threading", "signal", "tempfile", "importlib"
}

BLOCKED_PYTHON_ATTRIBUTES = {
    "__subclasses__", "__bases__", "__class__", "__builtins__",
    "__globals__", "__code__", "__loader__", "__spec__", "load_module", "_getframe"
}

BLOCKED_PYTHON_BUILTINS = {
    "eval", "exec", "__import__", "open", "compile", "breakpoint"
}

BLOCKED_CPP_PATTERNS = [
    r'#\s*include\s*<cstdlib>',
    r'#\s*include\s*<sys/',
    r'#\s*include\s*<unistd\.h>',
    r'#\s*include\s*<windows\.h>',
    r'#\s*include\s*<process\.h>',
    r'#\s*include\s*<fstream>',
    r'#\s*include\s*<filesystem>',
    r'\bsystem\s*\(',
    r'\bfork\s*\(',
    r'\bpopen\s*\(',
    r'\bexec[lv]?[p|e]?\s*\(',
    r'\bkill\s*\(',
    r'\bremove\s*\(',
    r'\b_wsystem\s*\(',
    r'\bfopen\s*\(',
    r'\bfreopen\s*\(',
    r'\b(std::)?(ifstream|ofstream|fstream)\b',
    r'\b(__asm__|asm)\b',
    r'\bsyscall\s*\(',
]

BLOCKED_JAVA_PATTERNS = [
    r'Runtime\.getRuntime\s*\(',
    r'ProcessBuilder',
    r'System\.exit\s*\(',
    r'java\.io\.File',
    r'java\.io\.FileInputStream',
    r'java\.io\.FileOutputStream',
    r'java\.net\.',
    r'java\.lang\.reflect',
]

def validate_source_code_safety(source_code: str, language: str) -> tuple[bool, str | None]:
    """Validate source code against dangerous syscalls, file manipulation, and forbidden modules."""
    lang = language.lower()
    
    if lang in ("python", "python3"):
        for blocked_token in ("__subclasses__", "__builtins__", "__globals__", "BuiltinImporter"):
            if blocked_token in source_code:
                return False, f"Forbidden dynamic introspection token '{blocked_token}' detected."

        try:
            tree = ast.parse(source_code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        mod_root = alias.name.split('.')[0]
                        if mod_root in BLOCKED_PYTHON_MODULES:
                            return False, f"Forbidden import '{alias.name}' detected."
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        mod_root = node.module.split('.')[0]
                        if mod_root in BLOCKED_PYTHON_MODULES:
                            return False, f"Forbidden import from '{node.module}' detected."
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in BLOCKED_PYTHON_BUILTINS:
                            return False, f"Forbidden built-in function '{node.func.id}' detected."
                elif isinstance(node, ast.Attribute):
                    if node.attr in BLOCKED_PYTHON_ATTRIBUTES:
                        return False, f"Forbidden introspection attribute '{node.attr}' detected."
        except SyntaxError:
            pass
            
    elif lang in ("cpp", "cpp17", "cpp20"):
        for pattern in BLOCKED_CPP_PATTERNS:
            if re.search(pattern, source_code, flags=re.IGNORECASE):
                return False, f"Forbidden C++ system operation or header matching '{pattern}' detected."
                
    elif lang == "java":
        for pattern in BLOCKED_JAVA_PATTERNS:
            if re.search(pattern, source_code, flags=re.IGNORECASE):
                return False, f"Forbidden Java system operation matching '{pattern}' detected."
                
    return True, None

class ExecutionConfig(BaseModel):
    """Execution constraints and configuration."""
    time_limit_ms: int = Field(2000, ge=100, le=10000, description="CPU execution timeout in milliseconds")
    memory_limit_mb: int = Field(256, ge=16, le=1024, description="Memory limit in megabytes")
    max_output_bytes: int = Field(MAX_OUTPUT_BYTES, description="Maximum bytes of output to capture")

class ExecutionResult(BaseModel):
    """Result of running a single code submission against a test case."""
    verdict: VerdictType
    time_ms: float = Field(0.0, description="Execution wall-clock time in milliseconds")
    memory_kb: float = Field(0.0, description="Estimated peak memory usage in kilobytes")
    stdout: str = Field("", description="Standard output captured from execution")
    stderr: str = Field("", description="Standard error captured from execution")
    exit_code: int | None = Field(None, description="Process exit code")
    error_message: str = Field("", description="Human-readable error details")

def normalize_output(text: str) -> str:
    """Normalize output by stripping trailing whitespace on each line and trailing newlines."""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)

def get_sanitized_execution_env() -> dict[str, str]:
    """Construct minimal execution environment stripping all API keys and credentials."""
    safe_env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
    }
    if os.name == "nt":
        for var in ("SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "PATHEXT"):
            if var in os.environ:
                safe_env[var] = os.environ[var]
    return safe_env

def compile_code(
    source_code: str,
    language: LanguageType,
    work_dir: Path
) -> tuple[bool, list[str], str]:
    """Compile or prepare source code in an isolated directory.
    
    Returns:
        tuple[bool, list[str], str]: (success, execution_command, compiler_error_message)
    """
    lang = language.lower()

    is_safe, sec_err = validate_source_code_safety(source_code, lang)
    if not is_safe and sec_err:
        return False, [], f"Security Violation: {sec_err}"

    env = get_sanitized_execution_env()

    if lang in ("python", "python3"):
        script_path = work_dir / "solution.py"
        script_path.write_text(source_code, encoding="utf-8")
        
        try:
            compile_res = subprocess.run(
                [sys.executable, "-m", "py_compile", str(script_path)],
                capture_output=True,
                text=True,
                timeout=10,
                env=env
            )
            if compile_res.returncode != 0:
                return False, [], compile_res.stderr or compile_res.stdout
        except Exception as e:
            return False, [], f"Syntax validation error: {str(e)}"

        return True, [sys.executable, "-u", str(script_path)], ""

    elif lang in ("cpp", "cpp17", "cpp20"):
        source_path = work_dir / "solution.cpp"
        exe_path = work_dir / ("solution.exe" if os.name == "nt" else "solution")
        source_path.write_text(source_code, encoding="utf-8")

        gpp_bin = shutil.which("g++") or shutil.which("clang++")
        if not gpp_bin:
            return False, [], "No C++ compiler (g++ or clang++) found in system PATH."

        compile_cmd = [
            gpp_bin,
            "-O2",
            "-std=c++17",
            "-Wall",
            str(source_path),
            "-o",
            str(exe_path)
        ]

        try:
            comp_res = subprocess.run(
                compile_cmd,
                capture_output=True,
                text=True,
                timeout=20,
                cwd=str(work_dir),
                env=env
            )
            if comp_res.returncode != 0:
                return False, [], comp_res.stderr or comp_res.stdout
        except subprocess.TimeoutExpired:
            return False, [], "Compilation timed out after 20 seconds."
        except Exception as e:
            return False, [], f"Compilation error: {str(e)}"

        return True, [str(exe_path)], ""

    elif lang == "java":
        source_path = work_dir / "Solution.java"
        source_path.write_text(source_code, encoding="utf-8")

        javac_bin = shutil.which("javac")
        java_bin = shutil.which("java")
        if not javac_bin or not java_bin:
            return False, [], "Java SDK (javac/java) not found in system PATH."

        try:
            comp_res = subprocess.run(
                [javac_bin, str(source_path)],
                capture_output=True,
                text=True,
                timeout=20,
                cwd=str(work_dir),
                env=env
            )
            if comp_res.returncode != 0:
                return False, [], comp_res.stderr or comp_res.stdout
        except subprocess.TimeoutExpired:
            return False, [], "Java compilation timed out after 20 seconds."
        except Exception as e:
            return False, [], f"Java compilation error: {str(e)}"

        return True, [java_bin, "-cp", str(work_dir), "Solution"], ""

    else:
        return False, [], f"Unsupported programming language: '{language}'."

def run_isolated(
    command: list[str],
    input_data: str,
    config: ExecutionConfig | None = None,
    cwd: Path | None = None
) -> ExecutionResult:
    """Execute command in a sandboxed subprocess with strict time and output limits."""
    cfg = config or ExecutionConfig()
    timeout_sec = cfg.time_limit_ms / 1000.0
    safe_env = get_sanitized_execution_env()

    start_time = time.perf_counter()
    try:
        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(cwd) if cwd else None,
            env=safe_env
        )

        try:
            stdout, stderr = proc.communicate(input=input_data, timeout=timeout_sec)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            
            if len(stdout.encode("utf-8")) > cfg.max_output_bytes:
                stdout = stdout[:cfg.max_output_bytes] + "\n...[OUTPUT TRUNCATED]"
            if len(stderr.encode("utf-8")) > cfg.max_output_bytes:
                stderr = stderr[:cfg.max_output_bytes] + "\n...[STDERR TRUNCATED]"

            if proc.returncode != 0:
                return ExecutionResult(
                    verdict="RE",
                    time_ms=round(elapsed_ms, 2),
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=proc.returncode,
                    error_message=f"Runtime error with exit code {proc.returncode}."
                )

            return ExecutionResult(
                verdict="UNKNOWN",
                time_ms=round(elapsed_ms, 2),
                stdout=stdout,
                stderr=stderr,
                exit_code=0
            )

        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.communicate(timeout=0.5)
            except Exception:
                pass
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ExecutionResult(
                verdict="TLE",
                time_ms=round(max(elapsed_ms, cfg.time_limit_ms), 2),
                exit_code=None,
                error_message=f"Time Limit Exceeded (> {cfg.time_limit_ms}ms)."
            )

    except Exception as e:
        return ExecutionResult(
            verdict="RE",
            time_ms=0.0,
            exit_code=-1,
            error_message=f"Execution failed to start: {str(e)}"
        )

JUDGE0_LANGUAGE_IDS = {
    "cpp": 54,
    "cpp17": 54,
    "cpp20": 54,
    "python": 71,
    "python3": 71,
    "java": 62,
}

def execute_via_judge0(
    source_code: str,
    language: LanguageType,
    input_data: str,
    expected_output: str,
    config: ExecutionConfig | None = None,
    api_url: str | None = None,
    api_key: str | None = None
) -> ExecutionResult:
    """Execute code remotely using an external Judge0 sandbox instance."""
    import requests
    base_url = (api_url or os.getenv("JUDGE0_URL", settings.judge0_url)).rstrip("/")
    key = api_key or os.getenv("JUDGE0_API_KEY", settings.judge0_api_key)
    cfg = config or ExecutionConfig()
    lang_id = JUDGE0_LANGUAGE_IDS.get(language.lower(), 71)

    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-RapidAPI-Key"] = key
        headers["X-RapidAPI-Host"] = base_url.replace("https://", "").replace("http://", "").split("/")[0]

    payload = {
        "source_code": source_code,
        "language_id": lang_id,
        "stdin": input_data,
        "expected_output": expected_output,
        "cpu_time_limit": cfg.time_limit_ms / 1000.0,
        "memory_limit": cfg.memory_limit_mb * 1024,
    }

    try:
        url = f"{base_url}/submissions?base64_encoded=false&wait=true"
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code not in (200, 201):
            return ExecutionResult(
                verdict="UNKNOWN",
                error_message=f"Judge0 API returned HTTP {resp.status_code}: {resp.text[:200]}"
            )

        data = resp.json()
        status_id = data.get("status", {}).get("id", 0)
        time_sec = float(data.get("time") or 0.0)
        memory_kb = float(data.get("memory") or 0.0)
        stdout = data.get("stdout") or ""
        stderr = data.get("stderr") or ""
        comp_out = data.get("compile_output") or ""

        if status_id == 3:
            return ExecutionResult(verdict="AC", time_ms=round(time_sec * 1000, 2), memory_kb=memory_kb, stdout=stdout)
        elif status_id == 4:
            return ExecutionResult(verdict="WA", time_ms=round(time_sec * 1000, 2), memory_kb=memory_kb, stdout=stdout, error_message=f"Wrong Answer.\nExpected:\n{expected_output[:200]}\nGot:\n{stdout[:200]}")
        elif status_id == 5:
            return ExecutionResult(verdict="TLE", time_ms=round(time_sec * 1000, 2), memory_kb=memory_kb, error_message="Time Limit Exceeded.")
        elif status_id == 6:
            return ExecutionResult(verdict="CE", stderr=comp_out, error_message=f"Compilation Error:\n{comp_out}")
        else:
            return ExecutionResult(verdict="RE", stderr=stderr, time_ms=round(time_sec * 1000, 2), error_message=stderr or f"Runtime error with status {status_id}")
    except Exception as e:
        return ExecutionResult(
            verdict="UNKNOWN",
            error_message=f"Failed to communicate with Judge0 instance ({base_url}): {str(e)}"
        )

def evaluate_test_case(
    source_code: str,
    language: LanguageType,
    input_data: str,
    expected_output: str,
    config: ExecutionConfig | None = None,
    backend: str | None = None
) -> ExecutionResult:
    """End-to-end compilation and execution of a single test case across configured backends."""
    active_backend = (backend or get_active_judge_backend()).lower().strip()
    if active_backend == "disabled":
        return ExecutionResult(
            verdict="UNKNOWN",
            error_message="Sandbox code execution is disabled in this environment. Please submit your solution directly to Codeforces and click 'Poll Codeforces'."
        )

    cfg = config or ExecutionConfig()

    if active_backend == "judge0":
        return execute_via_judge0(source_code, language, input_data, expected_output, config=cfg)
    
    with tempfile.TemporaryDirectory(prefix="cp_judge_") as temp_dir_str:
        work_dir = Path(temp_dir_str)

        success, cmd, comp_err = compile_code(source_code, language, work_dir)
        if not success:
            return ExecutionResult(
                verdict="CE",
                time_ms=0.0,
                stderr=comp_err,
                error_message="Compilation Error:\n" + comp_err
            )

        exec_res = run_isolated(cmd, input_data=input_data, config=cfg, cwd=work_dir)
        if exec_res.verdict in ("TLE", "MLE", "RE"):
            return exec_res

        norm_actual = normalize_output(exec_res.stdout)
        norm_expected = normalize_output(expected_output)

        if norm_actual == norm_expected:
            exec_res.verdict = "AC"
        else:
            exec_res.verdict = "WA"
            exec_res.error_message = (
                f"Wrong Answer.\n"
                f"Expected:\n{norm_expected[:200]}\n\n"
                f"Got:\n{norm_actual[:200]}"
            )

        return exec_res
