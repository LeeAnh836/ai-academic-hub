"""
Code Executor - Safe Python code execution in Docker
"""
import docker
import tempfile
import os
import json
import re
from typing import Dict, Any, Optional
import logging
from requests.exceptions import ReadTimeout

from core.config import settings

logger = logging.getLogger(__name__)


class CodeExecutor:
    """
    Executes Python code safely in Docker container
    """
    
    def __init__(self):
        """Initialize Docker client"""
        self.client = None
        self.enabled = False
        
        try:
            self.client = docker.from_env()
            # Test connection
            self.client.ping()
            self.enabled = True
            logger.info("✅ Docker client ready for code execution")
        except Exception as e:
            logger.warning(f"⚠️ Docker not available: {e}. Code execution disabled.")
            self.enabled = False
    
    def execute_code(
        self,
        code: str,
        data_files: Optional[Dict[str, bytes]] = None,
        timeout: int = None
    ) -> Dict[str, Any]:
        """
        Execute Python code in Docker container
        
        Args:
            code: Python code to execute
            data_files: Dict of {filename: file_content} to mount
            timeout: Execution timeout in seconds
        
        Returns:
            Dict with:
                - success: bool
                - output: stdout
                - error: stderr (if any)
                - execution_time: float (seconds)
        """
        if not self.enabled:
            return {
                "success": False,
                "output": "",
                "error": "Docker not available",
                "execution_time": 0
            }
        
        timeout = timeout or settings.CODE_EXEC_TIMEOUT
        
        try:
            # Create temporary directory for code and data
            use_volume = bool(settings.CODE_EXEC_VOLUME_NAME) and os.path.exists("/.dockerenv")
            shared_dir = settings.CODE_EXEC_SHARED_DIR if use_volume else None
            if use_volume and shared_dir:
                os.makedirs(shared_dir, exist_ok=True)
                tmp_dir_ctx = tempfile.TemporaryDirectory(dir=shared_dir)
            else:
                tmp_dir_ctx = tempfile.TemporaryDirectory()

            with tmp_dir_ctx as tmpdir:
                # Write code to file
                code_file = os.path.join(tmpdir, "script.py")
                with open(code_file, 'w', encoding='utf-8') as f:
                    f.write(code)
                
                # Write data files if provided
                if data_files:
                    for filename, content in data_files.items():
                        filepath = os.path.join(tmpdir, filename)
                        with open(filepath, 'wb') as f:
                            f.write(content)
                
                # Run code in Docker container
                import time
                start_time = time.time()
                
                volume_spec = (
                    {settings.CODE_EXEC_VOLUME_NAME: {'bind': '/workspace', 'mode': 'rw'}}
                    if use_volume
                    else {tmpdir: {'bind': '/workspace', 'mode': 'rw'}}
                )
                container_workdir = (
                    f"/workspace/{os.path.basename(tmpdir)}"
                    if use_volume
                    else "/workspace"
                )

                container = self.client.containers.run(
                    image=settings.CODE_EXEC_DOCKER_IMAGE,
                    command=["python", "script.py"],
                    volumes=volume_spec,
                    working_dir=container_workdir,
                    detach=True,
                    remove=False,
                    stdout=True,
                    stderr=True,
                    mem_limit='512m',  # Limit memory
                    network_disabled=True  # No network access
                )
                try:
                    wait_result = container.wait(timeout=timeout)
                except ReadTimeout:
                    try:
                        container.kill()
                    except Exception:
                        pass
                    return {
                        "success": False,
                        "output": "",
                        "error": f"execution_timeout_{timeout}s",
                        "execution_time": time.time() - start_time
                    }

                execution_time = time.time() - start_time
                exit_code = (
                    wait_result.get("StatusCode", 1)
                    if isinstance(wait_result, dict)
                    else wait_result
                )
                stdout = container.logs(stdout=True, stderr=False)
                stderr = container.logs(stdout=False, stderr=True)

                output = stdout.decode('utf-8', errors='replace') if stdout else ""
                error_output = stderr.decode('utf-8', errors='replace') if stderr else ""

                if len(output) > settings.CODE_EXEC_MAX_OUTPUT_SIZE:
                    output = output[:settings.CODE_EXEC_MAX_OUTPUT_SIZE] + "\n... (truncated)"

                if exit_code not in (0, "0", None):
                    return {
                        "success": False,
                        "output": output,
                        "error": error_output or f"exit_code_{exit_code}",
                        "execution_time": execution_time
                    }

                return {
                    "success": True,
                    "output": output,
                    "error": error_output,
                    "execution_time": execution_time
                }
                
        except docker.errors.ContainerError as e:
            # Code execution error
            return {
                "success": False,
                "output": str(e.exit_status),
                "error": e.stderr.decode('utf-8') if e.stderr else str(e),
                "execution_time": 0
            }

        except Exception as e:
            logger.error(f"❌ Code execution error: {e}")
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "execution_time": 0
            }

        finally:
            if 'container' in locals() and container is not None:
                try:
                    container.remove(force=True)
                except Exception:
                    pass
    
    def execute_pandas_code(
        self,
        code: str,
        csv_file: bytes,
        filename: str = "data.csv"
    ) -> Dict[str, Any]:
        """
        Execute pandas code with CSV file
        
        Args:
            code: Python code (can use df variable)
            csv_file: CSV file content
            filename: Filename for the CSV
        
        Returns:
            Execution result
        """
        needs_import = "import pandas" not in code
        file_ext = os.path.splitext(filename or "")[1].lower()
        load_stmt = (
            f"df = pd.read_excel('{filename}')"
            if file_ext in {".xlsx", ".xls"}
            else f"df = pd.read_csv('{filename}')"
        )

        defines_df = bool(re.search(r"^\s*df\s*=", code, re.MULTILINE))
        uses_reader = any(token in code for token in [
            "read_csv(",
            "read_excel(",
            "read_table(",
            "read_parquet(",
        ])

        needs_load = not defines_df and not uses_reader

        if needs_import and needs_load:
            code = "import pandas as pd\n" + load_stmt + "\n" + code
        elif needs_import:
            code = "import pandas as pd\n" + code
        elif needs_load:
            code = re.sub(
                r"(import\s+pandas[^\n]*\n)",
                r"\1" + load_stmt + "\n",
                code,
                count=1,
            )
        
        return self.execute_code(
            code=code,
            data_files={filename: csv_file}
        )


# Global singleton
code_executor = CodeExecutor()
