import json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from groq import Groq
from src.config import GROQ_API_KEY, GROQ_MODEL
from src.security import get_current_user
from src.db import get_connection
from src.rag import retrieve_chunks
from src.models import ChatQueryRequest, ChatSessionResponse

router = APIRouter(prefix="/api/chat", tags=["AI Chatbot & RAG"])
groq_client = Groq(api_key=GROQ_API_KEY)

@router.post("/query")
def chat_with_notes(
    req: ChatQueryRequest,
    current_user: dict = Depends(get_current_user)
):
    clean_code = req.course_code.strip().upper()

    # Ensure course exists
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT code FROM courses WHERE code = %s;", (clean_code,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Subject not found")

    session_id = req.session_id

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Resolve or Create Chat Session
            if not session_id:
                title_preview = (req.query[:40] + "..") if len(req.query) > 40 else req.query
                cur.execute(
                    """
                    INSERT INTO chat_sessions (user_id, course_code, title)
                    VALUES (%s, %s, %s)
                    RETURNING id;
                    """,
                    (current_user["id"], clean_code, title_preview)
                )
                session_id = cur.fetchone()[0]

            # 2. Fetch last 6 messages
            cur.execute(
                """
                SELECT role, content FROM chat_messages 
                WHERE session_id = %s 
                ORDER BY created_at ASC 
                LIMIT 6;
                """,
                (session_id,)
            )
            chat_history = [{"role": r[0], "content": r[1]} for r in cur.fetchall()]

    # 3. Vector Retrieval (Filtered by course_id)
    top_k = 10 if req.mode == "generate_exam" else 8
    retrieved = retrieve_chunks(req.query, course_id=clean_code, top_k=top_k)

    sources = [
        {
            "filename": c["filename"],
            "page_number": c["page_number"],
            "doc_type": c["doc_type"],
            "score": c["score"]
        }
        for c in retrieved
    ]

    # 4. Construct Context
    context_blocks = [
        f"[{c['doc_type'].upper()} Source: {c['filename']} (Page {c['page_number']})]\n{c['content']}"
        for c in retrieved
    ]
    context_text = "\n\n".join(context_blocks)

    if req.mode == "generate_exam":
        system_prompt = (
            "You are an academic examination designer. Using the course notes and sample questions "
            "provided in the context, synthesize a well-balanced sample examination paper.\n"
            "Requirements:\n"
            "- Allocate explicit marks for every question.\n"
            "- Divide the paper into logical sections (e.g., Short Concept Questions, Detailed Analytical Problems).\n"
            "- Formulate realistic questions strictly based on the provided material."
        )
    else:
        system_prompt = (
            "You are an academic teaching assistant. Answer the student's question by combining "
            "the provided course context with the recent chat history.\n"
            "Rules:\n"
            "- Use the retrieved context as the primary source of truth.\n"
            "- If the student is asking a follow-up question, use earlier conversation turns for continuity.\n"
            "- If neither the context nor the chat history provides the relevant material, state: "
            "'I cannot find this information in the uploaded notes.'\n"
            "- Cite source documents and page numbers where applicable."
        )

    # 5. Groq Inference
    groq_messages = [{"role": "system", "content": f"{system_prompt}\n\nContext:\n{context_text}"}]
    groq_messages.extend(chat_history)
    groq_messages.append({"role": "user", "content": req.query})

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=groq_messages,
        temperature=0.2 if req.mode == "generate_exam" else 0.1
    )
    answer = response.choices[0].message.content

    # 6. Persist Messages
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_messages (session_id, role, content, sources)
                VALUES (%s, 'user', %s, '[]'::jsonb);
                """,
                (session_id, req.query)
            )
            cur.execute(
                """
                INSERT INTO chat_messages (session_id, role, content, sources)
                VALUES (%s, 'assistant', %s, %s::jsonb);
                """,
                (session_id, answer, json.dumps(sources))
            )

    return {
        "session_id": session_id,
        "answer": answer,
        "sources": sources
    }

@router.get("/sessions/{course_code}", response_model=list[ChatSessionResponse])
def get_user_sessions(
    course_code: str,
    current_user: dict = Depends(get_current_user)
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, course_code, title, created_at 
                FROM chat_sessions 
                WHERE user_id = %s AND course_code = %s 
                ORDER BY created_at DESC;
                """,
                (current_user["id"], course_code.upper())
            )
            rows = cur.fetchall()

    return [
        {"id": r[0], "course_code": r[1], "title": r[2], "created_at": r[3]}
        for r in rows
    ]

@router.get("/history/{session_id}")
def get_session_history(
    session_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM chat_sessions WHERE id = %s;", (session_id,))
            session = cur.fetchone()
            if not session or str(session[0]) != str(current_user["id"]):
                raise HTTPException(status_code=404, detail="Session not found")

            cur.execute(
                """
                SELECT role, content, sources, created_at 
                FROM chat_messages 
                WHERE session_id = %s 
                ORDER BY created_at ASC;
                """,
                (session_id,)
            )
            messages = [
                {
                    "role": r[0],
                    "content": r[1],
                    "sources": r[2] if r[2] else [],
                    "created_at": r[3]
                }
                for r in cur.fetchall()
            ]

    return {"session_id": session_id, "messages": messages}