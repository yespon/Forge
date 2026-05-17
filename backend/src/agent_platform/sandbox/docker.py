"""Docker sandbox provider for isolated execution."""

import asyncio
import tarfile
import tempfile
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

import aiodocker

from agent_platform.sandbox.models import (
    ExecutionResult,
    SandboxConfig,
    SandboxInfo,
    SandboxStatus,
)


class DockerSandboxProvider:
    """Docker-based sandbox provider.

    Provides isolated execution environments using Docker containers.
    Each session gets its own container with resource limits.
    """

    def __init__(self) -> None:
        """Initialize provider."""
        self._docker: aiodocker.Docker | None = None
        self._sandboxes: dict[str, SandboxInfo] = {}

    async def _get_docker(self) -> aiodocker.Docker:
        """Get or create Docker client."""
        if self._docker is None:
            self._docker = aiodocker.Docker()
        return self._docker

    async def create(
        self,
        session_id: str,
        config: SandboxConfig | None = None,
    ) -> SandboxInfo:
        """Create a new sandbox container.

        Args:
            session_id: Session ID for the sandbox
            config: Optional sandbox configuration

        Returns:
            SandboxInfo with sandbox details

        Raises:
            RuntimeError: If Docker is not available or container creation fails
        """
        docker = await self._get_docker()
        config = config or SandboxConfig()

        # Generate sandbox ID
        import uuid
        sandbox_id = f"sandbox-{session_id}-{uuid.uuid4().hex[:8]}"

        # Prepare container configuration
        host_config = {
            "Memory": self._parse_memory(config.memory_limit),
            "CpuQuota": int(config.cpu_limit * 100000),
            "NetworkMode": config.network_mode if not config.allow_internet else "bridge",
            "AutoRemove": False,
            "Privileged": False,
            "ReadonlyRootfs": config.read_only,
            "SecurityOpt": ["no-new-privileges:true"],
        }

        # Add volume if needed
        if config.volume_size:
            host_config["Mounts"] = [
                {
                    "Type": "volume",
                    "Source": sandbox_id,
                    "Target": config.working_dir,
                    "VolumeOptions": {
                        "DriverConfig": {"Options": {"size": config.volume_size}},
                    },
                },
            ]

        try:
            # Create container
            container = await docker.containers.create(
                name=sandbox_id,
                config={
                    "Image": config.image,
                    "Cmd": ["sleep", "3600"],  # Keep container running
                    "WorkingDir": config.working_dir,
                    "Env": [f"{k}={v}" for k, v in config.env_vars.items()],
                    "HostConfig": host_config,
                    "Labels": {
                        "agent-platform.session_id": session_id,
                        "agent-platform.sandbox_id": sandbox_id,
                    },
                },
            )

            # Start container
            await container.start()

            # Create sandbox info
            now = datetime.now(timezone.utc)
            sandbox_info = SandboxInfo(
                id=sandbox_id,
                session_id=session_id,
                status=SandboxStatus.RUNNING,
                container_id=container.id,
                created_at=now,
                started_at=now,
                last_activity_at=now,
                config=config,
            )

            self._sandboxes[sandbox_id] = sandbox_info

            return sandbox_info

        except Exception as e:
            raise RuntimeError(f"Failed to create sandbox: {e}") from e

    async def destroy(self, sandbox_id: str) -> None:
        """Destroy a sandbox container.

        Args:
            sandbox_id: Sandbox ID to destroy

        Raises:
            KeyError: If sandbox not found
        """
        if sandbox_id not in self._sandboxes:
            raise KeyError(f"Sandbox not found: {sandbox_id}")

        sandbox = self._sandboxes[sandbox_id]
        docker = await self._get_docker()

        try:
            container = await docker.containers.get(sandbox.container_id)
            await container.stop()
            await container.delete()

            sandbox.status = SandboxStatus.DESTROYED
            del self._sandboxes[sandbox_id]

        except Exception as e:
            sandbox.status = SandboxStatus.ERROR
            raise RuntimeError(f"Failed to destroy sandbox: {e}") from e

    async def execute(
        self,
        sandbox_id: str,
        command: str,
        timeout: int | None = None,
        working_dir: str | None = None,
    ) -> ExecutionResult:
        """Execute a command in the sandbox.

        Args:
            sandbox_id: Sandbox ID
            command: Command to execute
            timeout: Optional timeout in seconds
            working_dir: Optional working directory

        Returns:
            ExecutionResult with output and status
        """
        if sandbox_id not in self._sandboxes:
            raise KeyError(f"Sandbox not found: {sandbox_id}")

        sandbox = self._sandboxes[sandbox_id]
        docker = await self._get_docker()
        timeout = timeout or sandbox.config.timeout

        try:
            container = await docker.containers.get(sandbox.container_id)

            # Update activity timestamp
            sandbox.last_activity_at = datetime.now(timezone.utc)

            # Execute command
            exec_config = {
                "Cmd": ["sh", "-c", command],
                "WorkingDir": working_dir or sandbox.config.working_dir,
                "AttachStdout": True,
                "AttachStderr": True,
            }

            exec_obj = await container.exec(exec_config)

            # Start execution with timeout
            start_time = datetime.now(timezone.utc)

            try:
                async with asyncio.timeout(timeout):
                    output = await exec_obj.start()
                    # Collect output
                    stdout = []
                    stderr = []

                    if output:
                        for chunk in output:
                            if "stdout" in chunk:
                                stdout.append(chunk["stdout"])
                            elif "stderr" in chunk:
                                stderr.append(chunk["stderr"])

                    # Get exit code
                    inspect_result = await exec_obj.inspect()
                    exit_code = inspect_result.get("ExitCode", -1)

                    duration = int(
                        (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                    )

                    return ExecutionResult(
                        success=exit_code == 0,
                        exit_code=exit_code,
                        stdout="".join(stdout),
                        stderr="".join(stderr),
                        duration_ms=duration,
                        timed_out=False,
                    )

            except asyncio.TimeoutError:
                # Kill the exec if timed out
                try:
                    await exec_obj.stop()
                except Exception:
                    pass

                return ExecutionResult(
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Command timed out after {timeout} seconds",
                    duration_ms=timeout * 1000,
                    timed_out=True,
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=0,
                timed_out=False,
            )

    async def upload_file(
        self,
        sandbox_id: str,
        path: str,
        content: bytes,
    ) -> None:
        """Upload a file to the sandbox.

        Args:
            sandbox_id: Sandbox ID
            path: Target path in sandbox
            content: File content as bytes
        """
        if sandbox_id not in self._sandboxes:
            raise KeyError(f"Sandbox not found: {sandbox_id}")

        sandbox = self._sandboxes[sandbox_id]
        docker = await self._get_docker()

        try:
            container = await docker.containers.get(sandbox.container_id)

            # Create tar archive with file
            tar_buffer = BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
                file_info = tarfile.TarInfo(name=path.lstrip("/"))
                file_info.size = len(content)
                file_info.mtime = datetime.now().timestamp()
                tar.addfile(file_info, BytesIO(content))

            tar_buffer.seek(0)

            # Extract to container
            await container.put_archive(sandbox.config.working_dir, tar_buffer.read())

            sandbox.last_activity_at = datetime.now(timezone.utc)

        except Exception as e:
            raise RuntimeError(f"Failed to upload file: {e}") from e

    async def download_file(
        self,
        sandbox_id: str,
        path: str,
    ) -> bytes:
        """Download a file from the sandbox.

        Args:
            sandbox_id: Sandbox ID
            path: File path in sandbox

        Returns:
            File content as bytes
        """
        if sandbox_id not in self._sandboxes:
            raise KeyError(f"Sandbox not found: {sandbox_id}")

        sandbox = self._sandboxes[sandbox_id]
        docker = await self._get_docker()

        try:
            container = await docker.containers.get(sandbox.container_id)

            # Get file from container
            full_path = f"{sandbox.config.working_dir}/{path.lstrip('/')}"
            response = await container.get_archive(full_path)

            # Extract file from tar
            tar_bytes = response[0] if isinstance(response, tuple) else response
            tar_buffer = BytesIO(tar_bytes)

            with tarfile.open(fileobj=tar_buffer, mode="r") as tar:
                member = tar.getmembers()[0]
                file_obj = tar.extractfile(member)
                if file_obj:
                    return file_obj.read()

            raise RuntimeError("Failed to extract file from archive")

        except Exception as e:
            raise RuntimeError(f"Failed to download file: {e}") from e

    async def get_info(self, sandbox_id: str) -> SandboxInfo:
        """Get sandbox information.

        Args:
            sandbox_id: Sandbox ID

        Returns:
            SandboxInfo
        """
        if sandbox_id not in self._sandboxes:
            raise KeyError(f"Sandbox not found: {sandbox_id}")

        sandbox = self._sandboxes[sandbox_id]

        # Update resource usage if possible
        try:
            docker = await self._get_docker()
            container = await docker.containers.get(sandbox.container_id)
            stats = await container.stats(stream=False)

            if stats and len(stats) > 0:
                latest = stats[-1]
                if "memory_stats" in latest:
                    sandbox.memory_usage_mb = latest["memory_stats"].get("usage", 0) / 1024 / 1024
                if "cpu_stats" in latest:
                    cpu_delta = latest["cpu_stats"].get("cpu_usage", {}).get("total_usage", 0)
                    sandbox.cpu_usage_percent = cpu_delta / 1e9  # Simplified calculation

        except Exception:
            pass  # Ignore stats errors

        return sandbox

    async def list_files(
        self,
        sandbox_id: str,
        path: str = "/",
    ) -> list[dict[str, Any]]:
        """List files in sandbox directory.

        Args:
            sandbox_id: Sandbox ID
            path: Directory path

        Returns:
            List of file/directory information
        """
        if sandbox_id not in self._sandboxes:
            raise KeyError(f"Sandbox not found: {sandbox_id}")

        sandbox = self._sandboxes[sandbox_id]

        # Use ls command to list files
        result = await self.execute(
            sandbox_id,
            f"ls -la {path}",
            timeout=5,
        )

        if not result.success:
            raise RuntimeError(f"Failed to list files: {result.stderr}")

        # Parse ls output
        files = []
        for line in result.stdout.split("\n")[1:]:  # Skip header
            if line.strip():
                parts = line.split()
                if len(parts) >= 9:
                    files.append({
                        "permissions": parts[0],
                        "owner": parts[2],
                        "group": parts[3],
                        "size": parts[4],
                        "modified": " ".join(parts[5:8]),
                        "name": " ".join(parts[8:]),
                        "is_dir": parts[0].startswith("d"),
                    })

        return files

    @staticmethod
    def _parse_memory(memory_str: str) -> int:
        """Parse memory string to bytes.

        Args:
            memory_str: Memory string like "512m", "1g"

        Returns:
            Memory in bytes
        """
        units = {
            "b": 1,
            "k": 1024,
            "kb": 1024,
            "m": 1024 * 1024,
            "mb": 1024 * 1024,
            "g": 1024 * 1024 * 1024,
            "gb": 1024 * 1024 * 1024,
        }

        memory_str = memory_str.lower().strip()

        for suffix, multiplier in units.items():
            if memory_str.endswith(suffix):
                return int(memory_str[: -len(suffix)]) * multiplier

        return int(memory_str)

    async def close(self) -> None:
        """Close Docker client and cleanup."""
        if self._docker:
            # Destroy all sandboxes
            for sandbox_id in list(self._sandboxes.keys()):
                try:
                    await self.destroy(sandbox_id)
                except Exception:
                    pass

            await self._docker.close()
            self._docker = None


# Global provider instance
_provider: DockerSandboxProvider | None = None


async def get_sandbox_provider() -> DockerSandboxProvider:
    """Get or create global sandbox provider."""
    global _provider

    if _provider is None:
        _provider = DockerSandboxProvider()

    return _provider
