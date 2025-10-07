"""Model-specific configurations for context window and parameters"""

from typing import Dict, Any


# Model context window sizes (in tokens)
MODEL_CONTEXT_WINDOWS = {
    # Qwen models
    'qwen3:latest': 32768,
    'qwen3': 32768,
    'qwen2.5': 32768,
    'qwen2': 32768,
    'qwen':  32768,

    # Llama models
    'llama3.3': 131072,
    'llama3.2': 131072,
    'llama3.1': 131072,
    'llama3': 8192,
    'llama2': 4096,

    # Mistral models
    'mistral': 32768,
    'mistral-nemo': 131072,
    'mixtral': 32768,

    # DeepSeek models
    'deepseek-r1': 65536,
    'deepseek-v3': 65536,
    'deepseek-coder': 16384,

    # Gemma models
    'gemma2': 8192,
    'gemma': 8192,

    # Phi models
    'phi3': 131072,
    'phi4': 16384,

    # Other models
    'codegemma': 8192,
    'command-r': 131072,
    'command-r-plus': 131072,
}

# Default context window for unknown models
DEFAULT_CONTEXT_WINDOW = 8192


def get_model_context_window(model_name: str) -> int:
    """Get context window size for a given model.

    Args:
        model_name: Name of the model (e.g., 'qwen3:latest', 'llama3')

    Returns:
        Context window size in tokens
    """
    # Remove version suffix if present (e.g., 'qwen3:latest' -> 'qwen3')
    base_model = model_name.split(':')[0].lower()

    # Try exact match first
    if base_model in MODEL_CONTEXT_WINDOWS:
        return MODEL_CONTEXT_WINDOWS[base_model]

    # Try prefix match (e.g., 'qwen3-32k' matches 'qwen3')
    for key in MODEL_CONTEXT_WINDOWS:
        if base_model.startswith(key):
            return MODEL_CONTEXT_WINDOWS[key]

    # Return default
    return DEFAULT_CONTEXT_WINDOW


def get_optimal_context_for_task(model_name: str, task_type: str = 'qa') -> int:
    """Get optimal context window for a specific task.

    Args:
        model_name: Name of the model
        task_type: Type of task ('qa', 'chat', 'map_generation')

    Returns:
        Optimal context window size
    """
    max_context = get_model_context_window(model_name)

    # Task-specific recommendations
    if task_type == 'qa':
        # Q&A: Use 60% of max context (留空間給文檔內容)
        return min(int(max_context * 0.6), 32768)

    elif task_type == 'chat':
        # Chat: Use 40% of max context (需要保留歷史記錄空間)
        return min(int(max_context * 0.4), 16384)

    elif task_type == 'map_generation':
        # Map generation: Use smaller context (只需要摘要)
        return min(int(max_context * 0.3), 8192)

    else:
        # Default: Use 50% of max
        return int(max_context * 0.5)


def get_model_config(model_name: str, task_type: str = 'qa') -> Dict[str, Any]:
    """Get complete model configuration for Ollama.

    Args:
        model_name: Name of the model
        task_type: Type of task

    Returns:
        Dictionary of Ollama options
    """
    context_window = get_optimal_context_for_task(model_name, task_type)

    config = {
        'num_ctx': context_window,
        'num_predict': -1,  # No limit on generation length
        'temperature': 0.3,  # Default temperature (can be overridden)
    }

    # Model-specific optimizations
    base_model = model_name.split(':')[0].lower()

    if base_model.startswith('qwen'):
        # Qwen models work well with slightly higher temperature
        config['temperature'] = 0.35
        config['top_p'] = 0.8

    elif base_model.startswith('llama'):
        # Llama models benefit from lower temperature for accuracy
        config['temperature'] = 0.2
        config['top_p'] = 0.9

    elif base_model.startswith('deepseek'):
        # DeepSeek models are optimized for reasoning
        config['temperature'] = 0.1
        config['top_p'] = 0.95

    return config


def format_model_info(model_name: str) -> str:
    """Format model information for display.

    Args:
        model_name: Name of the model

    Returns:
        Formatted string with model info
    """
    max_ctx = get_model_context_window(model_name)
    qa_ctx = get_optimal_context_for_task(model_name, 'qa')
    chat_ctx = get_optimal_context_for_task(model_name, 'chat')

    return f"""Model: {model_name}
Max Context: {max_ctx:,} tokens
Q&A Context: {qa_ctx:,} tokens
Chat Context: {chat_ctx:,} tokens"""
