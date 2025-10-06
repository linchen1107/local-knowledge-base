"""AI Agent for document exploration and question answering"""

import json
import yaml
from pathlib import Path
from typing import Optional, Dict, List
import ollama

from ..tools.file_ops import read_file, grep, list_docs
from ..tools.map_generator import load_knowledge_map, generate_knowledge_map
from .prompts import get_agent_system_prompt, get_simple_prompt
from ..utils.file_watcher import DocumentWatcher


class DocumentExplorer:
    """AI agent that explores documents and answers questions"""

    def __init__(
        self,
        directory: str = ".",
        model: str = "qwen3:latest",
        temperature: float = 0.3,
        max_iterations: int = 10
    ):
        """Initialize the document explorer.

        Args:
            directory: Working directory containing documents
            model: Ollama model name
            temperature: LLM temperature (0.0-1.0)
            max_iterations: Maximum reasoning iterations
        """
        self.directory = Path(directory)
        self.model = model
        self.temperature = temperature
        self.max_iterations = max_iterations
        self.conversation_history = []

        # Initialize components
        self.knowledge_map = None
        self.watcher = DocumentWatcher(directory)

        # Setup
        self._load_or_create_knowledge_map()

    def _load_or_create_knowledge_map(self):
        """Load existing knowledge map or create new one"""
        # Try to load existing map
        self.knowledge_map = load_knowledge_map(str(self.directory))

        if self.knowledge_map is None:
            # generate_knowledge_map will handle all printing
            result = generate_knowledge_map(str(self.directory))

            # Load the newly created map
            self.knowledge_map = load_knowledge_map(str(self.directory))

            if self.knowledge_map is None:
                print("⚠️  Warning: Could not load knowledge map. Operating without map context.")

    def _get_system_prompt(self, user_question: str = "") -> str:
        """Get system prompt with knowledge map

        Args:
            user_question: User's question for language detection
        """
        if self.knowledge_map:
            map_yaml = yaml.dump(self.knowledge_map, allow_unicode=True, sort_keys=False)
            return get_agent_system_prompt(map_yaml, user_question)
        else:
            return get_simple_prompt()

    def _call_tool(self, tool_name: str, tool_input: str, status_callback=None) -> str:
        """Call a tool and return result

        Args:
            tool_name: Name of the tool to call
            tool_input: Input for the tool
            status_callback: Optional callback function for status updates
        """
        try:
            # Show tool-specific progress message
            if status_callback:
                if tool_name == "read_file":
                    status_callback(f"Reading {tool_input}...")
                elif tool_name == "grep":
                    status_callback(f"Searching...")
                elif tool_name == "list_docs":
                    status_callback(f"Listing documents...")

            if tool_name == "read_file":
                return read_file.invoke(tool_input)
            elif tool_name == "grep":
                # Parse grep arguments: pattern, file_path
                parts = tool_input.split(',', 1)
                if len(parts) == 2:
                    pattern = parts[0].strip().strip('"').strip("'")
                    file_path = parts[1].strip().strip('"').strip("'")
                    return grep.invoke({"pattern": pattern, "file_path": file_path})
                else:
                    return "Error: grep requires pattern and file_path"
            elif tool_name == "list_docs":
                return list_docs.invoke(tool_input if tool_input else ".")
            else:
                return f"Error: Unknown tool {tool_name}"
        except Exception as e:
            return f"Error calling tool {tool_name}: {str(e)}"

    def ask(self, question: str, status_callback=None, verbose=False, stream_callback=None) -> Dict:
        """Ask a question using simple tool-calling loop.

        Args:
            question: User's question
            status_callback: Optional callback for status updates
            verbose: Show detailed reasoning process
            stream_callback: Optional callback for streaming output (char by char)

        Returns:
            Dictionary with 'answer' and 'steps'
        """
        system_prompt = self._get_system_prompt(question)
        steps = []

        # Build conversation with system prompt
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]

        # Add conversation history
        messages = messages[:1] + self.conversation_history + messages[1:]

        try:
            # Simple iterative approach
            for iteration in range(self.max_iterations):
                if verbose:
                    print(f"\n[Iteration {iteration + 1}]")

                if status_callback:
                    status_callback(f"Analyzing... (step {iteration + 1})")

                # Call Ollama with streaming for interruptibility
                try:
                    stream = ollama.chat(
                        model=self.model,
                        messages=messages,
                        options={
                            "temperature": self.temperature,
                            "num_ctx": 8192,  # Limit context to 8K for better performance
                        },
                        stream=True
                    )

                    assistant_message = ""
                    chunk_count = 0
                    max_chunks = 2000  # Safety limit to prevent infinite streaming
                    max_length = 16000  # Max response length in chars

                    first_chunk_received = False

                    for chunk in stream:
                        chunk_count += 1

                        # Safety checks to prevent infinite loops
                        if chunk_count > max_chunks:
                            assistant_message += "\n\n[Response truncated: exceeded maximum chunks]"
                            break

                        if len(assistant_message) > max_length:
                            assistant_message += "\n\n[Response truncated: exceeded maximum length]"
                            break

                        if 'message' in chunk and 'content' in chunk['message']:
                            content = chunk['message']['content']
                            # Handle potential encoding issues (surrogate characters)
                            try:
                                content = content.encode('utf-8', errors='ignore').decode('utf-8')
                            except:
                                pass
                            assistant_message += content

                            # Stream output in real-time if callback provided
                            if stream_callback and content:
                                # On first chunk, signal to stop spinner
                                if not first_chunk_received:
                                    first_chunk_received = True
                                    # Call with empty string to trigger spinner stop
                                    stream_callback("")
                                # Stream each character
                                for char in content:
                                    stream_callback(char, char_mode=True)

                except Exception as e:
                    if verbose:
                        print(f"⚠ Streaming error: {str(e)}")
                    # Return what we have so far or error message
                    if not assistant_message:
                        assistant_message = f"Error during response generation: {str(e)}"

                messages.append({"role": "assistant", "content": assistant_message})

                if verbose:
                    print(f"AI: {assistant_message[:200]}...")

                # Check if AI wants to use a tool
                # Simple parsing: look for "Action: tool_name" and "Action Input: input"
                if "Action:" in assistant_message and "Action Input:" in assistant_message:
                    lines = assistant_message.split('\n')
                    action_line = None
                    input_line = None

                    for line in lines:
                        if line.strip().startswith("Action:"):
                            action_line = line.split("Action:")[1].strip()
                        elif line.strip().startswith("Action Input:"):
                            input_line = line.split("Action Input:")[1].strip()

                    if action_line and input_line:
                        if verbose:
                            print(f"Tool Call: {action_line}({input_line})")

                        # Call the tool with progress callback
                        observation = self._call_tool(action_line, input_line, status_callback)

                        if verbose:
                            print(f"Observation: {observation[:200]}...")

                        steps.append({
                            'action': action_line,
                            'input': input_line,
                            'observation': observation
                        })

                        # Add observation to conversation
                        messages.append({
                            "role": "user",
                            "content": f"Observation: {observation}"
                        })

                        continue

                # Check if AI has final answer
                if "Final Answer:" in assistant_message:
                    final_answer = assistant_message.split("Final Answer:")[1].strip()

                    # Note: Output already streamed char-by-char in lines 190-191
                    # No need to stream again here

                    # Save to conversation history
                    self.conversation_history.append({"role": "user", "content": question})
                    self.conversation_history.append({"role": "assistant", "content": final_answer})

                    return {
                        'answer': final_answer,
                        'steps': steps
                    }

                # If no action and no final answer, treat response as final answer
                # This handles cases where AI directly answers without using "Final Answer:" format
                if "Action:" not in assistant_message:
                    # Note: Output already streamed char-by-char in lines 190-191
                    # No need to stream again here

                    # Save to conversation history
                    self.conversation_history.append({"role": "user", "content": question})
                    self.conversation_history.append({"role": "assistant", "content": assistant_message})

                    return {
                        'answer': assistant_message,
                        'steps': steps
                    }

                # If we're on last iteration and still here, return what we have
                if iteration == self.max_iterations - 1:
                    # Check if answer seems incomplete or error
                    if self._is_incomplete_answer(assistant_message):
                        fallback = self._fallback_keyword_search(question)
                        return {
                            'answer': assistant_message + "\n\n" + fallback,
                            'steps': steps
                        }
                    return {
                        'answer': assistant_message,
                        'steps': steps
                    }

            return {
                'answer': "Maximum iterations reached without final answer.",
                'steps': steps
            }

        except Exception as e:
            # Provide fallback on error
            fallback = self._fallback_keyword_search(question)
            return {
                'answer': f"Error: {str(e)}\n\n{fallback}",
                'steps': steps
            }

    def chat(self, message: str, use_tools: bool = True, stream_output: bool = True, live_display=None) -> str:
        """Chat with tool calling support for conversation mode

        Args:
            message: User's message
            use_tools: Whether to enable tool calling (default: True)
            stream_output: Whether to stream output character by character (default: True)
            live_display: Rich Live display object for spinner control (optional)

        Returns:
            AI's response
        """
        if not use_tools:
            # Simple chat without tools
            self.conversation_history.append({"role": "user", "content": message})

            try:
                # System prompt that encourages thinking
                system_prompt = """You are a helpful AI assistant.

When answering questions, you may use <think> tags to show your reasoning process before providing the final answer. This helps users understand your thought process.

Format:
<think>
Your internal reasoning here...
</think>

Final answer here."""

                # Use streaming for interruptible generation
                stream = ollama.chat(
                    model=self.model,
                    messages=[{"role": "system", "content": system_prompt}] +
                             self.conversation_history,
                    options={
                        "temperature": self.temperature,
                        "num_ctx": 8192,  # Limit context to 8K for better performance
                    },
                    stream=True
                )

                answer = ""
                first_chunk = True
                in_think_block = False

                for chunk in stream:
                    if 'message' in chunk and 'content' in chunk['message']:
                        content = chunk['message']['content']
                        answer += content
                        if stream_output:
                            # On first chunk, stop the spinner and switch to streaming output
                            if first_chunk:
                                if live_display:
                                    live_display.stop()  # Stop the spinner
                                first_chunk = False

                            # Color-code think tags and content
                            display_content = content

                            # Check for opening <think> tag
                            if '<think>' in content:
                                in_think_block = True
                                display_content = content.replace('<think>', '\033[35m<think>\033[90m')  # Purple tag, then dim gray

                            # Check for closing </think> tag
                            if '</think>' in content:
                                in_think_block = False
                                display_content = display_content.replace('</think>', '\033[35m</think>\033[0m')  # Purple tag, reset color

                            # If we're inside a think block and no tags in this chunk, use dim gray
                            if in_think_block and '<think>' not in content and '</think>' not in content:
                                display_content = f'\033[90m{content}\033[90m'  # Dim gray

                            # Print char by char for real-time display
                            print(display_content, end='', flush=True)

                if stream_output:
                    print()  # New line after streaming

                self.conversation_history.append({"role": "assistant", "content": answer})

                return answer

            except KeyboardInterrupt:
                # Handle interruption gracefully
                if stream_output:
                    print()  # New line
                self.conversation_history.pop()  # Remove user message
                raise  # Re-raise to let CLI handle it
            except Exception as e:
                return f"Error: {str(e)}"
        else:
            # Use ask() method with tools
            # Stop the spinner before streaming output
            first_char_printed = False
            accumulated_text = ""  # Accumulate all text for pattern detection
            in_think = False
            in_sources = False

            def stream_char_by_char(text, char_mode=False):
                """Stream output character by character with color formatting

                Args:
                    text: Text to stream (single char if char_mode=True, full text otherwise)
                    char_mode: If True, treat text as single character and print immediately
                """
                nonlocal first_char_printed, accumulated_text, in_think, in_sources

                # Stop spinner on first character (empty string signals start)
                if not first_char_printed and text == "":
                    if live_display:
                        try:
                            live_display.stop()
                        except:
                            pass
                    first_char_printed = True
                    return

                # If char_mode, accumulate and process character by character
                if char_mode:
                    try:
                        safe_char = text.encode('utf-8', errors='ignore').decode('utf-8')
                        if not safe_char:
                            return

                        accumulated_text += safe_char

                        # Check if we just completed a tag
                        if accumulated_text.endswith('<think>'):
                            # Output everything before <think> in normal color
                            before_tag = accumulated_text[:-7]
                            if before_tag:
                                print(before_tag, end='', flush=True)
                            # Output <think> tag in purple
                            print('\033[35m<think>\033[0m', end='', flush=True)
                            accumulated_text = ""
                            in_think = True
                            return

                        elif accumulated_text.endswith('</think>'):
                            # Output everything before </think> in dim gray
                            before_tag = accumulated_text[:-8]
                            if before_tag:
                                print(f'\033[90m{before_tag}\033[0m', end='', flush=True)
                            # Output </think> tag in purple
                            print('\033[35m</think>\033[0m', end='', flush=True)
                            accumulated_text = ""
                            in_think = False
                            return

                        elif accumulated_text.endswith('-----'):
                            # Output everything before ----- in normal color
                            before_sep = accumulated_text[:-5]
                            if before_sep:
                                print(before_sep, end='', flush=True)
                            # Output separator in dim
                            print('\n\033[2m-----\033[0m\n', end='', flush=True)
                            accumulated_text = ""
                            in_sources = True
                            return

                        # Check if we're building a potential tag (keep accumulating)
                        # Only keep short buffer for specific tags we care about
                        if len(accumulated_text) <= 8:  # Only buffer very short strings
                            potential_tags = ['<', '<t', '<th', '<thi', '<thin', '<think',
                                             '</', '</t', '</th', '</thi', '</thin', '</think',
                                             '-', '--', '---', '----']
                            if accumulated_text.endswith(tuple(potential_tags)):
                                return  # Keep accumulating

                        # Normal output - not building a tag, or buffer is too long
                        if accumulated_text:
                            if in_sources:
                                print(f'\033[2m{accumulated_text}\033[0m', end='', flush=True)
                            elif in_think:
                                print(f'\033[90m{accumulated_text}\033[0m', end='', flush=True)
                            else:
                                print(accumulated_text, end='', flush=True)
                            accumulated_text = ""

                    except:
                        pass
                else:
                    # Original mode: print full text char by char
                    import time
                    for char in text:
                        try:
                            safe_char = char.encode('utf-8', errors='ignore').decode('utf-8')
                            if safe_char:
                                print(safe_char, end='', flush=True)
                                time.sleep(0.005)  # 5ms delay
                        except:
                            pass
                    print()  # New line at end

            # Call ask() with streaming callback
            if stream_output:
                result = self.ask(message, verbose=False, stream_callback=stream_char_by_char)

                # Flush any remaining accumulated text
                if accumulated_text:
                    if in_sources:
                        print(f'\033[2m{accumulated_text}\033[0m', end='', flush=True)
                    elif in_think:
                        print(f'\033[90m{accumulated_text}\033[0m', end='', flush=True)
                    else:
                        print(accumulated_text, end='', flush=True)

                # Reset color at the end
                print('\033[0m', end='', flush=True)
            else:
                # Stop spinner immediately if no streaming
                if live_display:
                    try:
                        live_display.stop()
                    except:
                        pass
                result = self.ask(message, verbose=False)
                print(result['answer'])

            return result['answer']

    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []

    def rebuild_map(self):
        """Rebuild the knowledge map"""
        print("Rebuilding knowledge map...")
        result = generate_knowledge_map(str(self.directory))
        print(result)

        # Reload the map
        self.knowledge_map = load_knowledge_map(str(self.directory))

        return result

    def get_document_count(self) -> int:
        """Get the number of documents in the knowledge map"""
        if self.knowledge_map:
            return self.knowledge_map.get('total_documents', 0)
        return 0

    def list_documents(self) -> List[Dict]:
        """List all documents in the knowledge map"""
        if self.knowledge_map and 'documents' in self.knowledge_map:
            return self.knowledge_map['documents']
        return []

    def reload_knowledge_map(self):
        """Reload the knowledge map from disk"""
        self.knowledge_map = load_knowledge_map(str(self.directory))
        self.watcher = DocumentWatcher(str(self.directory))  # Reset watcher

    def check_for_updates(self) -> Optional[str]:
        """Check if documents have changed and return warning message if needed.

        Returns:
            Warning message if updates are needed, None otherwise
        """
        if self.watcher.has_changes():
            summary = self.watcher.get_change_summary()
            return f"⚠️  Document changes detected:\n{summary}\n\nConsider running 'locallm rebuild-map' to update the knowledge base."
        return None

    def _is_incomplete_answer(self, answer: str) -> bool:
        """Check if an answer seems incomplete or indicates failure.

        Args:
            answer: The AI's answer

        Returns:
            True if answer seems incomplete
        """
        incomplete_indicators = [
            "I cannot",
            "I don't have",
            "no information",
            "not found",
            "unable to",
            "無法",
            "找不到",
            "沒有資訊",
        ]

        answer_lower = answer.lower()
        return any(indicator.lower() in answer_lower for indicator in incomplete_indicators)

    def _fallback_keyword_search(self, question: str) -> str:
        """Perform keyword search as fallback when AI cannot answer.

        Args:
            question: Original question

        Returns:
            Search results or helpful message
        """
        # Extract potential keywords (simple approach: words > 3 chars, excluding common words)
        import re
        from pathlib import Path

        stop_words = {'what', 'when', 'where', 'which', 'who', 'how', 'the', 'this', 'that', 'with', 'from', 'for', 'are', 'was', 'were'}
        words = re.findall(r'\b\w{4,}\b', question.lower())
        keywords = [w for w in words if w not in stop_words]

        if not keywords:
            return "💡 **Suggestion**: Try rephrasing your question or use 'locallm search <keyword>' to search documents directly."

        # Try searching for the first meaningful keyword
        keyword = keywords[0]

        result_lines = [f"💡 **Fallback Search Results** (keyword: '{keyword}'):\n"]

        supported_exts = {'.pdf', '.docx', '.doc', '.txt', '.md', '.markdown'}
        found_any = False

        try:
            for file_path in self.directory.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in supported_exts:
                    grep_result = grep.invoke({"pattern": keyword, "file_path": str(file_path), "context_lines": 2})

                    if not grep_result.startswith("No matches"):
                        result_lines.append(f"**In {file_path.name}:**")
                        # Show first 200 chars of result
                        result_lines.append(grep_result[:200] + "...")
                        result_lines.append("")
                        found_any = True

                        # Limit to first 3 files
                        if len(result_lines) > 10:
                            break

            if not found_any:
                return f"💡 No direct matches found. Try using 'locallm search {keyword}' or 'locallm list' to explore available documents."

            return "\n".join(result_lines)

        except Exception as e:
            return f"💡 **Suggestion**: Try 'locallm search {keyword}' to search documents directly."
