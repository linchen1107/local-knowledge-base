"""Language detection and multilingual support"""

import re
from typing import Tuple


def detect_language(text: str) -> str:
    """Detect the primary language of a text.

    Args:
        text: Text to analyze

    Returns:
        Language code: 'zh' (Chinese), 'en' (English), 'ja' (Japanese), etc.
    """
    # Count characters from different scripts
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    japanese_chars = len(re.findall(r'[\u3040-\u309f\u30a0-\u30ff]', text))
    korean_chars = len(re.findall(r'[\uac00-\ud7af]', text))

    total_chars = len(text.strip())

    if total_chars == 0:
        return 'en'

    # Calculate percentages
    chinese_pct = chinese_chars / total_chars
    japanese_pct = japanese_chars / total_chars
    korean_pct = korean_chars / total_chars

    # Detect based on character distribution
    # Lower threshold to 10% or at least 1 Chinese character for better detection of short queries
    if chinese_chars > 0 and (chinese_pct > 0.1 or chinese_chars >= 1):
        return 'zh'
    elif japanese_chars > 0 and (japanese_pct > 0.1 or japanese_chars >= 1):
        return 'ja'
    elif korean_chars > 0 and (korean_pct > 0.1 or korean_chars >= 1):
        return 'ko'
    else:
        return 'en'


def get_language_instruction(lang: str) -> str:
    """Get language-specific instruction for the AI.

    Args:
        lang: Language code

    Returns:
        Instruction string
    """
    instructions = {
        'zh': "請用繁體中文回答問題。",
        'zh_hans': "请用简体中文回答问题。",
        'ja': "日本語で回答してください。",
        'ko': "한국어로 답변해 주세요.",
        'en': "Please answer in English.",
        'es': "Por favor responde en español.",
        'fr': "Veuillez répondre en français.",
        'de': "Bitte antworten Sie auf Deutsch.",
    }

    return instructions.get(lang, instructions['en'])


def get_ui_strings(lang: str) -> dict:
    """Get UI strings for a specific language.

    Args:
        lang: Language code

    Returns:
        Dictionary of UI strings
    """
    strings = {
        'en': {
            'analyzing': 'Analyzing...',
            'reading_file': 'Reading {}...',
            'searching': 'Searching...',
            'listing_docs': 'Listing documents...',
            'thinking': 'Thinking...',
            'answer': 'Answer',
            'sources': 'Sources',
            'error': 'Error',
            'completed': 'Completed',
        },
        'zh': {
            'analyzing': '分析中...',
            'reading_file': '正在讀取 {}...',
            'searching': '搜尋中...',
            'listing_docs': '列出文件...',
            'thinking': '思考中...',
            'answer': '回答',
            'sources': '來源',
            'error': '錯誤',
            'completed': '完成',
        },
        'ja': {
            'analyzing': '分析中...',
            'reading_file': '{}を読み込んでいます...',
            'searching': '検索中...',
            'listing_docs': 'ドキュメントをリストしています...',
            'thinking': '考え中...',
            'answer': '回答',
            'sources': 'ソース',
            'error': 'エラー',
            'completed': '完了',
        }
    }

    return strings.get(lang, strings['en'])
