import psycopg
from pgvector.psycopg import register_vector
from src.config import DATABASE_URL

def get_connection():
    """Returns a psycopg connection with pgvector registered."""
    conn = psycopg.connect(DATABASE_URL, autocommit=True)
    register_vector(conn)
    return conn

SEMESTER_CURRICULUM = [
    # Semester 1
    ("MA1001", "Engineering Mathematics - I", 1),
    ("PH1001", "Engineering Physics", 1),
    ("CS1001", "Fundamentals of Computer Programming", 1),
    ("EE1001", "Fundamentals of Electrical and Electronics", 1),
    ("HS1001", "Professional Communication", 1),
    ("HY1001", "Health and Yoga", 1),

    # Semester 2
    ("MA1002", "Engineering Mathematics - II", 2),
    ("CS1002", "Discrete Structure", 2),
    ("EC1002", "Digital Logic and Design", 2),
    ("CS1004", "Data Structure and Algorithms", 2),
    ("CS1006", "Object Oriented Programming", 2),
    ("HS1002", "Ethics and Human Values for Engineers", 2),

    # Semester 3
    ("CS2001", "Design and Analysis of Algorithms", 3),
    ("CS2003", "Database Management System", 3),
    ("CS2005", "Computer Organization and Architecture", 3),
    ("CS2007", "Formal Language and Automata Theory", 3),
    ("EC2001", "Signal and Communication Systems", 3),
    ("CS2009", "Advance Programming Lab - I (Python)", 3),

    # Semester 4
    ("MA2002", "Engineering Mathematics - III", 4),
    ("CS2002", "Computer Networks and Communication", 4),
    ("CS2004", "Operating Systems", 4),
    ("CS2006", "Data Mining and Warehousing", 4),
    ("CS2008", "Principles of Compiler Design", 4),
    ("CS2010", "Advance Programming Lab - II (WebTech)", 4),
]

def init_tables():
    """Initializes tables and seeds courses across Semesters 1-4."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            
            # 1. Users
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    email VARCHAR(255) UNIQUE NOT NULL,
                    full_name VARCHAR(150) NOT NULL,
                    hashed_password VARCHAR(255) NOT NULL,
                    role VARCHAR(20) NOT NULL CHECK (role IN ('student', 'faculty', 'admin')),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)

            # 2. Courses
            cur.execute("""
                CREATE TABLE IF NOT EXISTS courses (
                    code VARCHAR(50) PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    semester INT DEFAULT 1,
                    faculty_id UUID REFERENCES users(id) ON DELETE SET NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            cur.execute("ALTER TABLE courses ADD COLUMN IF NOT EXISTS semester INT DEFAULT 1;")

            # 3. Documents
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    filename VARCHAR(255) NOT NULL,
                    course_id VARCHAR(50) REFERENCES courses(code) ON DELETE CASCADE,
                    doc_type VARCHAR(50) NOT NULL,
                    uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL;")

            # 4. Document Chunks (pgvector)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
                    course_id VARCHAR(50) NOT NULL,
                    doc_type VARCHAR(50) NOT NULL,
                    page_number INT NOT NULL,
                    chunk_index INT NOT NULL,
                    content TEXT NOT NULL,
                    embedding VECTOR(384) NOT NULL
                );
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw 
                ON document_chunks USING hnsw (embedding vector_cosine_ops);
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_course_type 
                ON document_chunks (course_id, doc_type);
            """)
            cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS storage_url TEXT;")

            # 5. Chat Sessions & Messages
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                    course_code VARCHAR(50) REFERENCES courses(code) ON DELETE CASCADE,
                    title VARCHAR(255) DEFAULT 'New Chat',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
                    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
                    content TEXT NOT NULL,
                    sources JSONB DEFAULT '[]'::jsonb,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)

            # Seed All Semester Courses
            cur.execute("SELECT COUNT(*) FROM courses;")
            course_count = cur.fetchone()[0]

            if course_count == 0:
                for code, title, sem in SEMESTER_CURRICULUM:
                    cur.execute(
                        """
                        INSERT INTO courses (code, title, semester)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (code) DO NOTHING;
                        """,
                        (code, title, sem)
                    )