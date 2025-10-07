#!/usr/bin/env python3
"""LocalLM CLI Main Program"""

import os
import sys
from pathlib import Path
import click
from rich.console import Console

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        import locale
        if sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
            # Try to set UTF-8 encoding
            sys.stdout.reconfigure(encoding='utf-8')  # type: ignore
            sys.stderr.reconfigure(encoding='utf-8')  # type: ignore
    except Exception:
        pass  # If reconfigure fails, continue anyway
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.markdown import Markdown
from rich.live import Live
from rich.spinner import Spinner
from rich.syntax import Syntax

from .agents.explorer import DocumentExplorer
from .tools.file_ops import list_docs, grep
from .tools.map_generator import generate_knowledge_map
from .utils.config import get_default_model

console = Console()


def handle_slash_command(command: str, explorer, console):
    """Handle slash commands in chat mode"""
    parts = command[1:].split(maxsplit=1)  # Remove leading '/' and split
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if cmd == 'help':
        # Show available commands
        help_table = Table(title="Available Slash Commands", show_header=True, header_style="bold cyan")
        help_table.add_column("Command", style="green")
        help_table.add_column("Description", style="dim")

        help_table.add_row("/help", "Show this help message")
        help_table.add_row("/list", "List all documents in knowledge base")
        help_table.add_row("/search <keyword>", "Search for keyword in documents")
        help_table.add_row("/models", "List available Ollama models")
        help_table.add_row("/model <name>", "Switch to a different model")
        help_table.add_row("/rebuild", "Rebuild knowledge map")
        help_table.add_row("/rebuild --fast", "Rebuild knowledge map (fast mode)")
        help_table.add_row("/clear", "Clear conversation history")
        help_table.add_row("/exit or /quit", "Exit chat mode")

        console.print()
        console.print(help_table)
        console.print()

    elif cmd == 'list':
        # List documents
        docs = explorer.list_documents()
        console.print()
        console.print(f"[cyan]📚 Found {len(docs)} document(s):[/cyan]")
        console.print()

        for doc in docs:
            console.print(f"  • [bold]{doc['title']}[/bold]")
            console.print(f"    [dim]{doc['path']}[/dim]")
            if doc.get('key_concepts'):
                concepts = ", ".join(doc['key_concepts'][:5])
                console.print(f"    [yellow]Key concepts:[/yellow] {concepts}")
            console.print()

    elif cmd == 'search':
        if not args:
            console.print("[yellow]Usage: /search <keyword>[/yellow]")
            return

        # Perform grep search
        console.print()
        console.print(f"[cyan]🔍 Searching for: {args}[/cyan]")
        console.print()

        results = grep(args, os.getcwd())
        if results:
            console.print(results)
        else:
            console.print("[dim]No results found[/dim]")
        console.print()

    elif cmd == 'model':
        # Switch model
        if not args:
            console.print("[yellow]Usage: /model <model_name>[/yellow]")
            console.print("[dim]Example: /model llama3[/dim]")
            console.print("[dim]Use /models to see available models[/dim]")
            return

        # Switch to new model
        new_model = args.strip()
        old_model = explorer.model
        explorer.model = new_model
        console.print()
        console.print(f"[green]✓ Switched from {old_model} to {new_model}[/green]")
        console.print()

    elif cmd == 'models':
        # List Ollama models
        import ollama
        console.print()
        console.print("[cyan]Available Ollama Models:[/cyan]")
        console.print()

        try:
            models_response = ollama.list()
            model_table = Table(show_header=True, header_style="bold cyan")
            model_table.add_column("Model Name", style="green")
            model_table.add_column("Size", style="dim")
            model_table.add_column("Modified", style="dim")

            current_model = explorer.model

            # Handle both dict and object responses
            if hasattr(models_response, 'models'):
                models_list = models_response.models
            else:
                models_list = models_response.get('models', [])

            for model in models_list:
                # Get model name - could be 'model' or 'name' field
                if hasattr(model, 'model'):
                    name = model.model
                    size = model.size if hasattr(model, 'size') else 0
                    modified = model.modified_at if hasattr(model, 'modified_at') else None
                else:
                    name = model.get('model') or model.get('name', 'Unknown')
                    size = model.get('size', 0)
                    modified = model.get('modified_at')

                # Handle size - could be int or string
                try:
                    size_gb = int(size) / (1024**3) if size else 0
                except (ValueError, TypeError):
                    size_gb = 0

                # Mark current model
                display_name = name
                if name == current_model:
                    display_name = f"→ {name} (current)"

                modified = model.get('modified_at', 'Unknown')
                modified_str = 'Unknown'
                if modified and modified != 'Unknown':
                    try:
                        from datetime import datetime
                        modified_str = datetime.fromisoformat(str(modified).replace('Z', '+00:00')).strftime('%Y-%m-%d')
                    except:
                        modified_str = 'Unknown'

                model_table.add_row(display_name, f"{size_gb:.2f} GB", str(modified_str))

            console.print(model_table)
            console.print()
            console.print("[dim]Use /model <name> to switch model in chat, or use -m flag: locallm chat -m <model_name>[/dim]")
            console.print()
        except Exception as e:
            console.print(f"[red]Error listing models: {str(e)}[/red]")

    elif cmd == 'rebuild':
        # Rebuild knowledge map
        fast_mode = '--fast' in args
        console.print()
        console.print(f"[cyan]🔄 Rebuilding knowledge map{'(fast mode)' if fast_mode else ''}...[/cyan]")
        console.print()

        try:
            generate_knowledge_map(os.getcwd(), use_ai=not fast_mode)
            console.print("[green]✓ Knowledge map rebuilt successfully![/green]")
            console.print()

            # Reload explorer's knowledge map
            explorer.reload_knowledge_map()
            console.print(f"[dim]Loaded {explorer.get_document_count()} documents[/dim]")
            console.print()
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")

    elif cmd == 'clear':
        # Clear conversation history
        explorer.clear_history()
        console.print()
        console.print("[green]✓ Conversation history cleared[/green]")
        console.print()

    elif cmd in ['exit', 'quit']:
        console.print("[yellow]Use 'exit' or 'quit' without slash to exit chat mode[/yellow]")

    else:
        console.print()
        console.print(f"[yellow]Unknown command: /{cmd}[/yellow]")
        console.print("[dim]Type /help to see available commands[/dim]")
        console.print()


