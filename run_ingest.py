import sys
from src.db import init_tables
from src.ingest import ingest_pdf

if __name__ == "__main__":
    init_tables()

    if len(sys.argv) < 3:
        print("Usage: python run_ingest.py <path_to_pdf> <course_id> [doc_type]")
        print("Example: python run_ingest.py data/samples/OS_Unit1.pdf CS301 notes")
        sys.exit(1)

    path = sys.argv[1]
    course = sys.argv[2]
    dtype = sys.argv[3] if len(sys.argv) > 3 else "notes"

    ingest_pdf(path, course, dtype)