import subprocess
import tempfile
import os
import signal
import time
import json
import docker
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
import uuid
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


class ExecutionService:
    """Safe code execution service with sandboxing and security measures"""

    def __init__(self):
        self.supported_languages = {
            "python": {
                "extension": ".py",
                "docker_image": "python:3.9-alpine",
                "command": "python",
                "timeout": 30,
                "memory_limit": "128m",
            },
            "javascript": {
                "extension": ".js",
                "docker_image": "node:16-alpine",
                "command": "node",
                "timeout": 30,
                "memory_limit": "128m",
            },
            "typescript": {
                "extension": ".ts",
                "docker_image": "node:16-alpine",
                "command": "npx ts-node",
                "timeout": 30,
                "memory_limit": "128m",
            },
            "java": {
                "extension": ".java",
                "docker_image": "openjdk:11-jre-slim",
                "command": "javac && java",
                "timeout": 45,
                "memory_limit": "256m",
            },
            "cpp": {
                "extension": ".cpp",
                "docker_image": "gcc:9",
                "command": "g++ -o main && ./main",
                "timeout": 45,
                "memory_limit": "256m",
            },
            "c": {
                "extension": ".c",
                "docker_image": "gcc:9",
                "command": "gcc -o main && ./main",
                "timeout": 45,
                "memory_limit": "256m",
            },
            "go": {
                "extension": ".go",
                "docker_image": "golang:1.17-alpine",
                "command": "go run",
                "timeout": 30,
                "memory_limit": "128m",
            },
            "rust": {
                "extension": ".rs",
                "docker_image": "rust:1.60",
                "command": "rustc -o main && ./main",
                "timeout": 45,
                "memory_limit": "256m",
            },
            "php": {
                "extension": ".php",
                "docker_image": "php:8.0-cli-alpine",
                "command": "php",
                "timeout": 30,
                "memory_limit": "128m",
            },
            "ruby": {
                "extension": ".rb",
                "docker_image": "ruby:3.0-alpine",
                "command": "ruby",
                "timeout": 30,
                "memory_limit": "128m",
            },
        }

        # Initialize Docker client
        try:
            self.docker_client = docker.from_env()
            self.docker_available = True
            logger.info("Docker client initialized successfully")
        except Exception as e:
            logger.warning(
                f"Docker not available: {e}. Falling back to subprocess execution."
            )
            self.docker_available = False

        # Security settings
        self.max_output_size = 1024 * 1024  # 1MB
        self.max_execution_time = 60  # 60 seconds max
        self.temp_dir = Path("/tmp/snippet_execution")
        self.temp_dir.mkdir(exist_ok=True)

    def execute_code(
        self, code: str, language: str, input_data: str = "", user_id: int = None
    ) -> Dict[str, Any]:
        """
        Execute code safely in a sandboxed environment

        Args:
            code: The source code to execute
            language: Programming language
            input_data: Input data for the program
            user_id: User ID for logging and rate limiting

        Returns:
            Dict containing execution results
        """
        if not self.is_language_supported(language):
            return {
                "success": False,
                "error": f"Language {language} is not supported",
                "supported_languages": list(self.supported_languages.keys()),
            }

        # Rate limiting check
        if user_id and not self._check_rate_limit(user_id):
            return {
                "success": False,
                "error": "Rate limit exceeded. Please wait before executing more code.",
                "retry_after": 60,
            }

        # Security validation
        security_check = self._validate_code_security(code, language)
        if not security_check["safe"]:
            return {
                "success": False,
                "error": f'Security violation: {security_check["reason"]}',
                "code": "SECURITY_VIOLATION",
            }

        # Execute based on available environment
        if self.docker_available:
            result = self._execute_in_docker(code, language, input_data)
        else:
            result = self._execute_in_subprocess(code, language, input_data)

        # Log execution for monitoring
        self._log_execution(user_id, language, result)

        return result

    def _execute_in_docker(
        self, code: str, language: str, input_data: str
    ) -> Dict[str, Any]:
        """Execute code in Docker container for maximum security"""
        lang_config = self.supported_languages[language]
        execution_id = str(uuid.uuid4())

        try:
            # Create temporary directory for this execution
            temp_path = self.temp_dir / execution_id
            temp_path.mkdir(exist_ok=True)

            # Write code to file
            code_file = temp_path / f"main{lang_config['extension']}"
            with open(code_file, "w", encoding="utf-8") as f:
                f.write(code)

            # Bind mount the temp directory
            volumes = {str(temp_path): {"bind": "/code", "mode": "rw"}}

            # Security restrictions
            security_opt = ["no-new-privileges:true", "seccomp:unconfined"]

            # Prepare command based on language
            command = self._prepare_execution_command(
                language, "/code/main" + lang_config["extension"]
            )

            # Create and run container
            container = self.docker_client.containers.run(
                image=lang_config["docker_image"],
                command=command,
                volumes=volumes,
                working_dir="/code",
                mem_limit=lang_config["memory_limit"],
                cpu_period=100000,
                cpu_quota=50000,  # 50% CPU
                network_disabled=True,
                read_only=False,
                security_opt=security_opt,
                detach=True,
                stdin_open=True,
                tty=False,
                remove=True,
            )

            # Send input data if provided
            if input_data:
                container.exec_run(f'echo "{input_data}"', stdin=True)

            # Wait for execution with timeout
            start_time = time.time()
            timeout = lang_config["timeout"]

            while container.status in ["created", "running"]:
                if time.time() - start_time > timeout:
                    container.kill()
                    return {
                        "success": False,
                        "error": f"Execution timeout ({timeout}s)",
                        "code": "TIMEOUT",
                    }
                time.sleep(0.1)
                container.reload()

            # Get output
            logs = container.logs(stdout=True, stderr=True).decode("utf-8")

            # Parse output
            if container.attrs["State"]["ExitCode"] == 0:
                return {
                    "success": True,
                    "output": self._truncate_output(logs),
                    "execution_time": time.time() - start_time,
                    "memory_used": self._get_memory_usage(container),
                    "exit_code": 0,
                }
            else:
                return {
                    "success": False,
                    "error": self._truncate_output(logs),
                    "exit_code": container.attrs["State"]["ExitCode"],
                }

        except docker.errors.ImageNotFound:
            return {
                "success": False,
                "error": f"Docker image for {language} not found",
                "code": "IMAGE_NOT_FOUND",
            }
        except Exception as e:
            logger.error(f"Docker execution error: {e}")
            return {
                "success": False,
                "error": f"Execution failed: {str(e)}",
                "code": "EXECUTION_ERROR",
            }
        finally:
            # Cleanup
            if "temp_path" in locals():
                shutil.rmtree(temp_path, ignore_errors=True)

    def _execute_in_subprocess(
        self, code: str, language: str, input_data: str
    ) -> Dict[str, Any]:
        """Fallback execution using subprocess (less secure)"""
        lang_config = self.supported_languages[language]
        execution_id = str(uuid.uuid4())

        try:
            # Create temporary file
            temp_path = self.temp_dir / execution_id
            temp_path.mkdir(exist_ok=True)

            code_file = temp_path / f"main{lang_config['extension']}"
            with open(code_file, "w", encoding="utf-8") as f:
                f.write(code)

            # Prepare command
            command = self._prepare_execution_command(language, str(code_file))

            # Execute with timeout and security restrictions
            start_time = time.time()

            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(temp_path),
                preexec_fn=os.setsid if os.name == "posix" else None,
            )

            try:
                stdout, stderr = process.communicate(
                    input=input_data, timeout=lang_config["timeout"]
                )

                execution_time = time.time() - start_time

                if process.returncode == 0:
                    return {
                        "success": True,
                        "output": self._truncate_output(stdout),
                        "execution_time": execution_time,
                        "exit_code": 0,
                    }
                else:
                    return {
                        "success": False,
                        "error": self._truncate_output(stderr or stdout),
                        "exit_code": process.returncode,
                    }

            except subprocess.TimeoutExpired:
                # Kill the process group
                if os.name == "posix":
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                else:
                    process.terminate()

                return {
                    "success": False,
                    "error": f'Execution timeout ({lang_config["timeout"]}s)',
                    "code": "TIMEOUT",
                }

        except Exception as e:
            logger.error(f"Subprocess execution error: {e}")
            return {
                "success": False,
                "error": f"Execution failed: {str(e)}",
                "code": "EXECUTION_ERROR",
            }
        finally:
            # Cleanup
            if "temp_path" in locals():
                shutil.rmtree(temp_path, ignore_errors=True)

    def _prepare_execution_command(self, language: str, file_path: str) -> list:
        """Prepare execution command based on language"""
        lang_config = self.supported_languages[language]

        if language == "python":
            return ["python3", file_path]
        elif language in ["javascript", "typescript"]:
            return ["node", file_path]
        elif language == "java":
            class_name = Path(file_path).stem
            return ["sh", "-c", f"javac {file_path} && java {class_name}"]
        elif language == "cpp":
            return ["sh", "-c", f"g++ {file_path} -o main && ./main"]
        elif language == "c":
            return ["sh", "-c", f"gcc {file_path} -o main && ./main"]
        elif language == "go":
            return ["go", "run", file_path]
        elif language == "rust":
            return ["sh", "-c", f"rustc {file_path} -o main && ./main"]
        elif language == "php":
            return ["php", file_path]
        elif language == "ruby":
            return ["ruby", file_path]
        else:
            raise ValueError(f"Unsupported language: {language}")

    def _validate_code_security(self, code: str, language: str) -> Dict[str, Any]:
        """Validate code for security vulnerabilities"""
        dangerous_patterns = {
            "python": [
                "import os",
                "import subprocess",
                "import sys",
                "__import__",
                "exec(",
                "eval(",
                "open(",
                "file(",
                "input(",
                "raw_input(",
                "import socket",
                "import urllib",
                "import requests",
            ],
            "javascript": [
                "require(",
                "process.",
                "fs.",
                "child_process",
                "eval(",
                "Function(",
                "setTimeout(",
                "setInterval(",
                "XMLHttpRequest",
                "fetch(",
            ],
            "java": [
                "Runtime.",
                "ProcessBuilder",
                "System.exit",
                "File(",
                "FileInputStream",
                "FileOutputStream",
                "Socket(",
                "ServerSocket(",
            ],
            "cpp": [
                "#include <cstdlib>",
                "#include <fstream>",
                "system(",
                "popen(",
                "exec",
                "fork(",
            ],
            "c": [
                "#include <stdlib.h>",
                "#include <stdio.h>",
                "system(",
                "popen(",
                "exec",
                "fork(",
            ],
        }

        # Check for dangerous patterns
        patterns = dangerous_patterns.get(language, [])
        for pattern in patterns:
            if pattern.lower() in code.lower():
                return {
                    "safe": False,
                    "reason": f"Potentially dangerous operation detected: {pattern}",
                }

        # Check code length
        if len(code) > 10000:  # 10KB limit
            return {"safe": False, "reason": "Code too long (max 10KB allowed)"}

        return {"safe": True}

    def _check_rate_limit(self, user_id: int) -> bool:
        """Check if user has exceeded rate limits"""
        # Simple in-memory rate limiting
        # In production, use Redis or database
        if not hasattr(self, "_rate_limits"):
            self._rate_limits = {}

        now = datetime.now()
        if user_id not in self._rate_limits:
            self._rate_limits[user_id] = []

        # Remove old entries (older than 1 minute)
        self._rate_limits[user_id] = [
            timestamp
            for timestamp in self._rate_limits[user_id]
            if now - timestamp < timedelta(minutes=1)
        ]

        # Check if under limit (10 executions per minute)
        if len(self._rate_limits[user_id]) >= 10:
            return False

        # Add current timestamp
        self._rate_limits[user_id].append(now)
        return True

    def _truncate_output(self, output: str) -> str:
        """Truncate output to prevent excessive data"""
        if len(output) > self.max_output_size:
            return output[: self.max_output_size] + "\n... (output truncated)"
        return output

    def _get_memory_usage(self, container) -> Optional[int]:
        """Get memory usage from container stats"""
        try:
            stats = container.stats(stream=False)
            return stats["memory_stats"].get("usage", 0)
        except:
            return None

    def _log_execution(self, user_id: int, language: str, result: Dict[str, Any]):
        """Log execution for monitoring and analytics"""
        log_data = {
            "user_id": user_id,
            "language": language,
            "success": result.get("success", False),
            "execution_time": result.get("execution_time", 0),
            "timestamp": datetime.now().isoformat(),
            "error_code": result.get("code", None),
        }

        logger.info(f"Code execution: {json.dumps(log_data)}")

    def is_language_supported(self, language: str) -> bool:
        """Check if a programming language is supported"""
        return language.lower() in self.supported_languages

    def get_supported_languages(self) -> list:
        """Get list of all supported programming languages"""
        return list(self.supported_languages.keys())

    def get_language_info(self, language: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific language"""
        return self.supported_languages.get(language.lower())

    def validate_syntax(self, code: str, language: str) -> Dict[str, Any]:
        """Validate code syntax without execution"""
        if not self.is_language_supported(language):
            return {"valid": False, "error": f"Language {language} is not supported"}

        try:
            if language == "python":
                import ast

                ast.parse(code)
            elif language == "javascript":
                # Basic JS syntax validation using subprocess
                result = subprocess.run(
                    ["node", "-c"],
                    input=code,
                    text=True,
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode != 0:
                    return {"valid": False, "error": result.stderr}
            # Add more language-specific validation as needed

            return {"valid": True}

        except SyntaxError as e:
            return {"valid": False, "error": f"Syntax error: {str(e)}"}
        except Exception as e:
            return {"valid": False, "error": f"Validation error: {str(e)}"}

    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics"""
        return {
            "supported_languages": len(self.supported_languages),
            "docker_available": self.docker_available,
            "max_execution_time": self.max_execution_time,
            "max_output_size": self.max_output_size,
            "temp_directory": str(self.temp_dir),
        }

    def cleanup_temp_files(self, older_than_minutes: int = 60):
        """Cleanup temporary files older than specified minutes"""
        try:
            cutoff_time = datetime.now() - timedelta(minutes=older_than_minutes)

            for item in self.temp_dir.iterdir():
                if item.is_dir():
                    # Check directory creation time
                    creation_time = datetime.fromtimestamp(item.stat().st_ctime)
                    if creation_time < cutoff_time:
                        shutil.rmtree(item, ignore_errors=True)
                        logger.info(f"Cleaned up temp directory: {item}")

        except Exception as e:
            logger.error(f"Error cleaning up temp files: {e}")

    def __del__(self):
        """Cleanup when service is destroyed"""
        try:
            if hasattr(self, "docker_client"):
                self.docker_client.close()
        except:
            pass