def display_welcome():
    """Display welcome screen"""
    # ASCII art for LOCALLM
    welcome_text = Text()
    welcome_text.append("""
██╗      ██████╗  ██████╗ █████╗ ██╗     ██╗     ███╗   ███╗
██║     ██╔═══██╗██╔════╝██╔══██╗██║     ██║     ████╗ ████║
██║     ██║   ██║██║     ███████║██║     ██║     ██╔████╔██║
██║     ██║   ██║██║     ██╔══██║██║     ██║     ██║╚██╔╝██║
███████╗╚██████╔╝╚██████╗██║  ██║███████╗███████╗██║ ╚═╝ ██║
╚══════╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝╚══════╝╚══════╝╚═╝     ╚═╝
""", style="bold cyan")

    # Get current working directory
    current_dir = os.getcwd()

    # Create panel
    panel = Panel(
        welcome_text,
        title="[bold yellow]Local Knowledge Base System[/bold yellow]",
        subtitle=f"[dim]v0.8.0 | Current Location: {current_dir}[/dim]",
        border_style="bright_blue",
        padding=(1, 2)
    )

    console.print(panel)
    console.print()


@click.group(invoke_without_command=True)
@click.option('--model', '-m', default='qwen3:latest', help='Ollama model to use')
@click.pass_context
def main(ctx, model):
    """LocalLM - Local Knowledge Base Terminal System

    Type 'locallm' from anywhere to start chat mode
    """
    if ctx.invoked_subcommand is None:
        # Directly start chat mode
        ctx.invoke(chat, model=model)


