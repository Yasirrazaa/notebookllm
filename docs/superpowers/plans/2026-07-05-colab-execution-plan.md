Google Colab Remote Execution — Research & Integration Plan
=============================================================

**Date:** July 5, 2026
**Status:** Research complete — ready for implementation
**Goal:** Enable ``notebookllm`` to execute notebooks on Google's Colab
         infrastructure (GPUs/TPUs) from CLI and MCP server, with
         one-time OAuth setup.

---

Table of Contents
-----------------

1.  Executive Summary
2.  Research Findings
    a.  google-colab-cli (Official Google Tool)
    b.  Vertex AI Workbench (NotebookExecutionJob API)
    c.  Colab VS Code Extension
    d.  Community Projects (colab-ssh, ngrok tunnels)
    e.  Jupyter Kernel Gateway on GCE
3.  Architecture Comparison
4.  Recommended Integration Design
    a.  Overview
    b.  ColabGatewayBackend Class
    c.  ColabRuntimeManager
    d.  CLI Integration
    e.  MCP Server Integration
    f.  Workflow Walkthrough
5.  Implementation Phases
    Phase 1 — Colab CLI wrapping & execution
    Phase 2 — MCP server integration
    Phase 3 — File I/O & output retrieval
    Phase 4 — Multi-backend architecture
    Phase 5 — Vertex AI Workbench production path
6.  Risks & Mitigations
7.  Open Questions

---

1. Executive Summary
--------------------

``notebookllm`` currently executes cells locally via ``KernelPool``
(``jupyter_client``). We want to add the ability to execute notebooks
on **Google Colab's cloud infrastructure** — giving users access to
GPUs (T4, L4, A100, H100) and TPUs (v5e, v6e) without local hardware.

**The most practical path is ``google-colab-cli``**, an official Google
tool released in early 2026. It provides:

-   One-time OAuth (browser popup → cached refresh token)
-   Runtime provisioning with GPU/TPU selection
-   Script and notebook execution on remote kernels
-   Output retrieval (log export to .ipynb / .md / .jsonl)
-   Linux and macOS support

A secondary production path uses **Vertex AI Workbench's
NotebookExecutionJob API**, which is fully managed and API-driven but
requires a GCP project and batch-only execution.

---

2. Research Findings

### a. google-colab-cli (Official Google Tool)

**Repository:** https://github.com/googlecolab/google-colab-cli
**Installation:**

.. code-block:: bash

    pip install google-colab-cli
    # or
    uv tool install google-colab-cli

**Binary name:** ``colab``

**Authentication (one-time):**

.. code-block:: bash

    colab auth login
    # Opens browser → OAuth consent → token cached in ~/.config/colab-cli/

**Core subcommands:**

+----------------+----------------------------------------------------+
| Command        | Purpose                                            |
+================+====================================================+
| ``auth``       | Login/logout, manage OAuth credentials             |
+----------------+----------------------------------------------------+
| ``new``        | Create a new runtime session with optional GPU/TPU |
+----------------+----------------------------------------------------+
| ``sessions``   | List active sessions and their status              |
+----------------+----------------------------------------------------+
| ``status``     | Show session details (hardware, uptime, kernel)    |
+----------------+----------------------------------------------------+
| ``run``        | Ephemeral: provision → execute → teardown          |
+----------------+----------------------------------------------------+
| ``exec``       | Execute code/scripts in an existing session        |
+----------------+----------------------------------------------------+
| ``repl``       | Interactive Python REPL on the remote VM           |
+----------------+----------------------------------------------------+
| ``console``    | Full TTY shell on the remote VM                    |
+----------------+----------------------------------------------------+
| ``log``        | Export session history to .ipynb / .md / .jsonl   |
+----------------+----------------------------------------------------+
| ``stop``       | Terminate a runtime session                        |
+----------------+----------------------------------------------------+
| ``restart-kernel`` | Restart the kernel in a session               |
+----------------+----------------------------------------------------+
| ``upload``     | Upload files to the remote runtime                 |
+----------------+----------------------------------------------------+
| ``download``   | Download files from the remote runtime             |
+----------------+----------------------------------------------------+
| ``ls``         | List files on the remote runtime                   |
+----------------+----------------------------------------------------+

**Ephemeral execution (``colab run``):**

