"""
Example: Cách tích hợp AI Service vào Chat Flow

File này minh họa cách sử dụng AI Service trong chat endpoints
"""
import asyncio
from typing import List, Dict
from uuid import UUID
from fastapi import HTTPException

from services.ai_service import ai_service
from services.chat_service import chat_service
from sqlalchemy.orm import Session


# ============================================
# Example 1: RAG Query với Document Context
# ============================================
async def handle_rag_query(
    question: str,
    user_id: str,
    document_ids: List[str],
    db: Session
) -> Dict:
    """
    Xử lý câu hỏi RAG với document context
    
    Flow:
    1. User gửi câu hỏi
    2. Backend forward đến AI Service
    3. AI Service search Qdrant + generate answer
    4. Backend lưu message vào DB
    5. Return response
    """
    try:
        # Call AI Service RAG endpoint
        rag_response = await ai_service.query_rag(
            question=question,
            user_id=user_id,
            document_ids=document_ids,
            top_k=5,
            score_threshold=0.7
        )
        
        return {
            "answer": rag_response["answer"],
            "contexts": rag_response["contexts"],
            "model": rag_response["model"],
            "processing_time": rag_response["processing_time"]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG query failed: {e}")


# ============================================
# Example 2: Chat với Context từ Session
# ============================================
async def handle_chat_message(
    session_id: UUID,
    user_id: str,
    message: str,
    db: Session
) -> Dict:
    """
    Xử lý chat message trong session
    
    Flow:
    1. Lấy chat history từ DB
    2. Lấy document IDs từ session context
    3. Call AI Service chat endpoint
    4. Lưu user message và AI response vào DB
    5. Return response
    """
    try:
        # 1. Lấy session và check quyền
        session = chat_service.get_chat_session_by_id(
            session_id=session_id,
            user_id=user_id,
            db=db
        )
        
        # 2. Lấy chat history (cho context)
        messages = chat_service.get_session_messages(
            session_id=session_id,
            user_id=user_id,
            db=db,
            limit=10  # Last 10 messages for context
        )
        
        # 3. Format messages cho AI Service
        chat_history = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        chat_history.append({"role": "user", "content": message})
        
        # 4. Call AI Service
        ai_response = await ai_service.chat_with_ai(
            messages=chat_history,
            user_id=user_id,
            document_ids=session.context_documents,
            temperature=0.7,
            max_tokens=2000
        )
        
        # 5. Lưu user message vào DB
        user_message = chat_service.create_chat_message(
            session_id=session_id,
            user_id=user_id,
            content=message,
            retrieved_chunks=ai_response.get("contexts", []),
            db=db
        )
        
        # 6. Lưu AI response vào DB
        ai_message = chat_service.create_chat_message(
            session_id=session_id,
            user_id=user_id,
            content=ai_response["message"],
            retrieved_chunks=ai_response.get("contexts", []),
            db=db
        )
        
        return {
            "user_message_id": str(user_message.id),
            "ai_message_id": str(ai_message.id),
            "answer": ai_response["message"],
            "contexts": ai_response.get("contexts"),
            "model": ai_response["model"]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {e}")


# ============================================
# Example 3: Simple RAG Query (Không lưu DB)
# ============================================
async def simple_rag_query(
    question: str,
    user_id: str,
    document_ids: List[str] = None
) -> Dict:
    """
    RAG query đơn giản, không lưu vào DB
    Dùng cho quick questions
    """
    try:
        response = await ai_service.query_rag(
            question=question,
            user_id=user_id,
            document_ids=document_ids,
            top_k=3,
            score_threshold=0.75
        )
        
        return {
            "answer": response["answer"],
            "sources": [
                {
                    "file_name": ctx["file_name"],
                    "chunk_text": ctx["chunk_text"][:200] + "...",  # Preview
                    "score": ctx["score"]
                }
                for ctx in response["contexts"]
            ]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Example 4: Batch Embedding Generation
# ============================================
async def generate_text_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings cho nhiều texts
    Dùng cho semantic search, similarity comparison
    """
    try:
        embeddings = await ai_service.generate_embeddings(
            texts=texts,
            input_type="search_document"
        )
        return embeddings
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {e}")


# ============================================
# Example 5: Document Processing Hook
# ============================================
def on_document_uploaded(document_id: UUID, db: Session):
    """
    Hook được gọi sau khi user upload document
    Trigger background processing qua AI Service
    """
    try:
        # Process document sẽ tự động gọi AI Service
        # AI Service sẽ: load -> split -> embed -> Qdrant
        ai_service.process_document(document_id, db)
        
    except Exception as e:
        print(f"Document processing failed: {e}")
        # Update document status to failed in DB


# ============================================
# Example 6: Usage trong API Router
# ============================================
"""
# Trong backend/api/chat.py

from examples.ai_integration import handle_chat_message

@router.post("/messages", response_model=ChatMessageResponse)
async def send_chat_message(
    request: ChatMessageCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    result = await handle_chat_message(
        session_id=request.session_id,
        user_id=str(current_user.id),
        message=request.message,
        db=db
    )
    
    return result
"""


# ============================================
# Example 7: Error Handling
# ============================================
async def safe_rag_query(question: str, user_id: str) -> Dict:
    """
    RAG query với error handling
    """
    try:
        response = await ai_service.query_rag(
            question=question,
            user_id=user_id
        )
        return response
    
    except HTTPException as e:
        # AI Service returned HTTP error
        return {
            "answer": "Xin lỗi, tôi gặp lỗi khi xử lý câu hỏi của bạn.",
            "error": str(e.detail),
            "contexts": []
        }
    
    except Exception as e:
        # Network error, timeout, etc.
        return {
            "answer": "Xin lỗi, AI Service hiện không khả dụng.",
            "error": str(e),
            "contexts": []
        }


# ============================================
# Example 8: Streaming Response (Future)
# ============================================
"""
async def stream_chat_response(
    question: str,
    user_id: str,
    document_ids: List[str]
):
    '''
    Stream response từ LLM (implement sau)
    '''
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{ai_service.ai_service_url}/api/rag/chat",
            json={
                "messages": [{"role": "user", "content": question}],
                "user_id": user_id,
                "document_ids": document_ids,
                "stream": True
            }
        ) as response:
            async for chunk in response.aiter_text():
                yield chunk
"""