@main.command()
@click.option('--model', '-m', default=None, help='Ollama model to use (overrides config)')
def chat(model):
    """Start interactive chat session with the AI"""
    # Use config default if not specified
    if model is None:
        model = get_default_model()

    # Display welcome screen
    display_welcome()

    console.print("[bold cyan]Starting Chat Session[/bold cyan]")
    console.print("[dim]Type 'exit' or 'quit' to end the conversation[/dim]")
    console.print("[dim]Press Ctrl+C once to interrupt, twice to exit[/dim]")
    console.print("[dim]Type '/help' to see available slash commands[/dim]")
    console.print()

    try:
        # Show initialization message
        console.print(f"[cyan]Initializing AI ({model})...[/cyan]")

        # Initialize explorer (knowledge map generation will show its own progress)
        explorer = DocumentExplorer(
            directory=os.getcwd(),
            model=model
        )

        console.print(f"[green]✓[/green] Ready! Chat with {model}")
        console.print()

        # Check for document changes
        update_warning = explorer.check_for_updates()
        if update_warning:
            console.print(f"[yellow]{update_warning}[/yellow]")
            console.print()

        # Track Ctrl+C presses
        interrupt_count = 0

        # Chat loop
        while True:
            try:
                # Get user input
                user_input = console.input("[bold blue]You:[/bold blue] ")

                # Reset interrupt counter on new input
                interrupt_count = 0

                if user_input.strip().lower() in ['exit', 'quit', 'bye']:
                    console.print("[yellow]Goodbye![/yellow]")
                    break

                if not user_input.strip():
                    continue

                # Handle slash commands
                if user_input.strip().startswith('/'):
                    handle_slash_command(user_input.strip(), explorer, console)
                    continue

                # Get AI response
                console.print()

                live_display = None
                try:
                    # Show thinking spinner with Live display
                    from rich.live import Live
                    from rich.spinner import Spinner

                    thinking_spinner = Spinner("dots", text="Thinking...", style="yellow dim")
                    live_display = Live(thinking_spinner, console=console, refresh_per_second=20)
                    live_display.start()

                    # Stream response (explorer will stop the spinner when first chunk arrives)
                    response = explorer.chat(user_input, use_tools=True, stream_output=True, live_display=live_display)

                    # Stop live display if still running
                    if live_display:
                        live_display.stop()

                    console.print()  # Extra newline

                    # Reset interrupt counter after successful response
                    interrupt_count = 0

                except KeyboardInterrupt:
                    # Ensure live display is stopped
                    if live_display:
                        try:
                            live_display.stop()
                        except:
                            pass

                    interrupt_count += 1
                    if interrupt_count == 1:
                        console.print("\n[yellow]⚠ Interrupted! Press Ctrl+C again to exit.[/yellow]")
                        console.print()
                    else:
                        console.print("\n[yellow]Exiting...[/yellow]")
                        break

            except KeyboardInterrupt:
                interrupt_count += 1
                if interrupt_count == 1:
                    console.print("\n[yellow]⚠ Press Ctrl+C again to exit.[/yellow]")
                else:
                    console.print("\n[yellow]Exiting...[/yellow]")
                    break

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


@main.command()
@click.argument('question', nargs=-1, required=True)
@click.option('--model', '-m', default=None, help='Ollama model to use (overrides config)')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed reasoning process')
def ask(question, model, verbose):
    """Ask the knowledge base a question"""
    # Use config default if not specified
    if model is None:
        model = get_default_model()

    question_text = ' '.join(question)

    console.print()
    console.print(f"[bold cyan]Question:[/bold cyan] {question_text}")
    console.print()

    # Track Ctrl+C presses
    interrupt_count = 0

    try:
        # Show initialization message
        console.print(f"[cyan]⚙️  Initializing AI ({model})...[/cyan]")

        # Initialize document explorer (knowledge map generation will show its own progress)
        try:
            explorer = DocumentExplorer(
                directory=os.getcwd(),
                model=model
            )
        except KeyboardInterrupt:
            console.print("\n[yellow]Initialization cancelled[/yellow]")
            sys.exit(0)

        console.print(f"[dim]✓ Loaded {explorer.get_document_count()} documents[/dim]")
        console.print()

        # Ask question with live status updates
        current_status = {"text": "Analyzing..."}

        def update_status(message: str):
            """Update status message"""
            current_status["text"] = message

        try:
            # Use Live display for status updates
            with Live(console=console, refresh_per_second=4) as live:
                def status_update(msg):
                    update_status(msg)
                    live.update(f"[bold yellow]{current_status['text']}[/bold yellow]")

                result = explorer.ask(question_text, status_callback=status_update, verbose=verbose)

            # Display answer
            console.print()
            console.print("[bold green]Answer:[/bold green]")
            console.print()

            # Render answer as markdown
            answer_md = Markdown(result['answer'])
            console.print(answer_md)
            console.print()

            # Show reasoning steps if verbose
            if verbose and result.get('steps'):
                console.print()
                steps_table = Table(title="🔍 Reasoning Steps", show_header=True, header_style="bold magenta")
                steps_table.add_column("Step", style="cyan", width=6)
                steps_table.add_column("Action", style="yellow")
                steps_table.add_column("Input", style="green")

                for i, step in enumerate(result['steps'], 1):
                    steps_table.add_row(
                        str(i),
                        step['action'],
                        step['input'][:60] + "..." if len(step['input']) > 60 else step['input']
                    )

                console.print(steps_table)
                console.print()

        except KeyboardInterrupt:
            interrupt_count += 1
            if interrupt_count == 1:
                console.print("\n[yellow]⚠ Interrupted! Press Ctrl+C again to exit.[/yellow]")
                # Wait for second Ctrl+C
                try:
                    import time
                    time.sleep(2)  # Give user 2 seconds to press again
                    console.print("[yellow]Resuming...[/yellow]")
                except KeyboardInterrupt:
                    console.print("\n[yellow]Exiting...[/yellow]")
                    sys.exit(0)
            else:
                console.print("\n[yellow]Exiting...[/yellow]")
                sys.exit(0)

    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if verbose:
            import traceback
            console.print("[dim]" + traceback.format_exc() + "[/dim]")
        sys.exit(1)