.. code-block:: bash

    # Execute a Python script with GPU, auto-teardown
    colab run --gpu A100 train.py --epochs 50

    # Execute with TPU
    colab run --tpu v6e1 train.py

    # Keep the runtime alive for debugging
    colab run --gpu T4 --keep experiment.py

**Execute in persistent session (``colab exec``):**

.. code-block:: bash

    # Requires an active session (created via `colab new`)
    colab exec -f notebook.ipynb

    # Execute raw code
    colab exec -c "print('hello from colab')"

**Output retrieval:**

.. code-block:: bash

    # Export session log as .ipynb
    colab log -s <session_id> -o results.ipynb

    # Export as JSONL for programmatic parsing
    colab log -s <session_id> -o results.jsonl

**Key limitations:**

-   **Linux/macOS only** — no Windows support
-   **No native Python SDK** — must shell out to the CLI binary
-   **No direct ``jupyter_client`` gateway** — you cannot connect your
    own IDE to the kernel; execution is mediated by the CLI
-   **Requires internet** — the remote VM is provisioned in Google's
    data centers
-   **Free tier limits apply** — same usage quotas as Colab web UI

---

### b. Vertex AI Workbench (NotebookExecutionJob API)

**What it is:** Google Cloud's managed service for batch execution of
Jupyter notebooks on GCP infrastructure.

**API:** ``google.cloud.aiplatform`` Python SDK

**Basic usage:**

.. code-block:: python

    from google.cloud import aiplatform

    aiplatform.init(project="my-project", location="us-central1")

    parent = f"projects/my-project/locations/us-central1"
    job = {
        "display_name": "train-model",
        "gcs_notebook_source": {"uri": "gs://my-bucket/nb.ipynb"},
        "gcs_output_uri": "gs://my-bucket/output/",
        "custom_environment_spec": {
            "machine_spec": {
                "machine_type": "n1-standard-4",
                "accelerator_type": "NVIDIA_TESLA_T4",
                "accelerator_count": 1,
            }
        },
        "service_account": "sa@my-project.iam.gserviceaccount.com",
    }

    client = aiplatform.gapic.NotebookServiceClient()
    client.create_notebook_execution_job(
        parent=parent,
        notebook_execution_job=job,
    )

**Key characteristics:**

+---------------------------+------------------------------------------+
| Aspect                   | Detail                                   |
+===========================+==========================================+
| Execution model          | **Batch only** — spin up, run, teardown |
+---------------------------+------------------------------------------+
| Persistent kernel        | ❌ No — cannot connect to live kernel   |
+---------------------------+------------------------------------------+
| GPU/TPU support          | ✅ Full (T4, L4, A100, H100, TPU)      |
+---------------------------+------------------------------------------+
| Input                    | Notebook in GCS bucket                   |
+---------------------------+------------------------------------------+
| Output                   | Executed notebook saved to GCS           |
+---------------------------+------------------------------------------+
| Authentication           | Service account (IAM)                    |
+---------------------------+------------------------------------------+
| Pricing                  | Pay per node-hour + storage              |
+---------------------------+------------------------------------------+
| Best for                 | Production pipelines, scheduled jobs     |
+---------------------------+------------------------------------------+

**Tradeoff:** Fully managed and API-driven, but requires a GCP project
with billing enabled and is batch-only — you cannot use it for
interactive "execute this cell now" workflows.

---

### c. Colab VS Code Extension

**What it is:** A VS Code extension that lets you select a Colab runtime
as a Jupyter kernel within VS Code.

**Protocol:** Uses standard Jupyter Messaging Protocol (ZMQ via
WebSockets) proxied through Google's infrastructure. Authentication is
handled by the extension's OAuth flow.

**Why it can't be reused programmatically:**

-   Tokens are stored in VS Code's ``SecretStorage``
    (OS keychain — macOS Keychain, Windows Credential Manager, Linux
    libsecret). They are **isolated** to the VS Code extension process.
-   The OAuth client ID is scoped to the extension — tokens from it
    won't work for a CLI tool.
-   The extension does not expose a stable file-based credential store
    or a socket for external tools to connect to.

**Verdict:** Interactive-only. Cannot be leveraged by ``notebookllm``.

---

### d. Community Projects (colab-ssh, ngrok tunnels)

These projects (e.g., ``WassimBenzarti/colab-ssh``) work by executing
tunneling code **inside an already-running Colab web session**:

