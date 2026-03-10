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
        self._groq_rate_limited = False  # Set True when Groq 429 TPD hit; resets on restart
        
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
        print(f"\U0001f527 PRIMARY_PROVIDER={settings.PRIMARY_PROVIDER}, task={task_type}, complexity={complexity}")
        
        # Smart selection based on task + complexity (regardless of PRIMARY_PROVIDER)
        # Groq for simple/moderate, Gemini for complex — best use of both quotas
        model_key = self._select_model_key(task_type, complexity)
        
        if model_key == "gemini_flash" and self.gemini_api_key:
            print(f"✅ Selected: Gemini Flash ({task_type} / {complexity})")
            return ("gemini-flash", settings.GEMINI_FLASH_MODEL)
        elif model_key == "gemini_pro" and self.gemini_api_key:
            print(f"✅ Selected: Gemini Pro ({task_type} / {complexity})")
            return ("gemini-pro", settings.GEMINI_PRO_MODEL)
        elif model_key == "groq":
            if self.groq_client and not self._groq_rate_limited:
                print(f"✅ Selected: Groq Llama ({task_type} / {complexity})")
                return ("groq-llama", settings.GROQ_LLAMA_MODEL)
            # Groq unavailable or rate-limited → upgrade to Gemini Flash
            logger.warning(f"⚠️ Groq unavailable/rate-limited → upgrading to Gemini Flash")
            if self.gemini_api_key:
                return ("gemini-flash", settings.GEMINI_FLASH_MODEL)
        
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
        """
        Phân phối model theo độ phức tạp:
          simple/low     → Groq  (nhanh, tiết kiệm Gemini quota)
          moderate/medium → Groq  (đủ chất lượng cho phần lớn câu hỏi)
          complex/high   → Gemini Flash (cần chất lượng cao, tổng hợp nhiều thông tin)
        
        complexity có thể là "simple"/"moderate"/"complex" (từ analyzer)
        hoặc "low"/"medium"/"high" (từ các agent sau khi map)
        """
        # Tổng hợp / phân tích toàn bộ → Gemini Flash bất kể complexity
        if task_type in ["summarization", "question_generation", "homework_solver"]:
            return "gemini_flash"
        
        # Phân phối theo complexity (chấp nhận cả 2 naming convention)
        if complexity in ("simple", "low"):
            return "groq"           # Groq: nhanh + miễn phí
        elif complexity in ("moderate", "medium"):
            return "groq"           # Groq vẫn đủ chất lượng
        else:  # complex / high
            return "gemini_flash"   # Gemini Flash: hiểu sâu, tổng hợp tốt
    
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
            
            # If Groq itself is the primary and hits 429, flag it and try Gemini fallback
            if "groq" in provider_name and ("429" in error_str or "rate_limit_exceeded" in error_str):
                self._groq_rate_limited = True
                logger.error("❌ Groq TPD 429 while using Groq as primary — flagging as exhausted")
                if self.gemini_api_key:
                    logger.warning("⚠️ Groq 429 → Retrying with Gemini Flash")
                    try:
                        return self._generate_gemini(
                            settings.GEMINI_FLASH_MODEL, prompt, system_instruction,
                            temperature, max_tokens
                        )
                    except Exception as gem_err:
                        raise Exception(f"Groq hết quota ngày hôm nay và Gemini cũng lỗi: {gem_err}")
                raise Exception(
                    "Groq đã hết quota hôm nay (100k tokens/ngày). "
                    "Vui lòng đổi PRIMARY_PROVIDER=gemini trong .env và restart service."
                )
            
            # Automatic fallback to Groq if enabled and available
            # BUT: don't fall back to Groq if Groq itself is rate-limited (429)
            if enable_fallback and "gemini" in provider_name and self.groq_client:
                # Check if Groq is already known to be rate-limited
                if getattr(self, '_groq_rate_limited', False):
                    logger.warning("⚠️ Skipping Groq fallback — Groq daily limit (TPD) exhausted")
                    raise Exception(f"Gemini failed và Groq đã hết quota ngày hôm nay. Vui lòng thử lại vào ngày mai.")
                logger.warning(f"⚠️ Fallback: Gemini failed → Switching to Groq Llama")
                try:
                    # Use smaller token budget on Groq to preserve daily quota (100k TPD)
                    groq_max_tokens = min(max_tokens, 2048)
                    return self._generate_groq(
                        settings.GROQ_LLAMA_MODEL,
                        prompt,
                        system_instruction,
                        temperature,
                        groq_max_tokens
                    )
                except Exception as fallback_error:
                    fallback_str = str(fallback_error)
                    if "429" in fallback_str or "rate_limit_exceeded" in fallback_str:
                        self._groq_rate_limited = True
                        logger.error("❌ Groq 429: daily TPD limit reached")
                        raise Exception(
                            "Groq đã hết quota hôm nay (100k tokens/ngày). "
                            "Hệ thống đang chỉ dùng Gemini. Nếu Gemini cũng lỗi, vui lòng thử lại sau."
                        )
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
        
        # v1beta supports all models including gemini-2.5; v1 does not support 2.5 yet
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_identifier}:generateContent?key={self.gemini_api_key}"
        
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
