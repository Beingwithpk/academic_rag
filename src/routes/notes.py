import os
import shutil
from uuid import UUID
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from fastapi.responses import FileResponse
from src.security import get_current_user, require_role
from src.db import get_connection
from src.ingest import ingest_pdf
from src.models import DocumentResponse

router = APIRouter(prefix="/api/notes", tags=["Notes & Materials"])

UPLOAD_DIR = os.path.join(os.getcwd(), "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload", response_model=dict, status_code=status.HTTP_201_CREATED)
def upload_note(
    course_code: str = Form(...),
    doc_type: str = Form("notes"),  # 'notes', 'pyq', 'syllabus', 'assignment'
    file: UploadFile = File(...),
    current_user: dict = Depends(require_role("faculty", "admin"))
):
    clean_code = course_code.strip().upper()

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF documents are supported."
        )

    # Check course exists
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT code FROM courses WHERE code = %s;", (clean_code,))
            if not cur.fetchone():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course does not exist")

    saved_file_name = f"{clean_code}_{file.filename}"
    saved_file_path = os.path.join(UPLOAD_DIR, saved_file_name)
    with open(saved_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        result = ingest_pdf(
            file_path=saved_file_path,
            course_id=clean_code,
            doc_type=doc_type,
            uploaded_by=str(current_user["id"])
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        if os.path.exists(saved_file_path):
            try:
                os.remove(saved_file_path)
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(e)}"
        )

    return {
        "message": f"Successfully uploaded and indexed '{file.filename}'",
        "data": result
    }

@router.get("/course/{course_code}", response_model=list[DocumentResponse])
def list_course_documents(
    course_code: str,
    current_user: dict = Depends(get_current_user)
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, filename, course_id, doc_type, created_at 
                FROM documents 
                WHERE course_id = %s 
                ORDER BY created_at DESC;
                """,
                (course_code.upper(),)
            )
            rows = cur.fetchall()

    return [
        {
            "id": r[0],
            "filename": r[1],
            "course_id": r[2],
            "doc_type": r[3],
            "created_at": r[4]
        }
        for r in rows
    ]

@router.get("/view/{document_id}")
def view_document(document_id: UUID, current_user: dict = Depends(get_current_user)):
    """Opens the PDF directly inside browser."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT filename, course_id FROM documents WHERE id = %s;", (document_id,))
            doc = cur.fetchone()
            if not doc:
                raise HTTPException(status_code=404, detail="Document not found")
            filename, course_id = doc

    file_path = os.path.join(UPLOAD_DIR, f"{course_id}_{filename}")
    if not os.path.exists(file_path):
        # Fallback to pure filename
        file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File content missing from server storage.")

    return FileResponse(file_path, media_type="application/pdf", filename=filename)

@router.get("/download/{document_id}")
def download_document(document_id: UUID, current_user: dict = Depends(get_current_user)):
    """Triggers direct attachment download."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT filename, course_id FROM documents WHERE id = %s;", (document_id,))
            doc = cur.fetchone()
            if not doc:
                raise HTTPException(status_code=404, detail="Document not found")
            filename, course_id = doc

    file_path = os.path.join(UPLOAD_DIR, f"{course_id}_{filename}")
    if not os.path.exists(file_path):
        file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File content missing from server storage.")

    return FileResponse(file_path, media_type="application/octet-stream", filename=filename)