.. code-block:: python

    # Inside a Colab cell — must be manually run in the browser
    !pip install colab-ssh
    from colab_ssh import launch_ssh
    launch_ssh("my-password")

They install ``cloudflared`` or ``ngrok`` inside the ephemeral VM and
create an outbound tunnel, which your local machine then connects to.

**Why this is impractical for notebookllm:**

-   **Requires manual browser session start** — a human must open Colab,
    create a notebook, and run the tunneling cell
-   **Fragile** — tunnels break on reconnection, Colab VM preemptions
-   **Not automatable** — you cannot script the initial session creation
-   **Violates Colab ToS** for some tunneling methods
-   **No production reliability**

**Verdict:** Interesting hack, not a foundation for a product feature.

---

### e. Jupyter Kernel Gateway on GCE

**What it is:** Running the
`Jupyter Kernel Gateway <https://jupyter-kernel-gateway.readthedocs.io/>`_
on a Google Compute Engine VM, exposing a REST + WebSocket API for
kernel management.

**Workflow:**

1.  Provision a GCE VM with GPU (e.g., ``gcloud compute instances create``)
2.  Install Jupyter Kernel Gateway
3.  Start it as a systemd service: ``jupyter kernelgateway --KernelGatewayApp.ip=0.0.0.0``
4.  Connect from notebookllm via ``jupyter_client`` using the gateway's
    WebSocket URL

**Pros:** Full control, persistent kernels, any GPU type, no OAuth
(token-based auth)

**Cons:** Requires GCP project + billing, manual VM management (or
automation via Terraform/Pulumi), security hardening needed (HTTPS,
auth tokens), VM costs even when idle

**Verdict:** Best for teams that already manage GCP infrastructure and
need persistent, stateful kernel sessions. Overkill for most notebookllm
users.

---

3. Architecture Comparison
--------------------------

+-----------------------------------+----------+----------+------------+-------------+
| Criteria                          | colab-cli| Vertex AI| Kernel Gwy | VS Code Ext |
+===================================+==========+==========+============+=============+
| One-time OEM auth                 | ✅       | ✅ (SA)  | ❌ (manual)| ✅ (but     |
|                                   |          |          | VM setup)  | locked)     |
+-----------------------------------+----------+----------+------------+-------------+
| GPU/TPU support                   | ✅       | ✅       | ✅         | ✅          |
+-----------------------------------+----------+----------+------------+-------------+
| Persistent kernel (stateful)      | ✅       | ❌ batch | ✅         | ✅          |
+-----------------------------------+----------+----------+------------+-------------+
| Programmatic (no UI required)     | ✅       | ✅       | ✅         | ❌          |
+-----------------------------------+----------+----------+------------+-------------+
| Free tier available               | ✅       | ❌       | ❌         | ✅          |
|                                   |          | (GCP $)  | (GCP $)    |             |
+-----------------------------------+----------+----------+------------+-------------+
| Python SDK                        | ❌ (CLI) | ✅       | ✅         | ❌          |
|                                   |          |          | (jupyter)  |             |
+-----------------------------------+----------+----------+------------+-------------+
| Works without GCP project         | ✅       | ❌       | ❌         | ✅          |
+-----------------------------------+----------+----------+------------+-------------+
| Cell-level execution              | ✅       | ❌       | ✅         | ✅          |
+-----------------------------------+----------+----------+------------+-------------+
| Output capture & retrieval        | ✅       | ✅       | ✅         | ✅          |
+-----------------------------------+----------+----------+------------+-------------+
| Production-grade                  | ❌ (new) | ✅       | ✅         | N/A         |
|                                   | (preview)|          |            |             |
+-----------------------------------+----------+----------+------------+-------------+
| Supported platforms               | Linux/   | Linux/   | Linux/     | Linux/      |
|                                   | macOS    | macOS    | macOS/Win  | macOS/Win   |
+-----------------------------------+----------+----------+------------+-------------+

---

4. Recommended Integration Design
----------------------------------

### a. Overview

We recommend a **two-tier approach**:

1.  **Phase 1–4 (immediate):** Wrap ``google-colab-cli`` as a remote
    backend for notebookllm. This gives users Colab GPU/TPU access with
    one-time auth and no GCP project requirement.
2.  **Phase 5 (future):** Add a Vertex AI Workbench backend for
    production/batch pipelines that require GCP-managed infrastructure.

