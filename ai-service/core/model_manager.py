"""
Model Manager - Direct SDK and REST API Implementation
- Groq: Direct SDK
- Gemini: REST API (google-genai package has model name issues)
"""

from groq import Groq
from typing import Tuple, Optional
import logging
import httpx

from core.config import settings

logger = logging.getLogger(__name__)


class ModelManager:
    """Manages LLMs using direct SDKs and REST APIs."""
    
    def __init__(self):
        """Initialize provider clients."""
        self.gemini_api_key = None
        self.groq_client = None
        
        # Google Gemini (REST API)
        if settings.GOOGLE_API_KEY:
            try:
                self.gemini_api_key = settings.GOOGLE_API_KEY
                logger.info("✅ Gemini REST API ready")
            except Exception as e:
                logger.error(f"❌ Gemini init failed: {e}")
        
        # Groq
        if settings.GROQ_API_KEY:
            try:
                self.groq_client = Groq(api_key=settings.GROQ_API_KEY)
                logger.info("✅ Groq client ready")
            except Exception as e:
                logger.error(f"❌ Groq init failed: {e}")
    
    def get_model(self, task_type: str, complexity: str = "low", force_provider: Optional[str] = None) -> Tuple[str, str]:
        """
        Get model for task with PRIMARY_PROVIDER preference.
        Returns: (provider_name, model_identifier)
        - For Gemini: ("gemini-flash", "gemini-1.5-flash-002") 
        - For Groq: ("groq-llama", "llama-3.3-70b-versatile")
        
        Args:
            task_type: Type of task (rag_query, direct_chat, etc.)
            complexity: low, medium, high
            force_provider: Force specific provider ("gemini" or "groq")
        """
        # Force provider if specified
        if force_provider == "groq" and self.groq_client:
            return ("groq-llama", settings.GROQ_LLAMA_MODEL)
        elif force_provider == "gemini" and self.gemini_api_key:
            # Use Flash for simple, Pro for complex
            if complexity == "high":
                return ("gemini-pro", settings.GEMINI_PRO_MODEL)
            return ("gemini-flash", settings.GEMINI_FLASH_MODEL)
        
        # Respect PRIMARY_PROVIDER setting
        print(f"🔧 PRIMARY_PROVIDER={settings.PRIMARY_PROVIDER}, complexity={complexity}")
        if settings.PRIMARY_PROVIDER == "groq" and self.groq_client:
            # Groq as primary: Use for most tasks
            print(f"✅ Using PRIMARY: Groq Llama (unlimited)")
            return ("groq-llama", settings.GROQ_LLAMA_MODEL)
        
        # Gemini as primary (default): Smart selection
        model_key = self._select_model_key(task_type, complexity)
        
        if model_key == "gemini_flash" and self.gemini_api_key:
            return ("gemini-flash", settings.GEMINI_FLASH_MODEL)
        elif model_key == "gemini_pro" and self.gemini_api_key:
            return ("gemini-pro", settings.GEMINI_PRO_MODEL)
        elif model_key == "groq" and self.groq_client:
            return ("groq-llama", settings.GROQ_LLAMA_MODEL)
        
        # Ultimate Fallback based on FALLBACK_PROVIDER
        if settings.FALLBACK_PROVIDER == "groq" and self.groq_client:
            logger.warning("⚠️ Using FALLBACK: Groq")
            return ("groq-llama", settings.GROQ_LLAMA_MODEL)
        elif settings.FALLBACK_PROVIDER == "gemini" and self.gemini_api_key:
            logger.warning("⚠️ Using FALLBACK: Gemini Flash")
            return ("gemini-flash", settings.GEMINI_FLASH_MODEL)
        
        # Legacy fallback (if FALLBACK_PROVIDER not set correctly)
        if self.groq_client:
            logger.warning("⚠️ Using Groq fallback")
            return ("groq-llama", settings.GROQ_LLAMA_MODEL)
        elif self.gemini_api_key:
            logger.warning("⚠️ Using Gemini Flash fallback")
            return ("gemini-flash", settings.GEMINI_FLASH_MODEL)
        
        raise ValueError("No LLM available!")
    
    def _select_model_key(self, task_type: str, complexity: str) -> str:
        """Select best model based on task and complexity."""
        # Complex tasks always use Pro for accuracy
        if task_type in ["summarization", "question_generation", "homework_solver"]:
            return "gemini_pro"
        
        # RAG queries: Pro for high complexity
        if task_type == "rag_query" and complexity in ["high", "medium"]:
            return "gemini_pro"
        
        # Direct chat: Smart selection based on complexity
        if task_type == "direct_chat":
            if complexity == "low":
                return "gemini_flash"  # Fast for simple queries
            elif complexity in ["medium", "high"]:
                return "gemini_pro"  # Accurate for complex knowledge
        
        # Code help: Pro for better accuracy
        if task_type == "code_help":
            return "gemini_pro"
        
        # Default: Flash for speed
        return "gemini_flash"
    
    def generate_text(
        self, 
        provider_name: str, 
        model_identifier: str,
        prompt: str, 
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 8000,
        enable_fallback: bool = True
    ) -> str:
        """
        Generate text with provider and automatic fallback.
        
        Args:
            provider_name: Primary provider name
            model_identifier: Model identifier
            prompt: User prompt
            system_instruction: System instruction
            temperature: Temperature
            max_tokens: Max tokens
            enable_fallback: Enable automatic fallback to Groq if primary fails
        
        Returns:
            Generated text
        """
        try:
            if "gemini" in provider_name:
                return self._generate_gemini(
                    model_identifier, prompt, system_instruction, 
                    temperature, max_tokens
                )
            
            elif "groq" in provider_name:
                return self._generate_groq(
                    model_identifier, prompt, system_instruction,
                    temperature, max_tokens
                )
            
            else:
                raise ValueError(f"Unknown provider: {provider_name}")
        
        except Exception as e:
            error_str = str(e)
            logger.error(f"❌ Generation failed ({provider_name}): {e}")
            
            # Automatic fallback to Groq if enabled and available
            if enable_fallback and "gemini" in provider_name and self.groq_client:
                logger.warning(f"⚠️ Fallback: Gemini failed → Switching to Groq Llama")
                try:
                    return self._generate_groq(
                        settings.GROQ_LLAMA_MODEL,
                        prompt,
                        system_instruction,
                        temperature,
                        max_tokens
                    )
                except Exception as fallback_error:
                    logger.error(f"❌ Fallback also failed: {fallback_error}")
                    raise Exception(f"Primary and fallback failed. Primary: {error_str}, Fallback: {fallback_error}")
            
            raise
    
    def _generate_gemini(
        self,
        model_identifier: str,
        prompt: str,
        system_instruction: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate text using Gemini REST API."""
        full_prompt = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt
        
        url = f"https://generativelanguage.googleapis.com/v1/models/{model_identifier}:generateContent?key={self.gemini_api_key}"
        
        payload = {
            "contents": [{
                "parts": [{"text": full_prompt}]
            }],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }
        
        with httpx.Client(timeout=240.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            # Extract text from response
            if "candidates" in data and len(data["candidates"]) > 0:
                candidate = data["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    return candidate["content"]["parts"][0]["text"]
            
            raise ValueError(f"Unexpected Gemini response format: {data}")
    
    def _generate_groq(
        self,
        model_identifier: str,
        prompt: str,
        system_instruction: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate text using Groq SDK."""
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        completion = self.groq_client.chat.completions.create(
            model=model_identifier,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return completion.choices[0].message.content


# Singleton instance
model_manager = ModelManager()
