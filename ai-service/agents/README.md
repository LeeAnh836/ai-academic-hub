# AI Agents - Multi-Agent System

This folder contains specialized AI agents for different tasks.

## 🤖 Agents

### Base Agent (`__init__.py`)
Abstract base class for all agents
- Provides common functionality
- Memory management
- State persistence
- Logging

### Prompt Preprocessor (`prompt_preprocessor.py`)
Resolves ambiguous queries using conversation memory

**Examples:**
- "có" → "Có, tôi muốn phân tích dữ liệu"
- "được" → "Được, hãy tạo biểu đồ"
- "ok" → "OK, thực hiện phân tích"

**Features:**
- Detects ambiguous keywords
- Looks up conversation history
- Enriches query with context

### Document QA Agent (`document_qa_agent.py`)
Handles document-based Q&A using RAG

**Capabilities:**
- Semantic search in Qdrant
- Context retrieval
- Answer generation with sources
- Fallback retrieval strategy

**Use Cases:**
- "Theo tài liệu, Docker là gì?"
- "Tóm tắt file PDF này"
- "Tạo câu hỏi từ tài liệu"

### Data Analysis Agent (`data_analysis_agent.py`)
Analyzes CSV/Excel files with pandas code generation

**Workflow:**
1. Load data file
2. Understand structure
3. Generate pandas code with LLM
4. Execute code in Docker
5. Return results + code

**Use Cases:**
- "Phân tích doanh thu theo tháng"
- "Tính trung bình của cột revenue"
- "Tạo biểu đồ từ dữ liệu"

### General QA Agent (`general_qa_agent.py`)
General question answering with tool support

**Capabilities:**
- Direct LLM responses
- Tool integration (calculator, web search, weather)
- MCP protocol support (future)

**Use Cases:**
- "Giải phương trình x^2 + 2x + 1 = 0"
- "Viết code Python sắp xếp mảng"
- "Giải thích khái niệm OOP"

### Code Executor (`code_executor.py`)
Safe Python code execution in Docker containers

**Features:**
- Isolated execution environment
- Memory limit (512MB)
- Network disabled
- Timeout protection
- Output size limit

**Security:**
- No network access
- Resource limits
- Container auto-removal

## 🔄 Agent Workflow

```
User Query
    ↓
[Prompt Preprocessor]
    ↓ (enriched query)
[Intent Classifier]
    ↓ (intent)
[Master Orchestrator]
    ↓ (routes to agent)
[Specialized Agent]
    ↓ (executes task)
[Memory Manager]
    ↑ (saves context)
Response
```

## 🧠 Memory Integration

All agents have access to Memory Manager:
- Save/load agent state
- Access conversation history
- Store/retrieve context variables

**Example:**
```python
# In any agent
self.save_state(user_id, session_id, {
    "last_action": "data_analysis",
    "last_file": "sales.csv"
})

state = self.load_state(user_id, session_id)
```

## 🎯 Adding New Agent

1. Create new file: `agents/my_agent.py`
2. Inherit from BaseAgent:
```python
from agents import BaseAgent

class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="my_agent",
            description="Agent description"
        )
    
    async def execute(self, query, user_id, session_id, context):
        # Agent logic here
        return {
            "answer": "...",
            "metadata": {}
        }
```

3. Register in Master Orchestrator:
```python
self.agents = {
    "my_agent": my_agent,
    ...
}
```

4. Add intent in Intent Classifier:
```python
INTENTS = {
    "my_intent": {
        "keywords": [...],
        ...
    }
}
```

5. Add routing logic in Orchestrator:
```python
if intent == "my_intent":
    result = await my_agent.execute(...)
```

## 📚 Learn More

- See `MULTI_AGENT_SETUP.md` for full setup guide
- See `services/master_orchestrator.py` for orchestration logic
- See `routers/agent.py` for API endpoints
