"""Kernel execution engine for MCP server — manages Jupyter kernel lifecycle.

Provides a thread-safe :class:`KernelPool` that manages multiple Jupyter
kernels (one per session) and executes code cells asynchronously using a
thread pool for the blocking kernel client API.

Requires the ``jupyter_client`` package (installed with ``notebookllm[all]``
or ``pip install jupyter_client``).
"""
import asyncio
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Literal

from notebookllm.models import Cell, CellType

try:
    from jupyter_client import KernelManager as _KernelManager
    from jupyter_client.client import KernelClient as _KernelClient
except ImportError:
    _KernelManager = None  # type: ignore
    _KernelClient = None  # type: ignore


@dataclass
class ExecutionJob:
    """Represents an active or completed cell execution.

    Attributes:
        job_id: Unique job identifier.
        session_id: Session this job belongs to.
        cell_index: Index of the cell being executed.
        status: Current execution status.
        output: Captured stdout/stderr output.
        error: Error message if execution failed.
    """

    job_id: str
    session_id: str
    cell_index: int
    status: Literal["pending", "running", "completed", "failed", "interrupted"] = "pending"
    output: str = ""
    error: str | None = None


class KernelPool:
    """Manages kernel lifecycle and cell execution for MCP sessions.

    Thread-safe — all ``_kernels`` and ``_jobs`` access is guarded by
    ``self._lock``. Uses a :class:`ThreadPoolExecutor` to run blocking
    Jupyter client calls without blocking the asyncio event loop.

    Args:
        max_workers: Maximum number of concurrent kernel executions.
    """

    def __init__(self, max_workers: int = 4):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = threading.Lock()
        self._jobs: dict[str, ExecutionJob] = {}
        # session_id -> (KernelManager, KernelClient)
        self._kernels: dict[str, tuple[_KernelManager, _KernelClient]] = {}

    # ------------------------------------------------------------------
    # Kernel lifecycle
    # ------------------------------------------------------------------

    def _sync_start_kernel(self, session_id: str, kernel_name: str) -> str:
        """Start a kernel synchronously (runs in thread pool).

        Args:
            session_id: Session to start a kernel for.
            kernel_name: Kernel spec name (e.g. ``"python3"``).

        Returns:
            The kernel name that was started.
        """
        from jupyter_client import KernelManager

        with self._lock:
            if session_id in self._kernels:
                return kernel_name

        km = KernelManager(kernel_name=kernel_name)
        km.start_kernel()
        kc = km.client()
        kc.start_channels()

        with self._lock:
            self._kernels[session_id] = (km, kc)

        return kernel_name

    async def start_kernel(self, session_id: str, kernel_name: str = "python3") -> str:
        """Start a Jupyter kernel for a session.

        Args:
            session_id: Session identifier.
            kernel_name: Kernel spec name. Defaults to ``"python3"``.

        Returns:
            The kernel name that was started.

        Raises:
            ImportError: If ``jupyter_client`` is not installed.
        """
        try:
            import jupyter_client  # type: ignore[import-not-found] # noqa
        except ImportError:
            raise ImportError(
                "notebookllm[execute] not installed. Run: pip install notebookllm[execute]"
            ) from None

        return await asyncio.to_thread(self._sync_start_kernel, session_id, kernel_name)

    # ------------------------------------------------------------------
    # Cell execution
    # ------------------------------------------------------------------

    def _get_kernel(self, session_id: str) -> _KernelClient:
        """Get the kernel client for a session.

        Args:
            session_id: Session identifier.

        Returns:
            The Jupyter kernel client.

        Raises:
            RuntimeError: If no kernel has been started for the session.
        """
        with self._lock:
            if session_id not in self._kernels:
                raise RuntimeError(f"Kernel not started for session {session_id}")
            return self._kernels[session_id][1]

    def _sync_execute_cell(
        self, session_id: str, cell_source: str, timeout: int
    ) -> tuple[str, str | None]:
        """Execute a cell synchronously in the session's kernel.

        Args:
            session_id: Session identifier.
            cell_source: Source code to execute.
            timeout: Maximum execution time in seconds.

        Returns:
            A ``(output, error)`` tuple. *error* is ``None`` on success.
        """
        client = self._get_kernel(session_id)

        msg_id = client.execute(cell_source)
        try:
            reply = client.get_shell_msg(timeout=timeout)  # type: ignore[attr-defined]
        except TimeoutError:
            return "", f"Cell execution timed out after {timeout}s"

        error = None
        if reply["content"]["status"] == "error":
            error = reply["content"]["evalue"]

        # Collect outputs
        outputs = []
        while True:
            try:
                msg = client.get_iopub_msg(timeout=5)  # type: ignore[attr-defined]
                if msg["parent_header"].get("msg_id") == msg_id:
                    msg_type = msg["msg_type"]
                    content = msg["content"]
                    if msg_type == "stream":
                        out_name = content.get("name", "stdout")
                        out_text = content.get("text", "")
                        outputs.append(f"[{out_name}] {out_text}")
                    elif msg_type == "execute_result":
                        data = content.get("data", {})
                        outputs.append(f"[output] {data.get('text/plain', '')}")
                    elif msg_type == "error":
                        outputs.append(f"[error] {content.get('evalue', '')}")
                    elif msg_type == "status" and content.get("execution_state") == "idle":
                        break
            except TimeoutError:
                break

        output_str = "\n".join(outputs) if outputs else "Cell executed (no output)."
        return output_str, error

    async def execute_cell(
        self, session_id: str, cell_index: int, cell_source: str, timeout: int = 60
    ) -> str:
        """Execute a code cell via the session's kernel.

        Runs the blocking Jupyter client API in a thread pool so the
        event loop remains responsive.

        Args:
            session_id: Session identifier.
            cell_index: Index of the cell (for reporting).
            cell_source: Source code to execute.
            timeout: Maximum execution time in seconds.

        Returns:
            The cell output as a string, or an error message.
        """
        job_id = str(uuid.uuid4())
        job = ExecutionJob(
            job_id=job_id,
            session_id=session_id,
            cell_index=cell_index,
            status="running",
        )

        with self._lock:
            self._jobs[job_id] = job

        try:
            output_str, error = await asyncio.to_thread(
                self._sync_execute_cell, session_id, cell_source, timeout
            )
            job.output = output_str
            job.error = error
            with self._lock:
                job.status = "failed" if error else "completed"
            return error if error else output_str
        except Exception as e:
            with self._lock:
                job.status = "failed"
            job.error = str(e)
            return f"Error executing cell: {e}"

    async def execute_all_cells(
        self, session_id: str, cells: list[Cell], timeout: int = 60
    ) -> str:
        """Execute all code cells in a notebook sequentially.

        Skips non-code cells and stops on the first execution error.

        Args:
            session_id: Session identifier.
            cells: List of cells to execute.
            timeout: Maximum execution time per cell in seconds.

        Returns:
            Combined output from all cells as a string.
        """
        results = []
        for i, cell in enumerate(cells):
            if cell.cell_type != CellType.CODE:
                continue

            output = await self.execute_cell(session_id, i, cell.source, timeout=timeout)
            results.append(f"--- Cell {i} ---\n{output}")

            if output.startswith("Error executing"):
                results.append(f"\nExecution stopped at cell {i} due to error.")
                break

        if not results:
            return "No code cells found to execute."
        return "\n".join(results)

    # ------------------------------------------------------------------
    # Kernel interrupt / shutdown
    # ------------------------------------------------------------------

    def _sync_interrupt(self, session_id: str) -> None:
        """Interrupt a kernel synchronously.

        Args:
            session_id: Session to interrupt.
        """
        with self._lock:
            if session_id in self._kernels:
                self._kernels[session_id][0].interrupt_kernel()

    async def interrupt(self, session_id: str) -> str:
        """Interrupt the running kernel for a session.

        Args:
            session_id: Session to interrupt.

        Returns:
            A status message.
        """
        if session_id not in await self._list_active_kernels():
            return f"No active kernel for session {session_id}"
        await asyncio.to_thread(self._sync_interrupt, session_id)
        return "Kernel interrupted."

    async def _list_active_kernels(self) -> set[str]:
        """List session IDs with active kernels.

        Returns:
            A set of session IDs.
        """
        with self._lock:
            return set(self._kernels.keys())

    def _sync_shutdown(self, session_id: str) -> None:
        """Shutdown a kernel synchronously.

        Args:
            session_id: Session to shut down.
        """
        km = None
        with self._lock:
            if session_id in self._kernels:
                km = self._kernels.pop(session_id)[0]
        if km is not None:
            km.shutdown_kernel()

    async def shutdown_kernel(self, session_id: str) -> None:
        """Shutdown and cleanup a session's kernel.

        Args:
            session_id: Session to shut down.
        """
        await asyncio.to_thread(self._sync_shutdown, session_id)

    def has_kernel(self, session_id: str) -> bool:
        """Check if a session has an active kernel.

        Args:
            session_id: Session to check.

        Returns:
            ``True`` if a kernel exists for the session.
        """
        with self._lock:
            return session_id in self._kernels

    # ------------------------------------------------------------------
    # Kernel discovery
    # ------------------------------------------------------------------

    def list_kernels(self) -> list[dict]:
        """List available Jupyter kernels from ``jupyter kernelspec``.

        Returns:
            A list of dicts with ``name`` and ``display_name`` keys.
            Returns an empty list if ``jupyter_client`` is not installed.
        """
        try:
            from jupyter_client.kernelspec import KernelSpecManager

            ksm = KernelSpecManager()
            specs = ksm.get_all_specs()
            return [
                {"name": name, "display_name": spec["spec"]["display_name"]}
                for name, spec in specs.items()
            ]
        except ImportError:
            return []
