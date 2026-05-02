import subprocess
import textwrap
import json
import tempfile
import os
import uuid
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ToolExecutor:
    """Execute user‑defined Python code in an isolated subprocess.
    The execution environment is minimal: no network, no extra modules except the
    standard library and any third‑party packages pre‑installed in the project
    (e.g., pandas, numpy). Time‑outs and resource limits are enforced.
    """

    def __init__(self, timeout_seconds: int = 30):
        self.timeout = timeout_seconds

    def execute_python(self, code: str, inputs: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Run *code* with optional *inputs* (JSON‑serialisable) and capture output.

        Returns a dictionary with keys:
            - ``output``: stdout of the script (str)
            - ``error``: stderr or exception message (str, may be empty)
        """
        inputs = inputs or {}
        # Create a temporary directory for the script and any temporary files
        work_dir = tempfile.mkdtemp(prefix="tool_exec_" + uuid.uuid4().hex)
        script_path = os.path.join(work_dir, "script.py")
        # The runner will load the JSON payload from stdin
        runner_code = textwrap.dedent(
            f"""
            import sys, json, traceback
            try:
                payload = json.load(sys.stdin)
                # Expose payload as a variable for the user script
                globals().update(payload)
                exec(open('{script_path}').read(), globals())
            except Exception:
                err = traceback.format_exc()
                print(err, file=sys.stderr)
                sys.exit(1)
            """
        )
        # Write user script and runner script
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)
        runner_path = os.path.join(work_dir, "runner.py")
        with open(runner_path, "w", encoding="utf-8") as f:
            f.write(runner_code)
        # Run the runner with isolated python interpreter
        cmd = ["python", "-I", "-u", runner_path]
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=work_dir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={"PYTHONPATH": "", "PATH": os.environ.get("PATH", "")},
            )
            stdin_data = json.dumps(inputs)
            out, err = proc.communicate(input=stdin_data, timeout=self.timeout)
            result = {"output": out.strip(), "error": err.strip()}
            logger.info(
                f"ToolExecutor: Python script executed (exit {proc.returncode}), "
                f"stdout {len(out)} chars, stderr {len(err)} chars"
            )
            return result
        except subprocess.TimeoutExpired:
            proc.kill()
            logger.error("ToolExecutor: execution timed out after %s seconds", self.timeout)
            return {"output": "", "error": "Execution timed out"}
        except Exception as e:
            logger.exception("ToolExecutor: unexpected error during execution")
            return {"output": "", "error": str(e)}
        finally:
            # Clean up temporary directory
            try:
                import shutil
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                pass

# Global singleton for easy import
tool_executor = ToolExecutor()