@main.command()
def list():
    """List all documents in the knowledge base"""
    current_dir = os.getcwd()

    console.print()
    console.print(f"[bold cyan]Scanning:[/bold cyan] {current_dir}")
    console.print()

    try:
        # Get document list
        docs_output = list_docs.invoke(current_dir)

        if "No documents found" in docs_output:
            console.print("[yellow]No documents found in this directory[/yellow]")
            console.print("[dim]Supported formats: PDF, DOCX, TXT, MD[/dim]")
            return

        # Parse and display as table
        lines = docs_output.split('\n')

        # Create table
        table = Table(title="Documents in Knowledge Base", show_header=True, header_style="bold cyan")
        table.add_column("File Name", style="green")
        table.add_column("Type", style="yellow")
        table.add_column("Size", style="blue")
        table.add_column("Path", style="dim")

        # Parse document entries (simple parsing)
        current_doc = {}
        for line in lines[1:]:  # Skip first line (header)
            if line.strip().startswith('•'):
                # Document name line
                if current_doc:
                    table.add_row(
                        current_doc.get('name', ''),
                        current_doc.get('type', ''),
                        current_doc.get('size', ''),
                        current_doc.get('path', '')
                    )
                    current_doc = {}

                # Parse: • filename.pdf (PDF, 123.45 KB)
                parts = line.strip().split('(')
                if len(parts) >= 2:
                    name = parts[0].replace('•', '').strip()
                    info = parts[1].rstrip(')')
                    type_size = info.split(',')
                    current_doc['name'] = name
                    if len(type_size) >= 2:
                        current_doc['type'] = type_size[0].strip()
                        current_doc['size'] = type_size[1].strip()

            elif line.strip().startswith('Path:'):
                current_doc['path'] = line.split('Path:')[1].strip()

        # Add last document
        if current_doc:
            table.add_row(
                current_doc.get('name', ''),
                current_doc.get('type', ''),
                current_doc.get('size', ''),
                current_doc.get('path', '')
            )

        console.print(table)
        console.print()

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


