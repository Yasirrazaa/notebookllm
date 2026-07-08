API Reference
=============

notebookllm.models
------------------

.. automodule:: notebookllm.models

.. autoclass:: notebookllm.models.CellType
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:


.. autoclass:: notebookllm.models.OutputMode
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. autoclass:: notebookllm.models.CellOutput
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. autoclass:: notebookllm.models.Cell
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. autoclass:: notebookllm.models.NotebookDocument
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

notebookllm.loaders
-------------------

.. automodule:: notebookllm.loaders
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: notebookllm.loaders.percent
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: notebookllm.loaders.ipynb
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: notebookllm.loaders.marimo
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: notebookllm.loaders.quarto
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: notebookllm.loaders.markdown
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: notebookllm.loaders.rmarkdown
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: notebookllm.loaders.script
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: notebookllm.loaders.deepnote
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: notebookllm.loaders.base
   :members:
   :undoc-members:
   :show-inheritance:

notebookllm.converters
-----------------------

.. automodule:: notebookllm.converters.llm_optimizer
   :members:
   :undoc-members:
   :show-inheritance:

notebookllm.cli.commands
-------------------------

Command-Line Interface commands are documented on the dedicated :doc:`cli` page.

notebookllm.mcp
----------------

.. automodule:: notebookllm.mcp.server
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: notebookllm.mcp.session

.. autoclass:: notebookllm.mcp.session.Session
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. autoclass:: notebookllm.mcp.session.SessionManager
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: notebookllm.mcp.engine

.. autoclass:: notebookllm.mcp.engine.ExecutionJob
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. autoclass:: notebookllm.mcp.engine.KernelPool
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

notebookllm.utils
------------------

.. automodule:: notebookllm.utils.detect
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: notebookllm.utils.tokenizer

.. autoclass:: notebookllm.utils.tokenizer.CellTokenInfo
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. autoclass:: notebookllm.utils.tokenizer.NotebookTokenReport
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. autofunction:: notebookllm.utils.tokenizer.count_tokens
   :no-index:

.. autofunction:: notebookllm.utils.tokenizer.tokenize_notebook
   :no-index:

.. automodule:: notebookllm.utils.validation

.. autoclass:: notebookllm.utils.validation.ValidationError
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. autoclass:: notebookllm.utils.validation.ValidationReport
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. autofunction:: notebookllm.utils.validation.atomic_write
   :no-index:

.. autofunction:: notebookllm.utils.validation.validate_notebook
   :no-index:

.. autofunction:: notebookllm.utils.validation.validate_filepath
   :no-index:

.. autofunction:: notebookllm.utils.validation.validate_output_format
   :no-index:

.. autofunction:: notebookllm.utils.validation.validate_cell_index
   :no-index:

.. autofunction:: notebookllm.utils.validation.validate_cell_type
   :no-index:
