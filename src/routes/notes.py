import tempfile
import os
from uuid import UUID
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from src.security import get_current_user, require_role
from src.db import get_connection
from src.ingest import ingest_pdf
from src.storage import upload_pdf_to_supabase, delete_pdf_from_supabase
from src.classifier import extract_preview_text, classify_document
from src.models import DocumentResponse, ClassificationResponse

router = APIRouter(prefix="/api/notes", tags=["Notes & Materials"])

@router.post("/classify", response_model=ClassificationResponse)
def auto_classify_pdf(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_role("faculty", "admin"))
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF documents are supported.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        file_bytes = file.file.read()
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        sample_text = extract_preview_text(tmp_path, max_pages=2)
        if not sample_text.strip():
            return {
                "suggested_course": "CS2003",
                "suggested_type": "notes",
                "confidence": 0.40,
                "rationale": "File contains no selectable text; defaults applied."
            }
        return classify_document(sample_text)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

@router.post("/upload", response_model=dict, status_code=status.HTTP_201_CREATED)
def upload_notes(
    course_code: str = Form(...),
    doc_type: str = Form("notes"),
    files: list[UploadFile] = File(...),
    current_user: dict = Depends(require_role("faculty", "admin"))
):
    clean_code = course_code.strip().upper()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT code FROM courses WHERE code = %s;", (clean_code,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Course does not exist")

    results = []
    errors = []

    for file in files:
        if not file.filename.lower().endswith(".pdf"):
            errors.append(f"{file.filename}: Skipped (Only PDF documents allowed).")
            continue

        try:
            file_bytes = file.file.read()
            cloud_path = f"{clean_code}/{file.filename}"

            # 1. Upload to Supabase Storage
            public_url = upload_pdf_to_supabase(file_bytes, cloud_path)

            # 2. Ingest into pgvector using a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(file_bytes)
                temp_pdf_path = tmp.name

            try:
                ingest_res = ingest_pdf(
                    file_path=temp_pdf_path,
                    course_id=clean_code,
                    doc_type=doc_type,
                    uploaded_by=str(current_user["id"])
                )
            finally:
                # Discard local file immediately
                if os.path.exists(temp_pdf_path):
                    os.remove(temp_pdf_path)

            # 3. Store Supabase URL in documents table
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE documents SET storage_url = %s WHERE id = %s;",
                        (public_url, ingest_res["document_id"])
                    )

            results.append({
                "document_id": ingest_res["document_id"],
                "filename": file.filename,
                "storage_url": public_url,
                "total_chunks": ingest_res["total_chunks"]
            })

        except Exception as e:
            errors.append(f"{file.filename}: {str(e)}")

    if not results and errors:
        raise HTTPException(status_code=500, detail=f"All uploads failed: {'; '.join(errors)}")

    return {
        "message": f"Successfully stored {len(results)} file(s) in cloud storage and pgvector.",
        "uploaded_count": len(results),
        "results": results,
        "errors": errors
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
    """Redirects user directly to the Supabase CDN public URL to view in browser."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT storage_url FROM documents WHERE id = %s;", (document_id,))
            doc = cur.fetchone()
            if not doc or not doc[0]:
                raise HTTPException(status_code=404, detail="Document not found or URL missing.")
            
    return RedirectResponse(url=doc[0])

@router.get("/download/{document_id}")
def download_document(document_id: UUID, current_user: dict = Depends(get_current_user)):
    """Redirects user directly to the Supabase CDN URL."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT storage_url FROM documents WHERE id = %s;", (document_id,))
            doc = cur.fetchone()
            if not doc or not doc[0]:
                raise HTTPException(status_code=404, detail="Document not found or URL missing.")
            
    return RedirectResponse(url=doc[0])

@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
def delete_document(
    document_id: UUID,
    current_user: dict = Depends(require_role("faculty", "admin"))
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT filename, course_id FROM documents WHERE id = %s;", (document_id,))
            doc = cur.fetchone()
            if not doc:
                raise HTTPException(status_code=404, detail="Document not found")
            filename, course_id = doc

            cur.execute("DELETE FROM documents WHERE id = %s;", (document_id,))

    # Remove from Supabase Storage
    try:
        delete_pdf_from_supabase(f"{course_id}/{filename}")
    except Exception:
        pass

    return {"message": f"Document '{filename}' removed from cloud and database."}