# LocalLM - Local Knowledge Base System

A terminal-based AI knowledge base system that reads documents in your current directory and answers questions about them.

## Features

- 🤖 **AI-Powered Q&A**: Ask questions about your documents using Qwen3
- 💬 **Interactive Chat**: Have conversations with the AI
- 🗂️ **Smart Document Discovery**: Automatic knowledge map generation
- 🔍 **Document Search**: Search for keywords across all documents
- 📚 **Multi-Format Support**: PDF, DOCX, TXT, Markdown

## Prerequisites

1. **Python 3.8+**
2. **Ollama** installed and running
3. **Qwen3 model** downloaded

### Install Ollama & Qwen3

```bash
# Install Ollama (Windows)
# Download from: https://ollama.com/download

# Pull Qwen3 model
ollama pull qwen3:latest

# Verify it's running
ollama list
```

## Installation

```bash
cd locallm-v0.8
pip install -e .
pip install -r requirements.txt
```

## Usage

### 1. Interactive Chat Mode

Start a conversation with the AI:

```bash
locallm chat
```

Example:
```
You: Hello! How are you?
AI: I'm doing great! How can I help you today?

You: What can you do?
AI: I can help you understand documents in your current directory...

You: exit
```

### 2. Ask Questions About Documents

Ask a one-time question:

```bash
locallm ask "What is the main topic of this report?"
```

The AI will:
- Load/generate knowledge map
- Identify relevant documents
- Read them
- Answer your question with sources

### 3. List Documents

See all documents in the current directory:

```bash
locallm list
```

Output:
```
┌────────────────────────────────────────────┐
│  Documents in Knowledge Base               │
├──────────────┬──────┬─────────┬────────────┤
│ File Name    │ Type │ Size    │ Path       │
├──────────────┼──────┼─────────┼────────────┤
│ report.pdf   │ PDF  │ 234 KB  │ report.pdf │
│ notes.md     │ MD   │ 12 KB   │ notes.md   │
└──────────────┴──────┴─────────┴────────────┘
```

### 4. Search Documents

Search for keywords:

```bash
# Search all documents
locallm search "GPT"

# Search specific file
locallm search "machine learning" --file report.pdf
```

### 5. Rebuild Knowledge Map

Regenerate the knowledge map (useful after adding/modifying documents):

```bash
locallm rebuild-map
```

## How It Works

### Knowledge Map

When you first run `locallm ask` in a directory, it:

1. Scans for all supported documents
2. Reads the first 8000 tokens of each document
3. Uses Qwen3 to generate a concise description
4. Extracts key concepts
5. Saves to `knowledge_map.yaml`

Example map entry:
```yaml
documents:
  - id: doc_001
    title: GPT Report
    path: ./gpt_report.pdf
    description: |
      This document discusses the architecture and applications
      of GPT models, covering transformer architecture, training
      methodology, and practical use cases...
    key_concepts:
      - GPT
      - Transformer
      - Neural Networks
```

### AI Agent Workflow

When you ask a question:

1. **Read Map**: Agent reads the knowledge map
2. **Identify Docs**: Determines which 1-3 documents are relevant
3. **Read Files**: Uses `read_file` tool to get complete content
4. **Search**: If needed, uses `grep` tool for specific keywords
5. **Answer**: Provides answer with source citations

## Configuration

Edit `config.yaml` to customize:

```yaml
ollama:
  model: "qwen3:latest"
  temperature: 0.3

agent:
  max_iterations: 10
  verbose: true

documents:
  supported_types:
    - pdf
    - docx
    - txt
    - md
```

## Commands Reference

```bash
locallm                    # Show welcome screen
locallm chat               # Start interactive chat
locallm ask "question"     # Ask one question
locallm list               # List all documents
locallm search "keyword"   # Search documents
locallm rebuild-map        # Rebuild knowledge map
locallm --help             # Show all commands
```

## Tips

1. **Run in document directory**: Always `cd` to your document folder first
2. **Update map**: Run `rebuild-map` after adding new documents
3. **Use specific questions**: Better results with clear, specific questions
4. **Check sources**: AI always cites document sources

## Troubleshooting

### "Error: Connection refused"
- Make sure Ollama is running: `ollama serve`

### "Model not found"
- Download Qwen3: `ollama pull qwen3:latest`

### "No documents found"
- Check you're in the right directory
- Ensure documents are PDF, DOCX, TXT, or MD format

### Knowledge map out of date
- Run: `locallm rebuild-map`

## Architecture

Based on "AI Active Exploration" paradigm - trusting AI to intelligently explore documents rather than pre-chunking everything (like traditional RAG).

```
User Question
    ↓
Knowledge Map (descriptions of all docs)
    ↓
AI Agent reasoning (which docs to read?)
    ↓
Tools: read_file, grep, list_docs
    ↓
AI analyzes content
    ↓
Answer with citations
```

## License

MIT License

## Author

LocalLM v0.8.2

