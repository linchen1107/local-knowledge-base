"""Configuration management utilities"""

import yaml
from pathlib import Path
from typing import Dict, Any


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config file (default: config.yaml in current dir)

    Returns:
        Configuration dictionary
    """
    # Try to find config in multiple locations
    search_paths = [
        Path(config_path),  # Current directory
        Path.cwd() / config_path,  # Explicit current directory
        Path(__file__).parent.parent.parent / config_path,  # Package root
    ]

    for path in search_paths:
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)

    # Return default config if not found
    return get_default_config()


def get_default_config() -> Dict[str, Any]:
    """Get default configuration.

    Returns:
        Default configuration dictionary
    """
    return {
        'ollama': {
            'base_url': 'http://localhost:11434',
            'model': 'qwen3:latest',
            'temperature': 0.3,
            'timeout': 120
        },
        'agent': {
            'max_iterations': 10,
            'verbose': True
        },
        'documents': {
            'supported_types': ['pdf', 'docx', 'doc', 'txt', 'md', 'markdown'],
            'max_file_size_mb': 100,
            'encoding': 'utf-8'
        },
        'knowledge_map': {
            'filename': 'knowledge_map.yaml',
            'auto_rebuild': False,
            'description_max_tokens': 8000
        },
        'display': {
            'show_sources': True,
            'show_tool_calls': True,
            'color_scheme': 'default'
        }
    }


def get_default_model() -> str:
    """Get default model from config.

    Returns:
        Default model name
    """
    config = load_config()
    return config.get('ollama', {}).get('model', 'qwen3:latest')
