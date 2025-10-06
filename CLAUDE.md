# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LocalLM is a terminal-based AI knowledge base system that uses local LLMs (via Ollama) to answer questions about documents in the current directory. The system uses an "AI Active Exploration" paradigm - trusting the AI to intelligently explore documents rather than pre-chunking everything (like traditional RAG).

**Core Concept**: Instead of vector embeddings and chunking, LocalLM generates a `knowledge_map.yaml` with AI-generated descriptions of each document. When asked a question, the AI agent reads the map, decides which documents are relevant, and uses tools (`read_file`, `grep`, `list_docs`) to explore them.

## Installation & Setup

```bash
# Install dependencies
pip install -e .
pip install -r requirements.txt

# Verify Ollama is running and Qwen3 is available
ollama list
ollama pull qwen3:latest
```

## Common Commands

### Development
```bash
# Install package in editable mode
pip install -e .

# Run the CLI (after installation)
locallm                          # Start chat mode
locallm chat                     # Start chat mode explicitly
locallm ask "question here"      # Ask a single question
locallm list                     # List all documents
locallm search "keyword"         # Search documents for keyword
locallm rebuild-map              # Rebuild knowledge map
locallm rebuild-map --fast       # Fast mode: AI reads TOC only
```

### Testing
```bash
# Test map generation
python test_map.py
```

## Architecture

### Project Structure
```
locallm/
├── agents/
│   ├── explorer.py       # DocumentExplorer - main AI agent with tool-calling loop
│   └── prompts.py        # System prompts for the agent
├── tools/
│   ├── file_ops.py       # read_file, grep, list_docs tools
│   └── map_generator.py  # Knowledge map generation logic
├── cli.py                # Click-based CLI commands
└── utils/                # Utilities (currently empty)
```

### Key Components

1. **DocumentExplorer** (`locallm/agents/explorer.py`)
   - Main AI agent class that handles question answering
   - Uses Ollama's chat API with streaming for interruptibility
   - Implements a simple tool-calling loop (max 10 iterations)
   - Parses "Action:" and "Action Input:" from LLM responses
   - Maintains conversation history for chat mode
   - Two modes: `ask()` for Q&A with tools, `chat()` for simple conversation

2. **Knowledge Map** (`knowledge_map.yaml`)
   - Auto-generated YAML file describing all documents
   - Each entry contains: id, title, path, file_type, size, description, key_concepts
   - AI generates 200-300 word descriptions using first+last 8000 chars of each doc
   - Key concepts extracted using AI or regex fallback
   - Fast mode: extracts TOC/abstract and generates description from that

