"""
Code Executor - Safe Python code execution in Docker
"""
import docker
import tempfile
import os
import json
from typing import Dict, Any, Optional
import logging

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
            # Create temporary directory  for code and data
            with tempfile.TemporaryDirectory() as tmpdir:
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
                
                result = self.client.containers.run(
                    image=settings.CODE_EXEC_DOCKER_IMAGE,
                    command=["python", "/workspace/script.py"],
                    volumes={
                        tmpdir: {'bind': '/workspace', 'mode': 'rw'}
                    },
                    working_dir='/workspace',
                    remove=True,
                    stdout=True,
                    stderr=True,
                    timeout=timeout,
                    mem_limit='512m',  # Limit memory
                    network_disabled=True  # No network access
                )
                
                execution_time = time.time() - start_time
                
                # Decode output
                output = result.decode('utf-8')
                
                # Truncate if too long
                if len(output) > settings.CODE_EXEC_MAX_OUTPUT_SIZE:
                    output = output[:settings.CODE_EXEC_MAX_OUTPUT_SIZE] + "\n... (truncated)"
                
                return {
                    "success": True,
                    "output": output,
                    "error": "",
                    "execution_time": execution_time
                }
        
        except docker.errors.ContainerError as e:
            # Code execution error
            return {
                "success": False,
                "output": e.exit_status,
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
        # Prepend pandas import if not present
        if "import pandas" not in code:
            code = "import pandas as pd\n" + code
        
        # Load CSV if not already loaded
        if "read_csv" not in code and "df" not in code:
            code = f"df = pd.read_csv('{filename}')\n" + code
        
        return self.execute_code(
            code=code,
            data_files={filename: csv_file}
        )


# Global singleton
code_executor = CodeExecutor()