### b. ColabGatewayBackend Class

A new class in ``notebookllm/mcp/engine.py`` (or a new module
``notebookllm/execution/colab.py``) that wraps the ``colab`` CLI:

.. code-block:: python

    """Remote execution backend using google-colab-cli."""

    import subprocess
    import json
    import tempfile
    from pathlib import Path
    from dataclasses import dataclass

    @dataclass
    class ColabRuntimeSpec:
        """Hardware specification for a Colab runtime."""
        accelerator: str | None = None        # e.g. "T4", "A100", "L4"
        tpu: str | None = None                # e.g. "v5e1", "v6e1"
        region: str = "us-west1"
        keep_alive: bool = False


    class ColabGatewayBackend:
        """Manages Colab runtime sessions via the colab CLI."""

        @staticmethod
        def check_installed() -> bool:
            """Verify colab CLI is available and authenticated."""
            result = subprocess.run(
                ["colab", "auth", "status"],
                capture_output=True, text=True
            )
            return result.returncode == 0

        @staticmethod
        def auth_login() -> dict:
            """Trigger one-time OAuth (browser popup)."""
            result = subprocess.run(
                ["colab", "auth", "login", "--json"],
                capture_output=True, text=True
            )
            return json.loads(result.stdout)

        def create_session(self, spec: ColabRuntimeSpec) -> str:
            """Provision a new Colab runtime.

            Returns the session ID.
            """
            cmd = ["colab", "new", "--json"]
            if spec.accelerator:
                cmd += ["--gpu", spec.accelerator]
            if spec.tpu:
                cmd += ["--tpu", spec.tpu]
            cmd += ["--region", spec.region]

            result = subprocess.run(cmd, capture_output=True, text=True)
            data = json.loads(result.stdout)
            return data["session_id"]

        def execute_cell(self, session_id: str, code: str) -> dict:
            """Execute a code cell on the remote runtime."""
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False
            ) as f:
                f.write(code)
                script_path = f.name

            result = subprocess.run(
                ["colab", "exec", "-f", script_path,
                 "-s", session_id, "--json"],
                capture_output=True, text=True
            )
            Path(script_path).unlink()
            return json.loads(result.stdout)

        def execute_notebook(self, session_id: str,
                             notebook_path: str) -> dict:
            """Execute a .ipynb file on the remote runtime."""
            result = subprocess.run(
                ["colab", "exec", "-f", notebook_path,
                 "-s", session_id, "--json"],
                capture_output=True, text=True
            )
            return json.loads(result.stdout)

        def upload_file(self, session_id: str,
                        local_path: str, remote_path: str) -> None:
            subprocess.run(
                ["colab", "upload", local_path, remote_path,
                 "-s", session_id]
            )

        def download_file(self, session_id: str,
                          remote_path: str, local_path: str) -> None:
            subprocess.run(
                ["colab", "download", remote_path, local_path,
                 "-s", session_id]
            )

        def export_log(self, session_id: str,
                       output_path: str,
                       fmt: str = "ipynb") -> str:
            """Export session history to a file.

            Supported formats: ipynb, md, jsonl
            """
            result = subprocess.run(
                ["colab", "log", "-s", session_id,
                 "-o", output_path, "--format", fmt],
                capture_output=True, text=True
            )
            return output_path

        def stop_session(self, session_id: str) -> None:
            """Terminate a Colab runtime."""
            subprocess.run(["colab", "stop", session_id])

        def list_sessions(self) -> list[dict]:
            """List all active Colab sessions."""
            result = subprocess.run(
                ["colab", "sessions", "--json"],
                capture_output=True, text=True
            )
            return json.loads(result.stdout)

### c. ColabRuntimeManager

A higher-level manager that integrates with notebookllm's existing
session lifecycle (currently in ``mcp/session.py``):

.. code-block:: python

    class ColabRuntimeManager:
        """Manages the lifecycle of Colab runtimes for MCP sessions."""

        def __init__(self):
            self.backend = ColabGatewayBackend()
            self.runtimes: dict[str, ColabRuntimeSpec] = {}

        async def start_runtime(
            self, session_id: str, spec: ColabRuntimeSpec
        ) -> str:
            """Provision a Colab runtime for an MCP session."""
            colab_session = self.backend.create_session(spec)
            self.runtimes[colab_session] = spec
            # Store mapping in session metadata
            return colab_session

        async def shutdown_runtime(self, colab_session: str) -> None:
            """Cleanly terminate a Colab runtime."""
            self.backend.export_log(
                colab_session, f"colab-logs/{colab_session}.ipynb"
            )
            self.backend.stop_session(colab_session)
            self.runtimes.pop(colab_session, None)

        async def shutdown_all(self) -> None:
            """Terminate all managed Colab runtimes."""
            for colab_session in list(self.runtimes.keys()):
                await self.shutdown_runtime(colab_session)