3. **Tools** (`locallm/tools/file_ops.py`)
   - `read_file(file_path)`: Reads complete document (PDF/DOCX/TXT/MD)
   - `grep(pattern, file_path, context_lines=3)`: Regex search with context
   - `list_docs(directory)`: Lists all supported documents
   - Uses custom `Tool` wrapper class (not LangChain's)

4. **CLI** (`locallm/cli.py`)
   - Click-based command interface
   - Implements Ctrl+C interrupt handling (press twice to exit)
   - Uses Rich library for beautiful terminal output
   - All commands support keyboard interruption

### AI Agent Workflow

When user asks a question via `locallm ask "question"`:

1. Load/generate knowledge map (cached after first load)
2. Construct system prompt with full knowledge map YAML
3. Iterative loop (max 10 iterations):
   - Send messages to Ollama with streaming
   - Parse response for "Action:" and "Action Input:"
   - If tool call detected, execute tool and add "Observation:" to conversation
   - If "Final Answer:" detected, return answer to user
   - If no action/answer on last iteration, treat response as final answer

### Ollama Integration

- Uses `ollama` Python package (not LangChain)
- Streaming enabled for interruptibility (KeyboardInterrupt handling)
- Default model: `qwen3:latest`
- Temperature: 0.3 (configurable in `config.yaml`)
- No function calling API - uses prompt-based tool invocation with text parsing

## Important Design Patterns

### Ctrl+C Interrupt Handling
The codebase implements double Ctrl+C pattern throughout:
- First Ctrl+C: Shows warning, waits 2 seconds
- Second Ctrl+C: Actually exits
- Implemented in `chat`, `ask`, and `rebuild_map` commands

### Streaming for Interruptibility
All Ollama calls use `stream=True` to allow graceful interruption:
```python
stream = ollama.chat(model=self.model, messages=messages, stream=True)
for chunk in stream:
    # Process chunk - can be interrupted with KeyboardInterrupt
```

### Tool Invocation Format
The AI is prompted to use this format (parsed in `explorer.py`):
```
Action: read_file
Action Input: path/to/document.pdf

Observation: [tool output]

Final Answer: [answer with citations]
```

### Knowledge Map Generation Strategy
- **Full mode** (`use_ai=True`): AI reads 60% head + 40% tail (up to 8000 chars)
- **Fast mode** (`use_ai=False` or `--fast`): Extracts TOC/abstract, AI summarizes that
- Cleans up AI thinking tags: `<think>`, `<thinking>`
- Progress bar shows real-time processing status

## Configuration

Edit `config.yaml` for settings:
- Ollama model, temperature, timeout
- Agent max iterations, verbosity
- Supported document types
- Knowledge map settings

## Dependencies

Core dependencies (see `requirements.txt`):
- `ollama>=0.1.0` - Local LLM interface
- `rich>=13.0.0` - Terminal UI
- `click>=8.0.0` - CLI framework
- `pymupdf>=1.23.0` - PDF reading (PyMuPDF/fitz)
- `python-docx>=1.1.0` - Word documents
- `pyyaml>=6.0.0` - YAML parsing

## Development Notes

### When adding new document formats:
1. Add extension to `supported_exts` in `file_ops.py` and `map_generator.py`
2. Add reader function (e.g., `_read_epub()`) in `file_ops.py`
3. Update config.yaml `documents.supported_types`

### When modifying AI behavior:
- System prompts are in `locallm/agents/prompts.py`
- Tool descriptions are in tool docstrings (the AI reads these)
- Adjust temperature in `config.yaml` or pass `--model` to CLI

### When debugging tool calls:
- Enable verbose mode: `locallm ask "question" --verbose`
- Check console output - shows each iteration, action, and observation
- `explorer.py` prints iteration numbers and truncated responses

### Testing knowledge map generation:
```bash
# Full mode (slower, higher quality)
locallm rebuild-map

# Fast mode (reads TOC only)
locallm rebuild-map --fast
```

## Philosophy: AI Active Exploration vs RAG

Traditional RAG:
- Pre-chunks all documents
- Creates vector embeddings
- Retrieves chunks based on similarity
- AI sees fragments without full context

LocalLM approach:
- AI reads complete documents on-demand
- Knowledge map provides "menu" of what's available
- AI decides what to read and can explore further
- Full context preservation, better for complex questions
- Higher latency but better accuracy for document Q&A

## Known Limitations

- Ollama must be running locally
- Requires Qwen3 or compatible model
- No built-in vector search (relies on AI reasoning)
- Token consumption higher than RAG (full document reads)
- Best for 50-500 documents (not tested on larger corpora)

## Recent Optimizations

See [UPDATES.md](UPDATES.md) for detailed changelog.

Latest improvements (v0.8.2):
- ⚡ 40% faster knowledge map generation (3 sec/file vs 5 sec/file)
- 🎯 Stable progress bar (no more flickering)
- ⏱️ Time estimation for map generation
- 🎨 Beautiful terminal UI with Rich library

# important-instruction-reminders

## 文檔管理原則
**重要**: 本專案使用 **單一優化文檔** (`UPDATES.md`) 記錄所有改進。

- ✅ **每次優化後更新 `UPDATES.md`**，在文件開頭添加新版本
- ❌ **不要創建** `PERFORMANCE_IMPROVEMENTS.md` 或其他額外的摘要文檔
- 📝 格式: 每個版本包含「解決的問題」、「改進措施」、「效能提升」、「修改檔案」

Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.
