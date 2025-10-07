"""Knowledge map generator for document discovery"""

import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Union
import ollama


def generate_knowledge_map(directory: Union[str, Path] = ".", output_file: str = "knowledge_map.yaml", use_ai: bool = True, fast_mode: bool = False) -> str:
    """Generate a knowledge map for all documents in directory.

    Args:
        directory: Directory to scan for documents
        output_file: Output YAML file path
        use_ai: DEPRECATED - kept for backwards compatibility, use fast_mode instead
        fast_mode: If True, AI reads TOC/abstract only (fast); if False, AI reads full content (slower)

    Returns:
        Status message
    """
    from .file_ops import list_docs, read_file
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn

    console = Console()
    directory = Path(directory)
    output_path = directory / output_file

    # Get list of documents
    docs_list = list_docs.invoke(str(directory))

    if docs_list.startswith("Error:") or "No documents found" in docs_list:
        return docs_list

    # Parse document paths from list_docs output
    document_entries = []

    # Find all supported documents
    supported_exts = {'.pdf', '.docx', '.doc', '.txt', '.md', '.markdown'}

    # First, collect all files to process
    files_to_process = []
    for file_path in directory.rglob('*'):
        if file_path.is_file() and file_path.suffix.lower() in supported_exts:
            if file_path.name != output_file:
                files_to_process.append(file_path)

    total_files = len(files_to_process)
    if total_files == 0:
        return "No documents found to process."

    # Show initial info
    console.print(f"[cyan]📚 Found {total_files} document(s)[/cyan]")
    if fast_mode:
        estimated_time = total_files * 2  # Roughly 2 seconds per file with TOC/abstract
        console.print(f"[dim]Estimated time: ~{estimated_time} seconds (AI reads TOC/abstract)[/dim]")
    else:
        estimated_time = total_files * 5  # Roughly 5 seconds per file with full content
        console.print(f"[dim]Estimated time: ~{estimated_time} seconds (AI reads full content)[/dim]")
    console.print()

    # Process files with progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
        refresh_per_second=10  # Higher refresh rate for smooth spinner animation
    ) as progress:
        task = progress.add_task(f"[cyan]Building knowledge map", total=total_files)

        for idx, file_path in enumerate(files_to_process, 1):
            # Only update description every file or every 2 seconds to reduce flicker
            progress.update(task, description=f"[cyan]{idx}/{total_files}: {file_path.name[:30]}")

            # Read file content - only first 3000 chars for speed
            content = read_file.invoke(str(file_path))

            # Skip files with errors or empty content
            if content.startswith("Error:"):
                console.print(f"  [yellow]⚠ Skipped (read error): {file_path.name}[/yellow]")
                progress.advance(task)
                continue

            if not content or len(content.strip()) == 0:
                console.print(f"  [yellow]⚠ Skipped (empty file): {file_path.name}[/yellow]")
                progress.advance(task)
                continue

            # Smart sampling: take first 60% and last 40% (up to 8000 chars total)
            # This captures intro/TOC and conclusions/summary sections
            max_chars = 8000
            if len(content) <= max_chars:
                content_sample = content
            else:
                head_size = int(max_chars * 0.6)
                tail_size = max_chars - head_size
                content_sample = content[:head_size] + "\n\n...\n\n" + content[-tail_size:]

            # Generate description and key concepts using AI
            if fast_mode:
                # Fast mode: Extract TOC/abstract, then let AI quickly summarize
                progress.update(task, description=f"[cyan]{idx}/{total_files}: AI + TOC {file_path.name[:20]}...")

                toc_or_abstract = _extract_toc_or_abstract(content_sample)

                # If TOC/abstract not found, use first 2000 chars as summary
                if not toc_or_abstract or len(toc_or_abstract) < 100:
                    toc_or_abstract = content_sample[:2000]

                # AI quickly generates map from extracted summary
                description, key_concepts = _ai_analyze_toc(
                    title=file_path.stem,
                    toc_or_abstract=toc_or_abstract,
                    file_type=file_path.suffix[1:].upper()
                )
            else:
                # Full mode: Let AI read entire document and decide everything
                progress.update(task, description=f"[yellow]{idx}/{total_files}: AI full read {file_path.name[:20]}...")

                # AI-driven: trust the model to analyze the document completely
                description, key_concepts = _ai_analyze_document(
                    title=file_path.name,
                    content=content,  # Full content (all formats: PDF/DOCX/TXT/MD)
                    file_type=file_path.suffix[1:].upper()
                )

            # Ensure key_concepts is never empty
            if not key_concepts or len(key_concepts) == 0:
                # Fallback: use filename
                is_chinese = re.search(r'[\u4e00-\u9fff]', file_path.stem)
                if is_chinese:
                    filename_words = re.findall(r'[\u4e00-\u9fff]+', file_path.stem)
                    key_concepts = filename_words[:3] if filename_words else [f"{file_path.suffix[1:].upper()} document"]
                else:
                    key_concepts = [file_path.stem]
                console.print(f"  [yellow]⚠ Using filename as keywords: {file_path.name}[/yellow]")

            # Get file metadata
            stat = file_path.stat()

            document_entries.append({
                'id': f"doc_{len(document_entries):03d}",
                'title': file_path.stem,
                'path': str(file_path.relative_to(directory)),
                'file_type': file_path.suffix[1:],
                'size_kb': round(stat.st_size / 1024, 2),
                'description': description,
                'key_concepts': key_concepts,
                'last_updated': stat.st_mtime
            })

            progress.advance(task)

    # Create knowledge map structure
    knowledge_map = {
        'version': '1.0',
        'directory': str(directory.absolute()),
        'total_documents': len(document_entries),
        'documents': document_entries
    }

    # Save to YAML
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(knowledge_map, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    # Show completion summary
    console.print()
    console.print(f"[bold green]✓ Knowledge map completed![/bold green]")
    console.print(f"[dim]Location: {output_path}[/dim]")
    console.print(f"[dim]Processed {len(document_entries)} document(s)[/dim]")

    return f"✓ Knowledge map created ({len(document_entries)} documents)"


def _ai_analyze_document(title: str, content: str, file_type: str) -> tuple:
    """Let AI freely analyze entire document without rigid rules.

    Philosophy: Trust the AI to read the complete document and decide
    what's important. No predefined sampling, no fixed templates.

    Args:
        title: Document filename
        content: Full document content (any format: PDF, DOCX, TXT, MD)
        file_type: File extension (PDF, DOCX, etc.)

    Returns:
        (description, key_concepts) tuple
    """
    import json
    import re

    # Let AI read as much as possible without artificial limits
    # Only truncate if exceeding model context window (most models: 8k-32k tokens)
    max_chars = 32000  # ~8000 tokens, enough for most documents

    if len(content) > max_chars:
        # Smart sampling: prioritize beginning (intro/TOC) and end (conclusion)
        # but let AI see more context
        head = int(max_chars * 0.6)
        tail = max_chars - head
        content_for_ai = content[:head] + "\n\n[... middle content truncated ...]\n\n" + content[-tail:]
    else:
        content_for_ai = content

    # Minimal prompt: let AI decide everything
    prompt = f"""Read this document and create a knowledge map entry.

**Document**: {title}
**Format**: {file_type}

**Full Content**:
{content_for_ai}

**Instructions**:
You are free to analyze this document in any way you see fit. No strict rules.

1. Write a 200-300 word description that captures what this document is about
   - Focus on what would help someone decide if this document is relevant to their question
   - Include specific details, technical terms, key findings, or main themes
   - Write naturally - no need to follow a template

2. Extract 5-10 keywords/concepts that represent this document
   - Choose terms that someone might search for
   - Can be technical terms, topics, methods, tools, domain names, etc.
   - Avoid author names, institutions, generic words

**Output** (JSON only):
{{"description": "...", "key_concepts": ["...", "..."]}}

JSON:"""

    try:
        response = ollama.generate(
            model='qwen3:latest',
            prompt=prompt,
            options={
                'temperature': 0.3,
                'num_predict': 2000,  # Allow longer responses
                'num_ctx': 16384     # Large context window for full documents
            },
            stream=False
        )

        result = response['response'].strip()

        # Clean think tags
        result = re.sub(r'<think>[\s\S]*?</think>', '', result, flags=re.IGNORECASE)
        result = re.sub(r'<thinking>[\s\S]*?</thinking>', '', result, flags=re.IGNORECASE)
        result = re.sub(r'<think>\s*', '', result, flags=re.IGNORECASE)
        result = result.strip()

        # Try to extract JSON
        json_match = re.search(r'\{[\s\S]*?\}', result)
        if json_match:
            try:
                data = json.loads(json_match.group())
                description = data.get('description', '').strip()
                key_concepts = data.get('key_concepts', [])

                # Filter key concepts (only remove obvious noise)
                if key_concepts:
                    key_concepts = _filter_invalid_concepts(key_concepts)

                # Validate description quality
                if description and len(description) >= 100:
                    return description, key_concepts if key_concepts else []
                else:
                    # Description too short or empty, try fallback extraction
                    from rich.console import Console
                    console = Console()
                    console.print(f"  [yellow]⚠ AI description too short for {title[:30]}, using fallback[/yellow]")
                    return _fallback_analysis(title, content_for_ai, file_type)

            except json.JSONDecodeError:
                # JSON parsing failed, use fallback
                from rich.console import Console
                console = Console()
                console.print(f"  [yellow]⚠ JSON parse error for {title[:30]}, using fallback[/yellow]")
                return _fallback_analysis(title, content_for_ai, file_type)
        else:
            # AI didn't return JSON, use fallback
            from rich.console import Console
            console = Console()
            console.print(f"  [yellow]⚠ AI failed to return JSON for {title[:30]}, using fallback[/yellow]")
            return _fallback_analysis(title, content_for_ai, file_type)

    except Exception as e:
        from rich.console import Console
        console = Console()
        console.print(f"  [red]✗ AI analysis error for {title[:30]}: {str(e)[:50]}, using fallback[/red]")
        return _fallback_analysis(title, content_for_ai, file_type)


def _fallback_analysis(title: str, content: str, file_type: str) -> tuple:
    """Fallback: generate description and keywords using simple extraction.

    Args:
        title: Document title
        content: Document content
        file_type: File type

    Returns:
        (description, key_concepts) tuple
    """
    # Extract introduction as description
    description = _extract_introduction(content, max_chars=300)
    if not description or len(description) < 50:
        description = f"{file_type} document: {title}"

    # Extract keywords
    key_concepts = _extract_key_concepts(content, max_concepts=10)

    return description, key_concepts


def _extract_key_concepts(content: str, max_concepts: int = 10) -> List[str]:
    """Simple fallback: extract key concepts from document content using regex.

    This is only used when AI fails. Extracts capitalized words and technical terms.
    """
    import re
    from collections import Counter

    # Basic stopwords (minimal list)
    stopwords = {
        'The', 'This', 'That', 'These', 'Those', 'And', 'Or', 'But',
        'Page', 'Figure', 'Table', 'Section', 'Chapter'
    }

    # Find capitalized words and technical terms
    capitalized = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', content[:5000])
    technical = re.findall(r'\b[A-Za-z]+[-_][A-Za-z0-9]+\b', content[:5000])

    # For Chinese: extract 4-char phrases that appear frequently
    chinese_phrases = []
    if re.search(r'[\u4e00-\u9fff]', content):
        four_char = re.findall(r'[\u4e00-\u9fff]{4}', content[:5000])
        phrase_counts = Counter(four_char)
        chinese_phrases = [p for p, c in phrase_counts.most_common(10) if c >= 3]

    # Combine and filter
    all_candidates = capitalized + technical + chinese_phrases
    filtered = [c for c in set(all_candidates) if c not in stopwords and len(c) > 2]

    # Sort by frequency
    filtered.sort(key=lambda x: content.count(x), reverse=True)

    return filtered[:max_concepts]


def _extract_toc_or_abstract(content: str, max_chars: int = 2000) -> str:
    """Extract table of contents OR abstract from document (fast mode).

    Tries to find the most informative summary section: TOC, abstract, or executive summary.

    Args:
        content: Document content
        max_chars: Maximum characters to extract

    Returns:
        Extracted TOC/abstract text, or empty string if not found
    """
    import re

    # Try abstract first (usually more informative than TOC)
    abstract = _extract_abstract(content, max_chars)
    if abstract:
        return abstract

    # Then try TOC
    toc = _extract_toc(content, max_chars)
    if toc:
        return toc

    return ""


def _extract_abstract(content: str, max_chars: int = 2000) -> str:
    """Extract abstract or executive summary from document.

    Args:
        content: Document content
        max_chars: Maximum characters to extract

    Returns:
        Abstract text, or empty string if not found
    """
    import re

    abstract_patterns = [
        r'(?:^|\n)\s*(?:摘要|ABSTRACT|Abstract|執行摘要|Executive Summary)\s*[:：\n]',
    ]

    for pattern in abstract_patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
        if match:
            abstract_start = match.end()
            # Extract until next section
            section_end_markers = [
                r'(?:^|\n)\s*(?:關鍵詞|Keywords?|Introduction|1\.|I\.)\s*[:：\n]',
                r'(?:^|\n)\s*(?:一、|第一章)',
            ]
            abstract_end = abstract_start + max_chars
            for end_pattern in section_end_markers:
                end_match = re.search(end_pattern, content[abstract_start:], re.IGNORECASE | re.MULTILINE)
                if end_match and end_match.start() < max_chars:
                    abstract_end = abstract_start + end_match.start()
                    break

            abstract_text = content[abstract_start:abstract_end].strip()
            if len(abstract_text) > 50:  # Valid abstract
                return abstract_text

    return ""


def _ai_analyze_toc(title: str, toc_or_abstract: str, file_type: str) -> tuple:
    """Let AI quickly analyze TOC/abstract and generate knowledge map (fast mode).

    Args:
        title: Document title
        toc_or_abstract: Extracted table of contents or abstract
        file_type: File extension

    Returns:
        (description, key_concepts) tuple
    """
    import json
    import re

    prompt = f"""Based on this document's table of contents or abstract, create a brief knowledge map entry.

**Document**: {title}
**Format**: {file_type}

**TOC/Abstract**:
{toc_or_abstract}

**Instructions**:
Write a concise 150-200 word description and extract 5-10 keywords.

**Output** (JSON only):
{{"description": "...", "key_concepts": ["...", "..."]}}

JSON:"""

    try:
        response = ollama.generate(
            model='qwen3:latest',
            prompt=prompt,
            options={
                'temperature': 0.3,
                'num_predict': 800,
                'num_ctx': 4096
            },
            stream=False
        )

        result = response['response'].strip()
        result = re.sub(r'<think>[\s\S]*?</think>', '', result, flags=re.IGNORECASE)
        result = re.sub(r'<thinking>[\s\S]*?</thinking>', '', result, flags=re.IGNORECASE)
        result = result.strip()

        json_match = re.search(r'\{[\s\S]*?\}', result)
        if json_match:
            data = json.loads(json_match.group())
            description = data.get('description', '').strip()
            key_concepts = data.get('key_concepts', [])

            if key_concepts:
                key_concepts = _filter_invalid_concepts(key_concepts)

            if not description:
                description = f"Document: {title}"
            if not key_concepts:
                key_concepts = []

            return description, key_concepts
        else:
            return f"Document: {title}", []

    except Exception as e:
        return f"Document: {title}", []


def _extract_toc(content: str, max_chars: int = 2000) -> str:
    """Simple TOC extraction: look for common markers.

    Returns TOC text if found, empty string otherwise.
    """
    import re

    # Look for TOC markers
    toc_markers = [
        r'(?:目錄|Table of Contents|Contents)\s*[:：\n]',
        r'(?:大綱|Outline)\s*[:：\n]',
    ]

    for pattern in toc_markers:
        match = re.search(pattern, content[:3000], re.IGNORECASE)
        if match:
            # Extract next max_chars after marker
            start = match.end()
            toc = content[start:start + max_chars]
            # Clean up
            toc = re.sub(r'\s+', ' ', toc)
            return toc.strip() if len(toc.strip()) > 50 else ""

    return ""


def _extract_introduction(content: str, max_chars: int = 300) -> str:
    """Simple fallback: extract first meaningful content from document.

    Returns first N characters, skipping title page if detected.
    """
    import re

    # Skip first 200 chars if looks like title page
    start = 200 if len(content) > 500 else 0

    # Clean and extract
    text = content[start:start + max_chars * 2]
    text = re.sub(r'\n+', ' ', text)  # Remove newlines
    text = re.sub(r'\s+', ' ', text)  # Remove extra spaces

    return text[:max_chars].strip() + '...' if len(text) > max_chars else text.strip()


def _filter_invalid_concepts(concepts: List[str]) -> List[str]:
    """Minimal filter: remove obvious noise from AI-generated concepts.

    Trust AI to extract good keywords, only filter obvious issues.
    """
    # Minimal blacklist - trust the AI for most filtering
    blacklist = {
        'page', 'figure', 'table', 'section', 'chapter', 'appendix',
        'reference', 'abstract', 'introduction', 'conclusion',
        'university', 'department', 'institute'
    }

    filtered = []
    for concept in concepts:
        concept_lower = concept.lower().strip()

        # Basic checks
        if len(concept_lower) < 2:
            continue
        if concept_lower in blacklist:
            continue
        if '@' in concept_lower:  # Email addresses
            continue

        filtered.append(concept)

    return filtered


def load_knowledge_map(directory: Union[str, Path] = ".", map_file: str = "knowledge_map.yaml") -> Optional[Dict]:
    """Load existing knowledge map from YAML file.

    Args:
        directory: Directory containing the map
        map_file: Map file name

    Returns:
        Knowledge map dictionary, or None if not found
    """
    map_path = Path(directory) / map_file

    if not map_path.exists():
        return None

    with open(map_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)