### d. CLI Integration

New flags for ``notebookllm`` commands:

.. code-block:: bash

    # Execute on local kernels (existing behavior)
    notebookllm convert notebook.ipynb -o output.ipynb

    # Execute on Colab with GPU
    notebookllm convert notebook.ipynb -o output.ipynb \
        --execute \
        --backend colab \
        --gpu T4

    # Ephemeral: convert → execute on Colab → download executed notebook
    notebookllm execute notebook.ipynb \
        --backend colab \
        --gpu A100 \
        --output results.ipynb

    # Interactive: start a persistent Colab session
    notebookllm server --backend colab --gpu L4

Sample new CLI commands:

.. code-block:: bash

    # Auth
    notebookllm colab auth
    notebookllm colab sessions

    # Execute on Colab
    notebookllm colab run script.py --gpu A100 --keep
    notebookllm colab run notebook.ipynb --gpu T4

### e. MCP Server Integration

New MCP tools exposed by the server:

+------------------+--------------------------------------------------+
| Tool             | Description                                      |
+==================+==================================================+
| ``colab_auth``   | Trigger one-time OAuth or check auth status      |
+------------------+--------------------------------------------------+
| ``colab_start``  | Provision a new Colab runtime with accelerator   |
+------------------+--------------------------------------------------+
| ``colab_exec``   | Execute code on a Colab runtime                  |
+------------------+--------------------------------------------------+
| ``colab_stop``   | Terminate a Colab runtime                        |
+------------------+--------------------------------------------------+
| ``colab_list``   | List active Colab sessions                       |
+------------------+--------------------------------------------------+
| ``colab_upload`` | Upload files to Colab runtime                    |
+------------------+--------------------------------------------------+
| ``colab_log``    | Export session log as notebook (for results)     |
+------------------+--------------------------------------------------+

New resource:

+--------------------------------+---------------------------------------+
| Resource URI                   | Content                               |
+================================+=======================================+
| ``colab://{session_id}/status`` | JSON with accelerator, uptime, kernel |
+--------------------------------+---------------------------------------+

### f. Workflow Walkthrough

**User workflow (from fresh install):**

::

    1. Install notebookllm with Colab extras:
       pip install notebookllm[colab]

    2. Authenticate (one-time):
       notebookllm colab auth
       → Browser opens → user logs into Google → token cached

    3. Execute a notebook on a T4 GPU:
       notebookllm execute model_training.ipynb \
           --backend colab \
           --gpu T4 \
           --output trained_results.ipynb

       Under the hood:
       a. colab new --gpu T4 → provisions VM, returns session_id
       b. Upload model_training.ipynb to the VM
       c. colab exec -f model_training.ipynb -s <session_id>
       d. colab log -s <session_id> -o trained_results.ipynb
       e. Download trained_results.ipynb
       f. colab stop <session_id>

    4. Or use the MCP server for interactive cell execution:
       notebookllm server --backend colab --gpu L4
       → AI agent sends `execute` → runs on Colab GPU
       → Results stream back via MCP

    5. Done. Token persists for future sessions.

---

5. Implementation Phases
------------------------

### Phase 1 — Colab CLI Wrapping & Basic Execution (1–2 weeks)

**Goal:** ``notebookllm colab run`` command works end-to-end.

-   [ ] Add ``ColabGatewayBackend`` class in
    ``notebookllm/execution/colab.py``
-   [ ] Implement ``check_installed()``, ``auth_login()``,
    ``create_session()``, ``execute_cell()``, ``stop_session()``
-   [ ] Add ``notebookllm colab`` CLI subcommand group with:
    -   ``auth`` — trigger login, show status
    -   ``run`` — ephemeral execution of a file
    -   ``sessions`` — list active sessions
    -   ``stop`` — terminate a session
-   [ ] Error handling: missing CLI, auth failures, quota exceeded,
    runtime preemption
