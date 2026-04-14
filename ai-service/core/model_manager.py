"""
Model Manager - Direct SDK and REST API Implementation
- Groq: Direct SDK
- Gemini: REST API (google-genai package has model name issues)
"""

from groq import Groq
from typing import Tuple, Optional
import logging
import httpx
from datetime import datetime, timedelta, timezone

from core.config import settings

logger = logging.getLogger(__name__)


class ModelManager:
    """Manages LLMs using direct SDKs and REST APIs."""
    
    def __init__(self):
        """Initialize provider clients."""
        self.gemini_api_key = None
        self.mistral_api_key = None
        self.openai_api_key = None
        self.anthropic_api_key = None
        self.groq_client = None
        self._groq_rate_limited = False  # Set True when Groq 429 TPD hit; resets on restart
        self._gemini_rate_limited = False
        self._mistral_rate_limited = False
        self._openai_rate_limited = False
        self._anthropic_rate_limited = False
        self._groq_rate_limited_until = None
        self._gemini_rate_limited_until = None
        self._mistral_rate_limited_until = None
        self._openai_rate_limited_until = None
        self._anthropic_rate_limited_until = None
        
        self.gemini_api_keys = []
        self.current_gemini_key_idx = -1
        self.gemini_keys_status = {}
        
        # Google Gemini (REST API)
        if settings.GOOGLE_API_KEY:
            try:
                keys = [k.strip() for k in settings.GOOGLE_API_KEY.split(',') if k.strip()]
                if keys:
                    self.gemini_api_keys = keys
                    self.gemini_api_key = keys[0]
                    logger.info(f"✅ Gemini REST API ready with {len(keys)} rotated keys")
            except Exception as e:
                logger.error(f"❌ Gemini init failed: {e}")
        
        # Groq
        if settings.GROQ_API_KEY:
            try:
                self.groq_client = Groq(api_key=settings.GROQ_API_KEY)
                logger.info("✅ Groq client ready")
            except Exception as e:
                logger.error(f"❌ Groq init failed: {e}")

        # OpenAI
        if settings.OPENAI_API_KEY:
            self.openai_api_key = settings.OPENAI_API_KEY
            logger.info("✅ OpenAI API key ready")

        # Anthropic
        if settings.ANTHROPIC_API_KEY:
            self.anthropic_api_key = settings.ANTHROPIC_API_KEY
            logger.info("✅ Anthropic API key ready")

        # Mistral
        if settings.MISTRAL_API_KEY:
            self.mistral_api_key = settings.MISTRAL_API_KEY
            logger.info("✅ Mistral API key ready")
    
    def get_model(self, task_type: str, complexity: str = "low", force_provider: Optional[str] = None) -> Tuple[str, str]:
        """
        Get model for task with PRIMARY_PROVIDER preference.
        Returns: (provider_name, model_identifier)
        - For Gemini: ("gemini-flash", "gemini-1.5-flash-002") 
        - For Groq: ("groq-llama", "llama-3.3-70b-versatile")
        
        Args:
            task_type: Type of task (rag_query, direct_chat, query_rewrite, etc.)
            complexity: low, medium, high
            force_provider: Force specific provider (gemini, groq, mistral)
        """
        self._refresh_rate_limit_flags()

        if force_provider:
            forced = force_provider.lower().strip()
            if forced == "groq" and self._provider_available("groq"):
                return ("groq-llama", settings.GROQ_LLAMA_MODEL)
            if forced == "gemini" and self._provider_available("gemini"):
                return (
                    "gemini-pro" if complexity == "high" else "gemini-flash",
                    settings.GEMINI_PRO_MODEL if complexity == "high" else settings.GEMINI_FLASH_MODEL,
                )
            if forced == "mistral" and self._provider_available("mistral"):
                return ("mistral", settings.MISTRAL_MODEL)
            logger.warning(f"⚠️ Forced provider '{force_provider}' unavailable, using dynamic routing")
        
        logger.info(f"🔧 Routing task={task_type}, complexity={complexity}, primary={settings.PRIMARY_PROVIDER}")

        candidate_order = self._select_model_candidates(task_type, complexity)
        for model_key in candidate_order:
            selected = self._resolve_model_key(model_key)
            if selected:
                provider_name, model_identifier = selected
                logger.info(f"✅ Selected {provider_name} for task={task_type}, complexity={complexity}")
                return provider_name, model_identifier

        # Explicit fallback provider (only supported providers for current strategy)
        fallback_provider = (settings.FALLBACK_PROVIDER or "").strip().lower()
        if fallback_provider == "groq":
            selected = self._resolve_model_key("groq")
            if selected:
                logger.warning("⚠️ Using FALLBACK_PROVIDER=groq")
                return selected
        elif fallback_provider == "gemini":
            selected = self._resolve_model_key("gemini_flash")
            if selected:
                logger.warning("⚠️ Using FALLBACK_PROVIDER=gemini")
                return selected
        elif fallback_provider == "mistral":
            selected = self._resolve_model_key("mistral")
            if selected:
                logger.warning("⚠️ Using FALLBACK_PROVIDER=mistral")
                return selected

        # Last resort
        for model_key in ["groq", "gemini_flash", "mistral", "gemini_pro"]:
            selected = self._resolve_model_key(model_key)
            if selected:
                logger.warning(f"⚠️ Using last-resort provider {selected[0]}")
                return selected

        raise ValueError("No LLM available!")

    def _select_model_candidates(self, task_type: str, complexity: str) -> list[str]:
        """
        Return ordered model keys by task profile.

        Policy:
        - Helper/intermediate steps: prefer Groq first.
        - Final heavy answers: prefer stronger model first (Gemini Pro/Flash, then Mistral).
        """
        task = (task_type or "").strip().lower()
        level = (complexity or "").strip().lower()

        helper_tasks = {
            "intent_classification",
            "query_rewrite",
            "corrective_rag",
            "rerank",
            "document_map",
            "general",
        }

        if task in helper_tasks:
            return ["groq", "gemini_flash", "mistral", "gemini_pro"]

        if task == "entity_extraction":
            return ["gemini_flash", "mistral", "groq"]

        if task in {"summarization", "question_generation", "rag_query"}:
            if level in {"complex", "high"}:
                return ["gemini_pro", "mistral", "gemini_flash", "groq"]
            return ["gemini_flash", "mistral", "groq", "gemini_pro"]

        if task in {"code_help", "homework_solver", "data_analysis"}:
            if level in {"complex", "high"}:
                return ["mistral", "gemini_pro", "groq", "gemini_flash"]
            return ["groq", "mistral", "gemini_flash", "gemini_pro"]

        if level in {"complex", "high"}:
            return ["gemini_pro", "mistral", "gemini_flash", "groq"]
        if level in {"moderate", "medium"}:
            return ["groq", "gemini_flash", "mistral", "gemini_pro"]
        return ["groq", "gemini_flash", "mistral", "gemini_pro"]

    def _resolve_model_key(self, model_key: str) -> Optional[Tuple[str, str]]:
        key = (model_key or "").lower()
        if key == "groq" and self._provider_available("groq"):
            return ("groq-llama", settings.GROQ_LLAMA_MODEL)
        if key == "gemini_flash" and self._provider_available("gemini"):
            return ("gemini-flash", settings.GEMINI_FLASH_MODEL)
        if key == "gemini_pro" and self._provider_available("gemini"):
            return ("gemini-pro", settings.GEMINI_PRO_MODEL)
        if key == "mistral" and self._provider_available("mistral"):
            return ("mistral", settings.MISTRAL_MODEL)
        return None
    
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
        self._refresh_rate_limit_flags()
        try:
            if "gemini" in provider_name:
                return self._generate_gemini(
                    model_identifier, prompt, system_instruction, 
                    temperature, max_tokens
                )
            elif "openai" in provider_name:
                return self._generate_openai(
                    model_identifier, prompt, system_instruction,
                    temperature, max_tokens
                )
            elif "claude" in provider_name:
                return self._generate_claude(
                    model_identifier, prompt, system_instruction,
                    temperature, max_tokens
                )
            elif "mistral" in provider_name:
                return self._generate_mistral(
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

            # Mark Gemini as temporarily rate-limited on quota/429 errors.
            if "gemini" in provider_name and self._is_rate_limit_error(error_str):
                self._gemini_rate_limited = True
                self._gemini_rate_limited_until = self._estimate_reset_time(daily=False)
            if "openai" in provider_name and self._is_rate_limit_error(error_str):
                self._openai_rate_limited = True
                self._openai_rate_limited_until = self._estimate_reset_time(daily=False)
            if "claude" in provider_name and self._is_rate_limit_error(error_str):
                self._anthropic_rate_limited = True
                self._anthropic_rate_limited_until = self._estimate_reset_time(daily=False)
            if "mistral" in provider_name and self._is_rate_limit_error(error_str):
                self._mistral_rate_limited = True
                self._mistral_rate_limited_until = self._estimate_reset_time(daily=False)
            
            # If Groq itself is the primary and hits 429, flag it and try Gemini fallback
            if "groq" in provider_name and ("429" in error_str or "rate_limit_exceeded" in error_str):
                self._groq_rate_limited = True
                self._groq_rate_limited_until = self._estimate_reset_time(daily=True)
                logger.error("❌ Groq TPD 429 while using Groq as primary — flagging as exhausted")
                logger.warning("⚠️ Groq 429 detected, deferring to normal fallback chain")
            
            # Multi-provider fallback chain
            if enable_fallback:
                fallback_chain = self._get_fallback_chain(provider_name)
                for fb_provider, fb_model in fallback_chain:
                    try:
                        logger.warning(f"⚠️ Fallback: {provider_name} failed → {fb_provider}")
                        fb_max_tokens = min(max_tokens, 2500) if "groq" in fb_provider else max_tokens
                        return self.generate_text(
                            provider_name=fb_provider,
                            model_identifier=fb_model,
                            prompt=prompt,
                            system_instruction=system_instruction,
                            temperature=temperature,
                            max_tokens=fb_max_tokens,
                            enable_fallback=False,
                        )
                    except Exception as fallback_error:
                        fb_err = str(fallback_error)
                        if "groq" in fb_provider and self._is_rate_limit_error(fb_err):
                            self._groq_rate_limited = True
                            self._groq_rate_limited_until = self._estimate_reset_time(daily=True)
                        logger.error(f"❌ Fallback failed ({fb_provider}): {fallback_error}")
                raise Exception(
                    f"Tat ca provider deu that bai. Primary: {error_str}. "
                    "Vui long thu lai sau khi quota duoc reset."
                )
            
            raise
            
    def generate_text_from_image(
        self,
        prompt: str,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        system_instruction: Optional[str] = None,
        temperature: float = 0.2
    ) -> str:
        """
        Generate text from an image using Gemini Vision natively.
        Uses round-robin API keys and automatic rate limit handling.
        """
        import base64
        b64_data = base64.b64encode(image_bytes).decode("utf-8")
        
        parts = []
        if system_instruction:
            parts.append({"text": f"SYSTEM: {system_instruction}\n"})
        parts.append({"text": prompt})
        parts.append({
            "inlineData": {
                "mimeType": mime_type,
                "data": b64_data
            }
        })
        
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 8192  # Higher limit for detailed OCR
            },
            # Prevent safety filters from blocking educational/document content
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        }
        
        # Use gemini-2.5-flash for OCR (fast and capable)
        model_identifier = settings.GEMINI_FLASH_MODEL
        keys_to_try = len(getattr(self, 'gemini_api_keys', [1])) or 1
        last_exception = None
        
        img_size_kb = len(image_bytes) / 1024
        logger.info(f"🖼️ Vision OCR: model={model_identifier}, image={img_size_kb:.1f}KB, mime={mime_type}")
        
        for attempt in range(keys_to_try):
            api_key = self._get_available_gemini_key()
            masked_key = f"...{api_key[-4:]}" if api_key else "unknown"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_identifier}:generateContent?key={api_key}"
            
            try:
                with httpx.Client(timeout=300.0) as client:
                    response = client.post(url, json=payload)
                    response.raise_for_status()
                    data = response.json()

                    if "candidates" in data and len(data["candidates"]) > 0:
                        candidate = data["candidates"][0]
                        # Check for safety block (finishReason == "SAFETY")
                        finish_reason = candidate.get("finishReason", "")
                        if finish_reason == "SAFETY":
                            logger.warning(f"⚠️ Vision response blocked by safety filter (key {masked_key})")
                            last_exception = Exception(f"Vision blocked by safety filter: {candidate.get('safetyRatings', '')}")
                            continue

                        text = self._extract_gemini_text(data)
                        if text:
                            logger.info(f"✅ Vision OCR completed with key {masked_key}: {len(text)} chars")
                            return text
                    
                    # No usable text in response
                    logger.warning(f"⚠️ Vision response had no text content: {str(data)[:300]}")
                    last_exception = ValueError(f"Unexpected Vision response: {str(data)[:300]}")
                    continue
                    
            except httpx.HTTPStatusError as e:
                body_preview = response.text[:600] if response.text else ""
                error_msg = f"Gemini Vision API {response.status_code}: {body_preview}"
                if self._is_rate_limit_error(error_msg):
                    logger.warning(f"⚠️ Gemini Key {masked_key} hit rate limit (Vision). Rotating...")
                    if hasattr(self, 'gemini_keys_status'):
                        self.gemini_keys_status[api_key] = self._estimate_reset_time(daily=False)
                    last_exception = Exception(error_msg)
                    continue
                else:
                    logger.error(f"❌ Vision API error (key {masked_key}): {error_msg}")
                    raise Exception(error_msg) from e
            except Exception as e:
                logger.error(f"❌ Vision unexpected error (key {masked_key}): {e}")
                raise e
                
        raise last_exception if last_exception else Exception("All Gemini keys failed for Vision OCR")

    def _get_fallback_chain(self, provider_name: str) -> list[tuple[str, str]]:
        chain: list[tuple[str, str]] = []

        def add(provider: str, model: str, enabled: bool):
            if enabled and provider != provider_name:
                chain.append((provider, model))

        add("gemini-flash", settings.GEMINI_FLASH_MODEL, self._provider_available("gemini"))
        add("mistral", settings.MISTRAL_MODEL, self._provider_available("mistral"))
        add("groq-llama", settings.GROQ_LLAMA_MODEL, self._provider_available("groq"))
        add("openai-gpt", settings.OPENAI_MODEL, self._provider_available("openai"))
        add("claude", settings.ANTHROPIC_MODEL, self._provider_available("claude"))
        return chain

    def _provider_available(self, provider: str) -> bool:
        provider = provider.lower()
        if provider == "gemini":
            return bool(self.gemini_api_key and settings.ENABLE_GEMINI and not self._gemini_rate_limited)
        if provider == "groq":
            return bool(self.groq_client and settings.ENABLE_GROQ and not self._groq_rate_limited)
        if provider == "mistral":
            return bool(self.mistral_api_key and settings.ENABLE_MISTRAL and not self._mistral_rate_limited)
        if provider == "openai":
            return bool(self.openai_api_key and settings.ENABLE_OPENAI and not self._openai_rate_limited)
        if provider in ("anthropic", "claude"):
            return bool(self.anthropic_api_key and settings.ENABLE_ANTHROPIC and not self._anthropic_rate_limited)
        return False

    def _refresh_rate_limit_flags(self):
        now = datetime.now(timezone.utc)

        if self._gemini_rate_limited and self._gemini_rate_limited_until:
            if datetime.fromisoformat(self._gemini_rate_limited_until) <= now:
                self._gemini_rate_limited = False
                self._gemini_rate_limited_until = None

        if self._groq_rate_limited and self._groq_rate_limited_until:
            if datetime.fromisoformat(self._groq_rate_limited_until) <= now:
                self._groq_rate_limited = False
                self._groq_rate_limited_until = None

        if self._openai_rate_limited and self._openai_rate_limited_until:
            if datetime.fromisoformat(self._openai_rate_limited_until) <= now:
                self._openai_rate_limited = False
                self._openai_rate_limited_until = None

        if self._mistral_rate_limited and self._mistral_rate_limited_until:
            if datetime.fromisoformat(self._mistral_rate_limited_until) <= now:
                self._mistral_rate_limited = False
                self._mistral_rate_limited_until = None

        if self._anthropic_rate_limited and self._anthropic_rate_limited_until:
            if datetime.fromisoformat(self._anthropic_rate_limited_until) <= now:
                self._anthropic_rate_limited = False
                self._anthropic_rate_limited_until = None

    def _is_rate_limit_error(self, error_str: str) -> bool:
        s = (error_str or "").lower()
        indicators = [
            "429",
            "rate_limit",
            "rate limit",
            "quota",
            "resource_exhausted",
            "too many requests",
        ]
        return any(k in s for k in indicators)

    def _estimate_reset_time(self, daily: bool = False) -> Optional[str]:
        now = datetime.now(timezone.utc)
        if daily:
            tomorrow = (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return tomorrow.isoformat()
        # Unknown short-window limits: provide conservative estimate.
        return (now + timedelta(minutes=10)).isoformat()

    def get_quota_status(self, error_message: Optional[str] = None) -> dict:
        """Return quota/rate-limit status for UI and API metadata."""
        msg = (error_message or "").lower()

        gemini_limited = self._gemini_rate_limited or (
            "gemini" in msg and self._is_rate_limit_error(msg)
        )
        groq_limited = self._groq_rate_limited or (
            "groq" in msg and self._is_rate_limit_error(msg)
        )

        providers = {
            "gemini": {
                "limited": gemini_limited,
                "reset_at": self._gemini_rate_limited_until,
                "note": "Gemini free tier quota/rate-limit",
            },
            "groq": {
                "limited": groq_limited,
                "reset_at": self._groq_rate_limited_until,
                "note": "Groq daily token quota",
            },
            "openai": {
                "limited": self._openai_rate_limited,
                "reset_at": self._openai_rate_limited_until,
                "note": "OpenAI API rate-limit",
            },
            "claude": {
                "limited": self._anthropic_rate_limited,
                "reset_at": self._anthropic_rate_limited_until,
                "note": "Anthropic API rate-limit",
            },
            "mistral": {
                "limited": self._mistral_rate_limited,
                "reset_at": self._mistral_rate_limited_until,
                "note": "Mistral API rate-limit",
            },
        }

        any_limited = any(p.get("limited") for p in providers.values())

        return {
            "has_quota_issue": bool(any_limited),
            "providers": providers,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    def _get_available_gemini_key(self) -> str:
        if not getattr(self, 'gemini_api_keys', None):
            return self.gemini_api_key
            
        now = datetime.now(timezone.utc)
        for _ in range(len(self.gemini_api_keys)):
            self.current_gemini_key_idx = (self.current_gemini_key_idx + 1) % len(self.gemini_api_keys)
            key = self.gemini_api_keys[self.current_gemini_key_idx]
            
            # Check if this key is rate limited
            limit_until = self.gemini_keys_status.get(key)
            if limit_until and datetime.fromisoformat(limit_until) > now:
                continue
                
            self.gemini_keys_status[key] = None
            return key
                
        # If all keys are rate limited, return next one anyway (will likely throw 429 and trigger global fallback)
        self.current_gemini_key_idx = (self.current_gemini_key_idx + 1) % len(self.gemini_api_keys)
        return self.gemini_api_keys[self.current_gemini_key_idx]

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
        
        payload = {
            "contents": [{
                "parts": [{"text": full_prompt}]
            }],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }
        
        keys_to_try = len(getattr(self, 'gemini_api_keys', [1])) or 1
        last_exception = None
        
        for attempt in range(keys_to_try):
            api_key = self._get_available_gemini_key()
            # v1beta supports all models including gemini-2.5; v1 does not support 2.5 yet
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_identifier}:generateContent?key={api_key}"
            
            try:
                with httpx.Client(timeout=240.0) as client:
                    response = client.post(url, json=payload)
                    response.raise_for_status()
                    data = response.json()

                    text = self._extract_gemini_text(data)
                    if text:
                        return text
                    
                    raise ValueError(f"Unexpected Gemini response format: {data}")
            except httpx.HTTPStatusError as e:
                body_preview = response.text[:600] if response.text else ""
                error_msg = f"Gemini API {response.status_code}: {body_preview}"
                
                if self._is_rate_limit_error(error_msg):
                    masked_key = f"...{api_key[-4:]}" if api_key else "unknown"
                    logger.warning(f"⚠️ Gemini Key {masked_key} hit rate limit. Rotating...")
                    if hasattr(self, 'gemini_keys_status'):
                        self.gemini_keys_status[api_key] = self._estimate_reset_time(daily=False)
                    last_exception = Exception(error_msg)
                    continue # Try the next key
                else:
                    raise Exception(error_msg) from e
            except Exception as e:
                raise e
                
        raise last_exception if last_exception else Exception("All Gemini keys failed")

    def _extract_gemini_text(self, data: dict) -> Optional[str]:
        """
        Extract full text from Gemini response by concatenating all text parts.
        Gemini can return multiple text parts in a single candidate.
        """
        candidates = data.get("candidates") or []
        if not candidates:
            return None

        candidate = candidates[0] or {}
        content = candidate.get("content") or {}
        parts = content.get("parts") or []

        text_parts = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if text:
                text_parts.append(text)

        full_text = "".join(text_parts).strip()
        return full_text or None

    def _generate_openai(
        self,
        model_identifier: str,
        prompt: str,
        system_instruction: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Generate text using OpenAI Chat Completions API."""
        if not self.openai_api_key:
            raise ValueError("OpenAI API key is not configured")

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_identifier,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        with httpx.Client(timeout=240.0) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                body_preview = response.text[:600] if response.text else ""
                raise Exception(f"OpenAI API {response.status_code}: {body_preview}") from e
            data = response.json()

        choices = data.get("choices") or []
        if not choices:
            raise ValueError(f"Unexpected OpenAI response format: {data}")
        message = choices[0].get("message", {})
        content = message.get("content")
        if not content:
            raise ValueError(f"OpenAI response missing content: {data}")
        return content

    def _generate_claude(
        self,
        model_identifier: str,
        prompt: str,
        system_instruction: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Generate text using Anthropic Messages API."""
        if not self.anthropic_api_key:
            raise ValueError("Anthropic API key is not configured")

        headers = {
            "x-api-key": self.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": model_identifier,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_instruction:
            payload["system"] = system_instruction

        with httpx.Client(timeout=240.0) as client:
            response = client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                body_preview = response.text[:600] if response.text else ""
                raise Exception(f"Anthropic API {response.status_code}: {body_preview}") from e
            data = response.json()

        content_blocks = data.get("content") or []
        if not content_blocks:
            raise ValueError(f"Unexpected Anthropic response format: {data}")
        text_parts = [blk.get("text", "") for blk in content_blocks if blk.get("type") == "text"]
        text = "\n".join([p for p in text_parts if p]).strip()
        if not text:
            raise ValueError(f"Anthropic response missing text: {data}")
        return text

    def _generate_mistral(
        self,
        model_identifier: str,
        prompt: str,
        system_instruction: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Generate text using Mistral Chat Completions API."""
        if not self.mistral_api_key:
            raise ValueError("Mistral API key is not configured")

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.mistral_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_identifier,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        with httpx.Client(timeout=240.0) as client:
            response = client.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                body_preview = response.text[:600] if response.text else ""
                raise Exception(f"Mistral API {response.status_code}: {body_preview}") from e
            data = response.json()

        choices = data.get("choices") or []
        if not choices:
            raise ValueError(f"Unexpected Mistral response format: {data}")
        message = choices[0].get("message", {})
        content = message.get("content")
        if not content:
            raise ValueError(f"Mistral response missing content: {data}")
        return content
    
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
        
        # Prevent TPM limit error on Groq Free Tier
        max_tokens = min(max_tokens, 2048)
        
        completion = self.groq_client.chat.completions.create(
            model=model_identifier,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return completion.choices[0].message.content


# Singleton instance
model_manager = ModelManager()
