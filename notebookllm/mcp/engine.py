import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from notebookllm.models import Cell, CellType


@dataclass
class ExecutionJob:
    """Represents an active or completed cell execution."""

    job_id: str
    session_id: str
    cell_index: int
    status: str  # "pending", "running", "completed", "failed", "interrupted"
    output: str = ""
    error: str | None = None


class KernelPool:
    """Manages kernel lifecycle and execution for sessions using a thread pool for blocking kernel calls."""

    def __init__(self, max_workers: int = 4):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._jobs: dict[str, ExecutionJob] = {}
        # session_id -> (KernelManager, KernelClient)
        self._kernels: dict[str, tuple[Any, Any]] = {}

    def _sync_start_kernel(self, session_id: str, kernel_name: str) -> str:
        from jupyter_client import KernelManager

        if session_id in self._kernels:
            return kernel_name

        km = KernelManager(kernel_name=kernel_name)
        km.start_kernel()
        kc = km.client()
        kc.start_channels()
        self._kernels[session_id] = (km, kc)
        return kernel_name

    async def start_kernel(self, session_id: str, kernel_name: str = "python3") -> str:
        """Start a kernel for a session."""
        try:
            import jupyter_client  # type: ignore[import-not-found] # noqa
        except ImportError:
            raise ImportError("notebookllm[execute] not installed. Run: pip install notebookllm[execute]")

        return await asyncio.to_thread(self._sync_start_kernel, session_id, kernel_name)

    def _sync_execute_cell(self, session_id: str, cell_source: str, timeout: int) -> tuple[str, str | None]:
        if session_id not in self._kernels:
            raise RuntimeError(f"Kernel not started for session {session_id}")
        _, client = self._kernels[session_id]

        msg_id = client.execute(cell_source)
        try:
            reply = client.get_shell_msg(timeout=timeout)
        except TimeoutError:
            return "", f"Cell execution timed out after {timeout}s"

        error = None
        if reply["content"]["status"] == "error":
            error = reply["content"]["evalue"]

        # Collect outputs
        outputs = []
        while True:
            try:
                msg = client.get_iopub_msg(timeout=5)
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

    async def execute_cell(self, session_id: str, cell_index: int, cell_source: str, timeout: int = 60) -> str:
        """Execute a cell via blocking client in thread pool, return outputs."""
        job_id = str(uuid.uuid4())
        job = ExecutionJob(
            job_id=job_id,
            session_id=session_id,
            cell_index=cell_index,
            status="running"
        )
        self._jobs[job_id] = job

        try:
            output_str, error = await asyncio.to_thread(self._sync_execute_cell, session_id, cell_source, timeout)
            job.output = output_str
            job.error = error
            job.status = "failed" if error else "completed"
            return error if error else output_str
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            return f"Error executing cell: {e}"

    async def execute_all_cells(self, session_id: str, cells: list[Cell], timeout: int = 60) -> str:
        """Execute code cells sequentially. Skip non-code. Stop on error."""
        results = []
        for i, cell in enumerate(cells):
            if cell.cell_type != CellType.CODE:
                continue
            
            output = await self.execute_cell(session_id, i, cell.source, timeout=timeout)
            results.append(f"--- Cell {i} ---\n{output}")
            
            # If the execution returned an error (which doesn't raise exception but returns the error string/traceback)
            # Actually, `execute_cell` returns the error string if it fails.
            job = [j for j in self._jobs.values() if j.session_id == session_id and j.cell_index == i][-1]
            if job.error:
                results.append(f"\nExecution stopped at cell {i} due to error.")
                break
        
        if not results:
            return "No code cells found to execute."
        return "\n".join(results)

    def _sync_interrupt(self, session_id: str) -> None:
        if session_id in self._kernels:
            km, _ = self._kernels[session_id]
            km.interrupt_kernel()

    async def interrupt(self, session_id: str) -> str:
        """Interrupt the running kernel for a session."""
        if session_id not in self._kernels:
            return f"No active kernel for session {session_id}"
        await asyncio.to_thread(self._sync_interrupt, session_id)
        return "Kernel interrupted."

    def _sync_shutdown(self, session_id: str) -> None:
        if session_id in self._kernels:
            km, _ = self._kernels.pop(session_id)
            km.shutdown_kernel()

    async def shutdown_kernel(self, session_id: str) -> None:
        """Shutdown and cleanup a kernel."""
        await asyncio.to_thread(self._sync_shutdown, session_id)

    def list_kernels(self) -> list[dict]:
        """List available kernels from jupyter kernelspec."""
        try:
            from jupyter_client.kernelspec import KernelSpecManager
            ksm = KernelSpecManager()
            specs = ksm.get_all_specs()
            return [{"name": name, "display_name": spec["spec"]["display_name"]} for name, spec in specs.items()]
        except ImportError:
            return []
