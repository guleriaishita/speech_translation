"""
Translation service using DeepL API.
Best-in-class translation quality with generous free tier!
"""

import os
import logging
from typing import Optional
from functools import lru_cache
import time

logger = logging.getLogger(__name__)


# ============================================================================
# BASE TRANSLATOR (ABSTRACT)
# ============================================================================

class BaseTranslator:
    """Abstract base class for translation services"""
    
    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text from source to target language"""
        pass


# ============================================================================
# DEEPL TRANSLATOR
# ============================================================================

class DeepLTranslator(BaseTranslator):
    """
    Translation using DeepL API.
    
    Pros:
    - Best-in-class translation quality (better than Google)
    - Free tier: 500,000 characters/month
    - Fast and reliable
    - 30+ languages supported
    
    Setup:
    1. Sign up at https://www.deepl.com/pro-api (free tier, no credit card)
    2. Get your API key
    3. Add to .env: DEEPL_API_KEY=your_key_here
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize DeepL translator.
        
        Args:
            api_key: DeepL API key (or set DEEPL_API_KEY env var)
        """
        self.api_key = api_key or os.getenv('DEEPL_API_KEY')
        if not self.api_key:
            raise ValueError(
                "DeepL API key required! Get one free at:\n"
                "https://www.deepl.com/pro-api\n"
                "Then set DEEPL_API_KEY in your .env file"
            )
        
        # Import deepl here to avoid import errors if not installed
        try:
            import deepl
            self.translator = deepl.Translator(self.api_key)
        except ImportError:
            raise ImportError(
                "deepl library not installed! "
                "Install with: pip install deepl"
            )
        
        # Language code mapping (ISO 639-1 to DeepL codes)
        # DeepL uses uppercase 2-letter codes, some with variants
        self.lang_map = {
            'en': 'EN',
            'es': 'ES',
            'fr': 'FR',
            'de': 'DE',
            'it': 'IT',
            'pt': 'PT',  # Portuguese (auto-detects Brazilian/European)
            'nl': 'NL',
            'ru': 'RU',
            'zh': 'ZH',
            'ja': 'JA',
            'pl': 'PL',
            'uk': 'UK',
            'cs': 'CS',
            'sv': 'SV',
            'el': 'EL',
            'hu': 'HU',
            'da': 'DA',
            'fi': 'FI',
            'no': 'NB',  # Norwegian Bokmål
            'ro': 'RO',
            'sk': 'SK',
            'bg': 'BG',
            'id': 'ID',
            'tr': 'TR',
            'ko': 'KO',
        }
        
        logger.info("✓ Initialized DeepL Translator (API)")
    
    def _get_deepl_lang_code(self, lang_code: str) -> str:
        """Convert ISO 639-1 code to DeepL language code"""
        deepl_code = self.lang_map.get(lang_code.lower())
        if not deepl_code:
            logger.warning(f"Language '{lang_code}' not in mapping, using English")
            deepl_code = 'EN'
        return deepl_code
    
    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text using HuggingFace API"""
        
        if not text or not text.strip():
            return ""
        
        # Skip if source and target are the same
        if source_lang.lower() == target_lang.lower():
            return text
        
        try:
            # Convert language codes
            tgt_code = self._get_deepl_lang_code(target_lang)
            
            # DeepL API call - it handles long text automatically
            result = self.translator.translate_text(
                text,
                target_lang=tgt_code
            )
            
            logger.info(f"✓ Translated {len(text)} chars: {source_lang} → {target_lang}")
            return result.text
            
        except Exception as e:
            logger.error(f"DeepL translation error: {e}")
            logger.warning("Returning original text")
            return text
    





# ============================================================================
# SIMPLE TRANSLATOR (Fallback)
# ============================================================================

class SimpleTranslator(BaseTranslator):
    """Fallback translator that returns original text"""
    
    def __init__(self):
        logger.warning("Using SimpleTranslator - no actual translation will occur")
    
    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Return original text (no translation)"""
        logger.info(f"SimpleTranslator: returning original text ({source_lang} -> {target_lang})")
        return text


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

@lru_cache(maxsize=1)
def get_translator(service_type: str = 'deepl') -> BaseTranslator:
    """
    Factory function to get translator instance.
    
    Args:
        service_type: Type of translator ('deepl', 'simple')
        
    Returns:
        BaseTranslator instance
    """
    service_type = service_type.lower()
    
    if service_type == 'deepl':
        try:
            return DeepLTranslator()
        except Exception as e:
            logger.error(f"Failed to initialize DeepLTranslator: {e}")
            logger.warning("Falling back to SimpleTranslator")
            return SimpleTranslator()
    
    elif service_type == 'simple':
        return SimpleTranslator()
    
    else:
        logger.warning(f"Unknown service type '{service_type}', using 'deepl'")
        return get_translator('deepl')


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

def translate_text(
    text: str,
    source_lang: str,
    target_lang: str,
    service_type: Optional[str] = None
) -> str:
    """
    Convenience function for quick translation.
    
    Args:
        text: Text to translate
        source_lang: Source language code
        target_lang: Target language code
        service_type: Optional service type (defaults to 'huggingface')
        
    Returns:
        Translated text
    """
    if service_type is None:
        service_type = os.getenv('TRANSLATION_SERVICE', 'deepl')
    
    translator = get_translator(service_type)
    return translator.translate(text, source_lang, target_lang)
