"""File operation tools for document processing"""

import os
import re
from pathlib import Path
from typing import List, Dict, Optional, Union
import fitz  # PyMuPDF
from docx import Document


class Tool:
    """Simple tool wrapper to replace langchain.tools.tool"""
    def __init__(self, func):
        self.func = func
        self.name = func.__name__
        self.description = func.__doc__ or ""

    def invoke(self, *args, **kwargs):
        """Call the tool function"""
        # Handle both single argument and dict argument
        if len(args) == 1 and isinstance(args[0], dict):
            return self.func(**args[0])
        return self.func(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)


def tool(func):
    """Decorator to create a tool from a function"""
    return Tool(func)


@tool
def read_file(file_path: Union[str, Path]) -> str:
    """Read complete document content from a file.

    Supports: PDF, Markdown (.md), Text (.txt), Word (.docx)

    Args:
        file_path: Path to the document file

    Returns:
        Complete text content of the document with page/section markers
    """
    try:
        file_path = Path(file_path)

        if not file_path.exists():
            return f"Error: File not found: {file_path}"

        # PDF files
        if file_path.suffix.lower() == '.pdf':
            return _read_pdf(file_path)

        # Word documents
        elif file_path.suffix.lower() in ['.docx', '.doc']:
            return _read_docx(file_path)

        # Text/Markdown files
        elif file_path.suffix.lower() in ['.txt', '.md', '.markdown']:
            return _read_text(file_path)

        else:
            return f"Error: Unsupported file type: {file_path.suffix}"

    except Exception as e:
        return f"Error reading file {file_path}: {str(e)}"


def _read_pdf(file_path: Path) -> str:
    """Read PDF file using PyMuPDF"""
    doc = fitz.open(str(file_path))
    content = []

    for page_num, page in enumerate(doc, 1):
        text = page.get_text()
        content.append(f"--- Page {page_num} ---\n{text}")

    doc.close()
    return "\n\n".join(content)


def _read_docx(file_path: Path) -> str:
    """Read Word document"""
    doc = Document(str(file_path))
    content = []

    for para in doc.paragraphs:
        if para.text.strip():
            content.append(para.text)

    return "\n\n".join(content)


def _read_text(file_path: Path) -> str:
    """Read plain text or markdown file"""
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()


@tool
def grep(pattern: str, file_path: Union[str, Path], context_lines: int = 3) -> str:
    """Search for a pattern in a document and return matching lines with context.

    Args:
        pattern: Search pattern (supports regex)
        file_path: Path to the document file
        context_lines: Number of lines to show before and after match (default: 3)

    Returns:
        Matching lines with context, or empty if no matches found
    """
    try:
        # First read the file
        content = read_file(file_path)

        if content.startswith("Error:"):
            return content

        lines = content.split('\n')
        matches = []

        # Compile regex pattern
        regex = re.compile(pattern, re.IGNORECASE)

        for i, line in enumerate(lines):
            if regex.search(line):
                # Get context
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)

                context_block = []
                for j in range(start, end):
                    prefix = ">>> " if j == i else "    "
                    context_block.append(f"{prefix}Line {j+1}: {lines[j]}")

                matches.append("\n".join(context_block))

        if matches:
            return f"Found {len(matches)} match(es) for '{pattern}' in {file_path}:\n\n" + "\n\n---\n\n".join(matches)
        else:
            return f"No matches found for '{pattern}' in {file_path}"

    except Exception as e:
        return f"Error searching file {file_path}: {str(e)}"


@tool
def list_docs(directory: Union[str, Path] = ".") -> str:
    """List all documents in a directory and its subdirectories.

    Args:
        directory: Directory path to scan (default: current directory)

    Returns:
        Formatted list of documents with metadata
    """
    try:
        directory = Path(directory)

        if not directory.exists():
            return f"Error: Directory not found: {directory}"

        # Supported file extensions
        supported_exts = {'.pdf', '.docx', '.doc', '.txt', '.md', '.markdown'}

        documents = []

        # Recursively find documents
        for file_path in directory.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in supported_exts:
                stat = file_path.stat()
                documents.append({
                    'path': str(file_path.relative_to(directory)),
                    'name': file_path.name,
                    'type': file_path.suffix[1:].upper(),
                    'size_kb': round(stat.st_size / 1024, 2),
                    'modified': stat.st_mtime
                })

        if not documents:
            return f"No documents found in {directory}"

        # Sort by modification time (newest first)
        documents.sort(key=lambda x: x['modified'], reverse=True)

        # Format output
        output = [f"Found {len(documents)} document(s) in {directory}:\n"]

        for doc in documents:
            output.append(f"  • {doc['name']} ({doc['type']}, {doc['size_kb']} KB)")
            output.append(f"    Path: {doc['path']}")

        return "\n".join(output)

    except Exception as e:
        return f"Error listing documents in {directory}: {str(e)}"


# Export tools for LangChain
TOOLS = [read_file, grep, list_docs]