@main.command()
@click.argument('keyword')
@click.option('--file', '-f', help='Search in specific file only')
def search(keyword, file):
    """Search for keywords in documents"""
    current_dir = os.getcwd()

    console.print()
    console.print(f"[bold cyan]Searching for:[/bold cyan] '{keyword}'")
    console.print()

    try:
        if file:
            # Search in specific file
            result = grep.invoke({"pattern": keyword, "file_path": file, "context_lines": 3})

            # Display in a panel
            panel = Panel(
                result,
                title=f"[bold cyan]Results in {Path(file).name}[/bold cyan]",
                border_style="cyan",
                padding=(1, 2)
            )
            console.print(panel)
        else:
            # Search in all documents
            supported_exts = {'.pdf', '.docx', '.doc', '.txt', '.md', '.markdown'}
            found_any = False

            for file_path in Path(current_dir).rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in supported_exts:
                    result = grep.invoke({"pattern": keyword, "file_path": str(file_path), "context_lines": 2})

                    if not result.startswith("No matches"):
                        # Display in a panel for each file
                        panel = Panel(
                            result,
                            title=f"[bold green]📄 {file_path.name}[/bold green]",
                            subtitle=f"[dim]{file_path.relative_to(current_dir)}[/dim]",
                            border_style="green",
                            padding=(1, 2)
                        )
                        console.print(panel)
                        console.print()
                        found_any = True

            if not found_any:
                console.print(f"[yellow]❌ No matches found for '{keyword}'[/yellow]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


@main.command()
def models():
    """List available Ollama models"""
    console.print()
    console.print("[bold cyan]Available Ollama Models[/bold cyan]")
    console.print()

    try:
        import ollama

        # Get list of models from Ollama
        model_list = ollama.list()

        if not model_list or 'models' not in model_list or len(model_list['models']) == 0:
            console.print("[yellow]No models found. Please pull a model first:[/yellow]")
            console.print("[dim]  ollama pull qwen3:latest[/dim]")
            return

        # Get default model from config
        default_model = get_default_model()

        # Create table
        table = Table(title="Ollama Models", show_header=True, header_style="bold cyan")
        table.add_column("Model Name", style="green")
        table.add_column("Size", style="yellow")
        table.add_column("Modified", style="blue")
        table.add_column("Default", style="magenta")

        for model in model_list['models']:
            model_name = model.get('name', 'Unknown')
            size = model.get('size', 0)
            # Convert size to human readable
            if size > 1024**3:
                size_str = f"{size / (1024**3):.1f} GB"
            elif size > 1024**2:
                size_str = f"{size / (1024**2):.1f} MB"
            else:
                size_str = f"{size / 1024:.1f} KB"

            # Get modified time
            import datetime
            modified = model.get('modified_at', '')
            if modified:
                try:
                    dt = datetime.datetime.fromisoformat(modified.replace('Z', '+00:00'))
                    modified_str = dt.strftime('%Y-%m-%d %H:%M')
                except:
                    modified_str = modified[:16]
            else:
                modified_str = 'Unknown'

            # Check if default
            is_default = "✓" if model_name == default_model else ""

            table.add_row(model_name, size_str, modified_str, is_default)

        console.print(table)
        console.print()
        console.print(f"[dim]Default model: {default_model}[/dim]")
        console.print(f"[dim]Change default in config.yaml or use --model flag[/dim]")
        console.print()

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        console.print("[yellow]Make sure Ollama is running:[/yellow]")
        console.print("[dim]  ollama serve[/dim]")
        sys.exit(1)


@main.command()
@click.option('--fast', is_flag=True, help='Fast mode: AI reads TOC/abstract only (faster)')
def rebuild_map(fast):
    """Rebuild the knowledge map for current directory"""
    current_dir = os.getcwd()

    console.print()
    console.print(f"[bold cyan]Rebuilding knowledge map in:[/bold cyan] {current_dir}")
    if fast:
        console.print("[yellow]Fast mode: AI reads TOC/abstract only[/yellow]")
    else:
        console.print("[yellow]Full mode: AI reads full content (slower but higher quality)[/yellow]")
    console.print("[dim]Press Ctrl+C to cancel[/dim]")
    console.print()

    interrupt_count = 0

    try:
        try:
            result = generate_knowledge_map(current_dir, fast_mode=fast)

            console.print("[bold green]Success![/bold green]")
            console.print(result)
            console.print()

        except KeyboardInterrupt:
            interrupt_count += 1
            if interrupt_count == 1:
                console.print("\n[yellow]⚠ Interrupted! Press Ctrl+C again to exit.[/yellow]")
                # Wait for second Ctrl+C
                try:
                    import time
                    time.sleep(2)
                    console.print("[yellow]Cancelled. Partial map may have been saved.[/yellow]")
                except KeyboardInterrupt:
                    console.print("\n[yellow]Exiting...[/yellow]")
                    sys.exit(0)
            else:
                console.print("\n[yellow]Exiting...[/yellow]")
                sys.exit(0)

    except KeyboardInterrupt:
        console.print("\n[yellow]Map generation cancelled[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
