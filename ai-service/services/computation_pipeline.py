"""
Computation Pipeline
RAG -> Extract data -> Execute tool -> Explain
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import json
import logging
import re

from core.model_manager import model_manager
from agents.code_executor import code_executor
from services.query_complexity_analyzer import complexity_analyzer

logger = logging.getLogger(__name__)


class ComputationPipeline:
    """
    Pipeline to extract structured data and formulas, run Python computation,
    and generate a grounded explanation.
    """

    def __init__(self) -> None:
        self.model_manager = model_manager

    def run(
        self,
        query: str,
        contexts: Optional[List[Dict[str, Any]]] = None,
        intent: str = "computation",
        chat_history: Optional[List[Dict[str, Any]]] = None,
        source_metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        context_str = self._build_context_str(contexts)
        plan = self._extract_plan(query, context_str, intent)
        if not plan:
            answer = (
                "Không thể trích xuất dữ liệu/công thức từ nội dung hiện có. "
                "Vui lòng cung cấp thêm dữ liệu hoặc ảnh rõ hơn."
            )
            return {
                "answer": answer,
                "metadata": {
                    "pipeline": "computation",
                    "error": "plan_extraction_failed",
                },
            }

        python_code = (plan.get("python_code") or "").strip()
        tool_result = None
        if python_code:
            tool_result = self._execute_code(python_code)
        else:
            tool_result = {
                "success": False,
                "output": "",
                "error": "missing_python_code",
                "execution_time": 0,
            }

        explanation = self._generate_explanation(
            query=query,
            context_str=context_str,
            plan=plan,
            tool_result=tool_result,
            intent=intent,
            chat_history=chat_history,
            source_metadata=source_metadata,
        )

        include_code = self._should_include_code_in_answer(query=query)
        answer = self._format_answer(
            plan=plan,
            tool_result=tool_result,
            explanation=explanation,
            python_code=python_code,
            intent=intent,
            include_code=include_code,
        )

        return {
            "answer": answer,
            "metadata": {
                "pipeline": "computation",
                "plan": plan,
                "code": python_code,
                "include_code": include_code,
                "tool_result": tool_result,
            },
        }

    def _build_context_str(self, contexts: Optional[List[Dict[str, Any]]]) -> str:
        if not contexts:
            return ""

        parts: List[str] = []
        max_chars = 8000
        current = 0
        for ctx in contexts:
            label = ctx.get("file_name") or ctx.get("title") or "document"
            chunk = ctx.get("chunk_text", "")
            if not chunk:
                continue
            entry = f"[{label}]\n{chunk}"
            if current + len(entry) > max_chars:
                break
            parts.append(entry)
            current += len(entry)
        return "\n\n".join(parts)

    def _extract_plan(self, query: str, context_str: str, intent: str) -> Optional[Dict[str, Any]]:
        system_prompt = (
            "Bạn là chuyên gia trích xuất dữ liệu và lập kế hoạch tính toán.\n"
            "Nhiệm vụ: từ câu hỏi và tài liệu (nếu có), trích xuất số liệu, biến, "
            "công thức cần dùng, và viết mã Python để tính kết quả.\n\n"
            "YÊU CẦU BẮT BUỘC:\n"
            "- Chỉ dùng số liệu có trong câu hỏi hoặc tài liệu.\n"
            "- Không suy đoán. Nếu thiếu dữ liệu, liệt kê ở 'missing'.\n"
            "- Mã Python chỉ dùng thư viện chuẩn (math, statistics).\n"
            "- Mã phải in ra kết quả rõ ràng bằng print().\n"
            "- Trả về JSON thuần theo schema bên dưới.\n\n"
            "SCHEMA JSON:\n"
            "{\n"
            "  \"task_type\": \"computation|analysis\",\n"
            "  \"variables\": [{\"name\": \"\", \"value\": \"\", \"unit\": \"\", \"source\": \"\"}],\n"
            "  \"formulas\": [\"\"],\n"
            "  \"assumptions\": [\"\"],\n"
            "  \"missing\": [\"\"],\n"
            "  \"expected_outputs\": [\"\"],\n"
            "  \"python_code\": \"\"\n"
            "}"
        )

        context_block = context_str if context_str else "(KHONG CO TAI LIEU)"
        user_prompt = (
            f"CÂU HỎI:\n{query}\n\n"
            f"TÀI LIỆU:\n{context_block}\n\n"
            f"INTENT: {intent}\n\n"
            "JSON KẾT QUẢ:"  # Force JSON only
        )

        try:
            provider, model = self.model_manager.get_model("entity_extraction", "low")
            response = self.model_manager.generate_text(
                provider_name=provider,
                model_identifier=model,
                prompt=user_prompt,
                system_instruction=system_prompt,
                temperature=0.1,
                max_tokens=1200,
            )
            plan = self._extract_json(response)
            if not plan:
                logger.warning("⚠️ Plan extraction returned no JSON")
                return None
            plan.setdefault("task_type", intent)
            plan.setdefault("variables", [])
            plan.setdefault("formulas", [])
            plan.setdefault("assumptions", [])
            plan.setdefault("missing", [])
            plan.setdefault("expected_outputs", [])
            plan.setdefault("python_code", "")
            return plan
        except Exception as e:
            logger.warning(f"⚠️ Plan extraction failed: {e}")
            return None

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None

        cleaned = text.strip()
        if "```" in cleaned:
            parts = cleaned.split("```")
            for part in parts:
                if "{" in part and "}" in part:
                    cleaned = part
                    break

        cleaned = cleaned.replace("json", "", 1).strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None

        candidate = cleaned[start : end + 1]
        candidate = re.sub(r"\s+$", "", candidate)

        try:
            return json.loads(candidate)
        except Exception:
            return None

    def _execute_code(self, code: str) -> Dict[str, Any]:
        if not code_executor.enabled:
            return {
                "success": False,
                "output": "",
                "error": "code_executor_disabled",
                "execution_time": 0,
            }

        safe_code = code.strip()
        if not safe_code:
            return {
                "success": False,
                "output": "",
                "error": "empty_code",
                "execution_time": 0,
            }

        return code_executor.execute_code(code=safe_code)

    def _generate_explanation(
        self,
        query: str,
        context_str: str,
        plan: Dict[str, Any],
        tool_result: Dict[str, Any],
        intent: str,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        source_metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        complexity = complexity_analyzer.analyze(query)
        model_complexity = {
            "simple": "low",
            "moderate": "medium",
            "complex": "high",
        }.get(complexity, "medium")

        task_type = "rag_query" if context_str else "direct_chat"
        provider, model = self.model_manager.get_model(task_type, model_complexity)

        history_hint = ""
        if chat_history:
            recent = chat_history[-6:]
            history_hint = "\n".join(
                f"{msg.get('role', '').upper()}: {msg.get('content', '')}"
                for msg in recent
            )

        source_hint = ""
        if source_metadata:
            names = [
                (src.get("file_name") or src.get("source_id") or "unknown")
                for src in source_metadata[:3]
            ]
            source_hint = f"Nguồn đính kèm: {', '.join(names)}"

        system_prompt = (
            "Bạn là trợ lý phân tích.\n"
            "Hãy giải thích kết quả dựa trên dữ liệu trích xuất và kết quả tool.\n\n"
            "YÊU CẦU:\n"
            "- Dùng dữ liệu/công thức đã trích xuất.\n"
            "- Nếu thiếu dữ liệu hoặc tool lỗi, nêu rõ phần thiếu.\n"
            "- Trình bày ngắn gọn, có bước thế số nếu là computation.\n"
            "- Nếu là analysis, nêu nhận xét và ý nghĩa thống kê.\n"
            "- Nếu có tài liệu, nhắc tên file khi trích dẫn."
        )

        user_prompt = (
            f"CÂU HỎI:\n{query}\n\n"
            f"TÀI LIỆU:\n{context_str or '(KHONG CO)'}\n\n"
            f"DỮ LIỆU TRÍCH XUẤT (JSON):\n{json.dumps(plan, ensure_ascii=False)}\n\n"
            f"KẾT QUẢ TOOL:\n{tool_result}\n\n"
            f"LỊCH SỬ NGẮN:\n{history_hint}\n\n"
            f"{source_hint}\n\n"
            "GIẢI THÍCH:"  # LLM explanation
        )

        try:
            return self.model_manager.generate_text(
                provider_name=provider,
                model_identifier=model,
                prompt=user_prompt,
                system_instruction=system_prompt,
                temperature=0.3,
                max_tokens=2000,
            )
        except Exception as e:
            logger.warning(f"⚠️ Explanation generation failed: {e}")
            return "Không thể tạo phần giải thích tự động."

    def _format_answer(
        self,
        plan: Dict[str, Any],
        tool_result: Dict[str, Any],
        explanation: str,
        python_code: str,
        intent: str,
        include_code: bool = False,
    ) -> str:
        parts: List[str] = []

        # Results
        result_output = tool_result.get("output", "") if tool_result else ""
        if tool_result.get("success") and result_output:
            parts.append("### Kết quả tính toán\n" + "```\n" + result_output.strip() + "\n```")
        elif tool_result.get("success"):
            parts.append("### Kết quả tính toán\n(Đã chạy tool nhưng không có output hiển thị.)")
        else:
            err = tool_result.get("error", "")
            if plan.get("missing"):
                missing = "\n".join(f"- {item}" for item in plan.get("missing", []) if item)
                parts.append("### Thiếu dữ liệu\n" + (missing or "- Thiếu dữ liệu cần thiết"))
            if err:
                parts.append("### Lỗi tool\n```\n" + str(err) + "\n```")

        # Extracted variables
        variables = plan.get("variables") or []
        if variables:
            lines = []
            for var in variables:
                name = var.get("name", "")
                value = var.get("value", "")
                unit = var.get("unit", "")
                source = var.get("source", "")
                line = f"- {name} = {value} {unit}".strip()
                if source:
                    line += f" (nguon: {source})"
                lines.append(line)
            parts.append("### Dữ liệu trích xuất\n" + "\n".join(lines))

        # Formulas
        formulas = plan.get("formulas") or []
        if formulas:
            parts.append("### Công thức sử dụng\n" + "\n".join(f"- {f}" for f in formulas if f))

        # Explanation
        if explanation:
            parts.append("### Giải thích\n" + explanation.strip())

        # Code
        # Only show code when the user explicitly asks for code/script,
        # to avoid "random code" in informational math questions.
        if include_code and python_code and tool_result.get("error") != "code_executor_disabled":
            parts.append("### Code đã chạy\n```python\n" + python_code.strip() + "\n```")

        return "\n\n".join(parts)

    def _should_include_code_in_answer(self, query: str) -> bool:
        q = (query or "").lower()
        if not q.strip():
            return False
        code_markers = [
            "code", "mã", "mã nguồn", "script", "python", "pandas",
            "viết code", "viết mã", "generate code", "source code",
            "cho tôi code", "đưa code", "đoạn code",
        ]
        return any(m in q for m in code_markers)


computation_pipeline = ComputationPipeline()
