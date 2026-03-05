"""
Data Analysis Agent
Handles CSV/Excel analysis with pandas code generation and execution
"""
from typing import Dict, Any, List, Optional
import logging
import io
import pandas as pd

from agents import BaseAgent
from agents.code_executor import code_executor
from core.config import settings

logger = logging.getLogger(__name__)


class DataAnalysisAgent(BaseAgent):
    """
    Agent for data analysis tasks
    - Load CSV/Excel files  - Generate pandas code
    - Execute analysis code
    - Create visualizations
    """
    
    def __init__(self):
        super().__init__(
            agent_name="data_analysis_agent",
            description="Analyzes CSV/Excel data with pandas code generation"
        )
    
    async def execute(
        self,
        query: str,
        user_id: str,
        session_id: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute data analysis task
        
        Args:
            query: Analysis request (e.g., "Phân tích doanh thu theo tháng")
            user_id: User ID
            session_id: Session ID
            context: Must contain:
                - file_path: Path to CSV/Excel file
                - file_name: Filename
                - file_data: File bytes (optional)
        
        Returns:
            Dict with analysis results
        """
        try:
            logger.info(f"📊 Data Analysis: {query}")
            
            # Get file from context
            file_path = context.get("file_path")
            file_name = context.get("file_name")
            file_data = context.get("file_data")
            
            if not file_path and not file_data:
                return {
                    "answer": "Không tìm thấy file dữ liệu. Vui lòng upload file CSV/Excel.",
                    "metadata": {"error": "no_file"}
                }
            
            # Analyze file and generate code
            analysis_result = await self._analyze_data(
                query, file_path, file_name, file_data, user_id, session_id
            )
            
            # Save state
            self.save_state(user_id, session_id, {
                "last_analysis": query,
                "last_file": file_name,
                "last_code": analysis_result.get("code", "")
            })
            
            # Set context for next interaction
            self.memory.set_context(user_id, session_id, "last_action", "data_analysis")
            self.memory.set_context(user_id, session_id, "last_file", file_name)
            
            return analysis_result
        
        except Exception as e:
            logger.error(f"❌ Data analysis error: {e}")
            return {
                "answer": f"Lỗi khi phân tích dữ liệu: {e}",
                "metadata": {"error": str(e)}
            }
    
    async def _analyze_data(
        self,
        query: str,
        file_path: Optional[str],
        file_name: str,
        file_data: Optional[bytes],
        user_id: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Analyze data file
        
        Steps:
            1. Load file (CSV/Excel)
            2. Understand data structure
            3. Generate pandas code for analysis
            4. Execute code
            5. Format results
        """
        try:
            # Step 1: Load file
            logger.info(f"📂 Loading file: {file_name}")
            df, file_bytes = await self._load_file(file_path, file_name, file_data)
            
            if df is None:
                return {
                    "answer": f"Không thể đọc file {file_name}. Vui lòng kiểm tra định dạng.",
                    "metadata": {"error": "file_read_error"}
                }
            
            # Step 2: Understand structure
            data_info = self._get_data_info(df)
            logger.info(f"📋 Data info: {data_info['shape']} | Columns: {len(data_info['columns'])}")
            
            # Step 3: Generate analysis code
            logger.info(f"🔧 Generating analysis code for: {query}")
            code = await self._generate_analysis_code(query, data_info)
            
            if not code:
                return {
                    "answer": "Không thể tạo code phân tích cho yêu cầu này.",
                    "metadata": {"error": "code_generation_failed"}
                }
            
            logger.info(f"✅ Generated code:\n{code}")
            
            # Step 4: Execute code
            logger.info("⚙️ Executing analysis code...")
            result = code_executor.execute_pandas_code(
                code=code,
                csv_file=file_bytes,
                filename=file_name
            )
            
            if not result["success"]:
                return {
                    "answer": f"Lỗi khi thực thi code:\n```\n{result['error']}\n```\n\nCode đã tạo:\n```python\n{code}\n```",
                    "metadata": {
                        "error": "execution_failed",
                        "code": code,
                        "error_detail": result["error"]
                    }
                }
            
            # Step 5: Format results
            output = result["output"]
            execution_time = result["execution_time"]
            
            answer = f"""📊 **Kết quả phân tích**

**File:** `{file_name}`
**Câu hỏi:** {query}

**Kết quả:**
```
{output}
```

**Code đã sử dụng:**
```python
{code}
```

**Thời gian thực thi:** {execution_time:.2f}s

---
💡 **Bạn có muốn tôi:**
- Tạo biểu đồ minh họa?
- Phân tích chi tiết hơn?
- Export kết quả ra file?
"""
            
            return {
                "answer": answer,
                "metadata": {
                    "data_info": data_info,
                    "code": code,
                    "output": output,
                    "execution_time": execution_time
                },
                "next_action": "suggest_chart"
            }
        
        except Exception as e:
            logger.error(f"❌ Analysis error: {e}")
            return {
                "answer": f"Lỗi phân tích: {e}",
                "metadata": {"error": str(e)}
            }
    
    async def _load_file(
        self,
        file_path: Optional[str],
        file_name: str,
        file_data: Optional[bytes]
    ) -> tuple[Optional[pd.DataFrame], Optional[bytes]]:
        """
        Load CSV/Excel file
        
        Returns:
            (DataFrame, file_bytes)
        """
        try:
            # Determine file type
            file_ext = file_name.lower().split('.')[-1]
            
            # Load from file_data if provided
            if file_data:
                if file_ext == 'csv':
                    df = pd.read_csv(io.BytesIO(file_data))
                elif file_ext in ['xlsx', 'xls']:
                    df = pd.read_excel(io.BytesIO(file_data))
                else:
                    return None, None
                
                return df, file_data
            
            # Load from file_path
            if file_path:
                if file_ext == 'csv':
                    df = pd.read_csv(file_path)
                elif file_ext in ['xlsx', 'xls']:
                    df = pd.read_excel(file_path)
                else:
                    return None, None
                
                # Read file bytes
                with open(file_path, 'rb') as f:
                    file_bytes = f.read()
                
                return df, file_bytes
            
            return None, None
        
        except Exception as e:
            logger.error(f"❌ File load error: {e}")
            return None, None
    
    def _get_data_info(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Get DataFrame information
        
        Returns:
            Dict with shape, columns, dtypes, sample
        """
        try:
            return {
                "shape": df.shape,
                "columns": df.columns.tolist(),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "sample": df.head(3).to_dict(orient='records'),
                "null_counts": df.isnull().sum().to_dict(),
                "numeric_columns": df.select_dtypes(include=['number']).columns.tolist(),
                "categorical_columns": df.select_dtypes(include=['object']).columns.tolist()
            }
        except Exception as e:
            logger.error(f"❌ Data info error: {e}")
            return {}
    
    async def _generate_analysis_code(
        self,
        query: str,
        data_info: Dict[str, Any]
    ) -> Optional[str]:
        """
        Generate pandas code for analysis using LLM
        
        Args:
            query: User's analysis request
            data_info: Data structure info
        
        Returns:
            Python code string
        """
        try:
            # Build prompt for LLM
            system_instruction = """Bạn là chuyên gia phân tích dữ liệu với pandas.

NHIỆM VỤ:
Tạo code Python để phân tích dữ liệu theo yêu cầu.

YÊU CẦU:
- Dùng pandas (đã import sẵn: import pandas as pd)
- DataFrame đã được load sẵn vào biến `df`
- Code phải ngắn gọn, hiệu quả
- In kết quả ra stdout (dùng print())
- KHÔNG tạo biểu đồ trừ khi được yêu cầu rõ ràng
- Xử lý lỗi cơ bản (null values, etc.)

ĐỊNH DẠNG OUTPUT:
Chỉ trả về code Python, KHÔNG giải thích.

VÍ DỤ:
Yêu cầu: "Tính tổng doanh thu theo tháng"
Code:
```python
# Giả sử có cột 'month' và 'revenue'
monthly_revenue = df.groupby('month')['revenue'].sum()
print(monthly_revenue)
```
"""
            
            user_prompt = f"""THÔNG TIN DỮ LIỆU:
- Shape: {data_info['shape']}
- Columns: {', '.join(data_info['columns'])}
- Numeric columns: {', '.join(data_info['numeric_columns'])}
- Categorical columns: {', '.join(data_info['categorical_columns'])}

Sample data (first 3 rows):
{data_info['sample']}

YÊU CẦU PHÂN TÍCH:
{query}

CODE PYTHON:
```python
"""
            
            # Generate code with LLM
            provider_name, model_identifier = self.model_manager.get_model(
                task_type="code_help",
                complexity="medium"
            )
            
            response = self.model_manager.generate_text(
                provider_name=provider_name,
                model_identifier=model_identifier,
                prompt=user_prompt,
                system_instruction=system_instruction,
                temperature=0.3,  # Low temperature for code
                max_tokens=2000
            )
            
            # Extract code from response
            code = self._extract_code(response)
            
            return code
        
        except Exception as e:
            logger.error(f"❌ Code generation error: {e}")
            return None
    
    def _extract_code(self, response: str) -> str:
        """
        Extract Python code from LLM response
        
        Handles:
            - ```python ... ```
            - ``` ... ```
            - Plain code
        """
        # Remove markdown code blocks
        if "```python" in response:
            start = response.find("```python") + len("```python")
            end = response.find("```", start)
            code = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + len("```")
            end = response.find("```", start)
            code = response[start:end].strip()
        else:
            code = response.strip()
        
        return code


# Global singleton
data_analysis_agent = DataAnalysisAgent()