-   [ ] Add ``[colab]`` extras in ``pyproject.toml``
    (``google-colab-cli`` as optional dep — or just system-installed CLI
    since it's a standalone binary)

**Dependencies:** ``pip install google-colab-cli`` (user-side)
**Testing:** Integration tests with ``colab --dry-run`` or mock CLI

---

### Phase 2 — MCP Server Integration (1 week)

**Goal:** AI agents can execute cells on Colab GPUs via MCP tools.

-   [ ] Add ``ColabRuntimeManager`` that maps MCP session IDs to Colab
    runtime sessions
-   [ ] Register MCP tools: ``colab_auth``, ``colab_start``,
    ``colab_exec``, ``colab_stop``, ``colab_list``
-   [ ] Register MCP resource: ``colab://{session_id}/status``
-   [ ] Integrate with existing ``Session`` lifecycle — auto-start
    Colab runtime when backend="colab" is specified
-   [ ] Add ``--backend`` / ``--gpu`` / ``--tpu`` flags to
    ``notebookllm server``

**Key design decision:** Should the MCP session automatically provision
a Colab runtime, or should the AI agent call ``colab_start``
explicitly? **Recommendation:** Explicit — let the agent decide.
However, add a ``session_start`` lifecycle hook for the
``--backend colab`` flag.

---

### Phase 3 — File I/O & Output Retrieval (1 week)

**Goal:** Full round-trip: local notebook → Colab execution →
executed notebook downloaded.

-   [ ] Implement ``upload_file()`` and ``download_file()`` in backend
-   [ ] Implement ``export_log()`` to retrieve executed notebook
-   [ ] Add ``notebookllm execute`` CLI command:
    -   Converts notebook to script (via existing converters)
    -   Uploads to Colab runtime
    -   Executes via ``colab exec -f``
    -   Downloads executed notebook or exports log
-   [ ] Handle large file transfers, retry logic, timeout

---

### Phase 4 — Multi-backend Architecture (1 week)

**Goal:** ``KernelPool`` becomes a pluggable backend system.

-   [ ] Define abstract ``ExecutionBackend`` interface:

    .. code-block:: python

        class ExecutionBackend(ABC):
            @abstractmethod
            def execute_cell(self, code: str, timeout: int) -> CellOutput: ...

            @abstractmethod
            def interrupt(self) -> None: ...

            @abstractmethod
            def restart_kernel(self) -> None: ...

            @abstractmethod
            def shutdown(self) -> None: ...

-   [ ] Refactor ``KernelPool`` → ``LocalKernelBackend`` (implements
    above, uses ``jupyter_client`` — identical to current behavior)
-   [ ] ``ColabGatewayBackend`` implements the same interface
-   [ ] ``KernelPool`` selects backend based on config

**Result:** This design pattern lets us add any future backend (SSH
gateway, remote Jupyter server, Docker container) by implementing a
single interface.

---

### Phase 5 — Vertex AI Workbench Backend (Future)

**Goal:** Production-grade batch execution via GCP APIs.

-   [ ] Add ``VertexAIBackend`` implementing ``ExecutionBackend``
-   [ ] Uses ``google-cloud-aiplatform`` SDK
-   [ ] Requires GCP project, service account, GCS bucket
-   [ ] Batch-only (no cell-level execution)
-   [ ] ``notebookllm execute --backend vertex-ai --gpu T4 --project my-project``

This is deliberately deferred — most users will benefit more from the
simpler ``colab`` CLI approach first.

---

6. Risks & Mitigations
-----------------------

+--------------------------------------+-----------------------------------+
| Risk                                 | Mitigation                        |
+======================================+===================================+
| ``google-colab-cli`` is new — may    | Pin known-good version. Monitor   |
| have breaking changes or bugs        | GitHub releases. Add integration  |
|                                      | tests with a ``--dry-run`` flag.  |
+--------------------------------------+-----------------------------------+
| Colab free-tier quotas (GPU hours)   | Clearly document limits. Detect   |
|                                      | quota errors from CLI output and  |
|                                      | surface user-friendly messages.   |
+--------------------------------------+-----------------------------------+
| Users may not have ``colab`` CLI     | ``check_installed()`` returns     |
| installed                            | clear error + install instructions|
+--------------------------------------+-----------------------------------+
| Runtime preemption (Colab VMs are    | Add ``--keep-alive`` flag and     |
| ephemeral, can be terminated)        | background keepalive daemon.      |
|                                      | Export log before shutdown.       |
+--------------------------------------+-----------------------------------+
| OAuth token expiry                   | ``colab auth login --json``       |
|                                      | returns expiry info; prompt       |
|                                      | re-auth when expired.             |
+--------------------------------------+-----------------------------------+
| Colab CLI output parsing fragility   | Always use ``--json`` flag for    |
|                                      | structured output. Validate       |
|                                      | expected fields, fail gracefully. |
+--------------------------------------+-----------------------------------+
| No Windows support for colab-cli     | Document as Linux/macOS only.     |
|                                      | Windows users can use WSL2 or     |
|                                      | Vertex AI backend (future).       |
+--------------------------------------+-----------------------------------+

---

7. Open Questions
-----------------

These should be resolved before or during Phase 1 implementation:

1.  **Should ``google-colab-cli`` be a Python dependency or a
    system-installed CLI?**
    -   As a Python dep: ``pip install notebookllm[colab]`` installs it
        → consistent, versioned
    -   As system dep: user installs separately → more flexible, avoids
        dependency conflicts
    -   **Recommendation:** Make it a Python optional dep in
        ``pyproject.toml`` under ``[project.optional-dependencies]``
        using ``google-colab-cli``

2.  **What should the MCP session lifecycle look like?**
    -   Option A: ``notebookllm server --backend colab`` provisions a
        Colab runtime at startup
    -   Option B: Agent calls ``colab_start`` explicitly
    -   **Recommendation:** Support both — CLI flags for automatic
        provisioning, MCP tools for manual control

3.  **How should output be retrieved for ``notebookllm execute``?**
    -   Option A: ``colab exec -f notebook.ipynb`` runs it, then
        ``colab log -o results.ipynb`` exports
    -   Option B: Modify notebook in-place on the remote VM, then
        download it
    -   **Recommendation:** Option A — cleaner separation, uses the
        tool as designed

4.  **Should we support ``colab run`` (ephemeral) or ``colab new`` +
    ``colab exec`` (persistent) as the default?**
    -   ``colab run``: Simpler for batch jobs, auto-teardown
    -   ``colab new`` + ``colab exec``: Better for interactive use,
        debugging
    -   **Recommendation:** ``colab run`` for ``notebookllm execute``
        (CLI), ``colab new`` + ``colab exec`` for MCP server. Use
        ``--keep`` flag when user wants persistence.

5.  **Should we limit Colab execution to ``notebookllm convert
    --execute`` or add a new ``notebookllm execute`` command?**
    -   **Recommendation:** Add ``notebookllm execute`` as a separate
        command. It's a different workflow from conversion and deserves
        its own entry point. The convert command already has ``--execute``
        for local execution; ``notebookllm execute`` extends this to
        remote backends.

---

Appendix A: Existing Architecture References
---------------------------------------------

Key files that will be modified or extended:

.. code-block:: text

    notebookllm/
    ├── cli/
    │   └── commands.py      ← Add ``colab`` and ``execute`` commands
    ├── mcp/
    │   ├── server.py        ← Register colab tools
    │   ├── session.py       ← Hook into session lifecycle
    │   └── engine.py        ← KernelPool → multi-backend refactor
    ├── execution/            ← NEW module
    │   ├── __init__.py
    │   ├── base.py          ← ExecutionBackend ABC
    │   ├── local.py         ← LocalKernelBackend (refactored KernelPool)
    │   └── colab.py         ← ColabGatewayBackend (NEW)
    └── converters/
        └── llm_optimizer.py ← May need minor adjustments

---

Appendix B: Alternative: Direct Colab Kernel Connection
--------------------------------------------------------

There is one additional speculative approach worth noting for the
future: if the ``google-colab-cli`` exposes kernel connection info
(e.g., a WebSocket URL and auth token) in its JSON output, we could
potentially connect ``jupyter_client`` directly to the Colab kernel
via ZMQ over WebSockets. This would give us:

-   Cell-level execution with output streaming
-   Interrupt support
-   Stateful kernel (variables persist between cells)

As of the current version, ``google-colab-cli`` does not expose this.
If it becomes available in a future release, we should add a
``DirectColabBackend`` that uses ``jupyter_client`` instead of shelling
out to the CLI.

---

**End of plan.**
