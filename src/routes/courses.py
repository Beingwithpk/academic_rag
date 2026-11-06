from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from src.models import CourseCreate, CourseUpdate, CourseResponse, FacultyDetailResponse
from src.security import get_current_user, require_role
from src.db import get_connection

router = APIRouter(prefix="/api/courses", tags=["Courses"])

@router.get("/all", response_model=list[CourseResponse])
def get_all_courses(semester: Optional[int] = Query(None)):
    """Retrieves all academic courses grouped and ordered by semester and code."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if semester:
                cur.execute(
                    "SELECT code, title, semester, faculty_id FROM courses WHERE semester = %s ORDER BY semester ASC, code ASC;",
                    (semester,)
                )
            else:
                cur.execute(
                    "SELECT code, title, semester, faculty_id FROM courses ORDER BY semester ASC, code ASC;"
                )
            rows = cur.fetchall()

    return [{"code": r[0], "title": r[1], "semester": r[2], "faculty_id": r[3]} for r in rows]

# Admin: Add New Subject
@router.post("/", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
def create_course(
    course: CourseCreate,
    current_user: dict = Depends(require_role("admin"))
):
    code = course.code.strip().upper()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT code FROM courses WHERE code = %s;", (code,))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail=f"Course code '{code}' already exists.")

            cur.execute(
                """
                INSERT INTO courses (code, title, semester)
                VALUES (%s, %s, %s)
                RETURNING code, title, semester, faculty_id;
                """,
                (code, course.title.strip(), course.semester)
            )
            created = cur.fetchone()

    return {"code": created[0], "title": created[1], "semester": created[2], "faculty_id": created[3]}

# Admin: Edit Subject & Semester
@router.put("/{code}", response_model=CourseResponse)
def update_course(
    code: str,
    update: CourseUpdate,
    current_user: dict = Depends(require_role("admin"))
):
    clean_code = code.strip().upper()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT code FROM courses WHERE code = %s;", (clean_code,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Course not found")

            cur.execute(
                """
                UPDATE courses
                SET title = %s, semester = %s
                WHERE code = %s
                RETURNING code, title, semester, faculty_id;
                """,
                (update.title.strip(), update.semester, clean_code)
            )
            updated = cur.fetchone()

    return {"code": updated[0], "title": updated[1], "semester": updated[2], "faculty_id": updated[3]}

# Admin: Delete Subject
@router.delete("/{code}", status_code=status.HTTP_200_OK)
def delete_course(
    code: str,
    current_user: dict = Depends(require_role("admin"))
):
    clean_code = code.strip().upper()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT code FROM courses WHERE code = %s;", (clean_code,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Course not found")

            # CASCADE in DB removes documents, chunks, and sessions
            cur.execute("DELETE FROM courses WHERE code = %s;", (clean_code,))

    return {"message": f"Course {clean_code} deleted successfully."}

# Admin: View Faculty Details
@router.get("/faculty-details", response_model=list[FacultyDetailResponse])
def get_faculty_details(current_user: dict = Depends(require_role("admin"))):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.email, u.full_name, u.role, u.created_at,
                       COUNT(d.id) AS uploaded_docs_count
                FROM users u
                LEFT JOIN documents d ON u.id = d.uploaded_by
                WHERE u.role IN ('faculty', 'admin')
                GROUP BY u.id, u.email, u.full_name, u.role, u.created_at
                ORDER BY u.created_at DESC;
                """
            )
            rows = cur.fetchall()

    return [
        {
            "id": r[0],
            "email": r[1],
            "full_name": r[2],
            "role": r[3],
            "created_at": r[4],
            "uploaded_docs_count": r[5]
        }
        for r in rows
    ]