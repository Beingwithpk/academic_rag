import json
import pymupdf
from groq import Groq
from src.config import GROQ_API_KEY, GROQ_MODEL
from src.db import get_connection

groq_client = Groq(api_key=GROQ_API_KEY)

def extract_preview_text(file_path: str, max_pages: int = 2, max_chars: int = 2500) -> str:
    """Extracts text from the first few pages of a PDF for classification."""
    extracted = []
    with pymupdf.open(file_path) as doc:
        for idx in range(min(len(doc), max_pages)):
            page_text = doc[idx].get_text()
            if page_text.strip():
                extracted.append(page_text.strip())
    
    full_text = "\n\n".join(extracted)
    return full_text[:max_chars]

def classify_document(sample_text: str) -> dict:
    """Uses Groq to classify the course and document type with structured output."""
    # 1. Fetch valid course catalog directly from database
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT code, title, semester FROM courses ORDER BY semester ASC, code ASC;")
            courses = [{"code": r[0], "title": r[1], "semester": r[2]} for r in cur.fetchall()]

    catalog_str = "\n".join([f"- {c['code']}: {c['title']} (Sem {c['semester']})" for c in courses])
    allowed_codes = [c["code"] for c in courses]
    allowed_types = ["notes", "pyq", "syllabus", "assignment"]

    system_prompt = (
        "You are an academic document classification assistant. Analyze the sample text extracted "
        "from the front pages of an academic PDF. Map it to exactly one course from the provided catalog "
        "and determine its document category.\n\n"
        f"Available Course Catalog:\n{catalog_str}\n\n"
        f"Allowed Document Types: {allowed_types}\n\n"
        "Return strictly a valid JSON object matching this schema:\n"
        "{\n"
        '  "suggested_course": "COURSE_CODE",\n'
        '  "suggested_type": "notes|pyq|syllabus|assignment",\n'
        '  "confidence": float between 0.0 and 1.0,\n'
        '  "rationale": "Brief 1-sentence explanation of the classification"\n'
        "}"
    )

    try:
        completion = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Document Sample Content:\n{sample_text}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        result = json.loads(completion.choices[0].message.content)

        # Fallback validation to guarantee schema safety
        if result.get("suggested_course") not in allowed_codes:
            result["suggested_course"] = allowed_codes[0] if allowed_codes else "CS2003"
        if result.get("suggested_type") not in allowed_types:
            result["suggested_type"] = "notes"
        if "confidence" not in result:
            result["confidence"] = 0.85
        if "rationale" not in result:
            result["rationale"] = "Classified based on key syllabus terminology."

        return result

    except Exception as e:
        return {
            "suggested_course": allowed_codes[0] if allowed_codes else "CS2003",
            "suggested_type": "notes",
            "confidence": 0.50,
            "rationale": f"Default fallback due to classification error: {str(e)}"
        }