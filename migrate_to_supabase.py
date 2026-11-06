import os
from src.db import get_connection
from src.storage import upload_pdf_to_supabase

UPLOAD_DIR = os.path.join(os.getcwd(), "data", "uploads")

def migrate_local_files():
    print("Connecting to Neon PostgreSQL...")
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Query documents that haven't been linked to cloud storage yet
            cur.execute("""
                SELECT id, filename, course_id, storage_url 
                FROM documents 
                WHERE storage_url IS NULL OR storage_url = '';
            """)
            documents = cur.fetchall()

            if not documents:
                print("No pending local documents found. All records already have cloud storage URLs!")
                return

            print(f"Found {len(documents)} document(s) to migrate to Supabase Storage.\n")

            migrated_count = 0
            for doc_id, filename, course_id, _ in documents:
                # Local naming convention check: either "{course_id}_{filename}" or pure "{filename}"
                local_path_prefixed = os.path.join(UPLOAD_DIR, f"{course_id}_{filename}")
                local_path_raw = os.path.join(UPLOAD_DIR, filename)

                target_file_path = None
                if os.path.exists(local_path_prefixed):
                    target_file_path = local_path_prefixed
                elif os.path.exists(local_path_raw):
                    target_file_path = local_path_raw

                if not target_file_path:
                    print(f"⚠️ [Skipped] Local file not found for: {filename} (Course: {course_id})")
                    continue

                print(f"Uploading: {filename} -> Supabase ({course_id}/{filename})...")
                try:
                    with open(target_file_path, "rb") as f:
                        file_bytes = f.read()

                    cloud_path = f"{course_id}/{filename}"
                    public_url = upload_pdf_to_supabase(file_bytes, cloud_path)

                    # Update database record with the new public URL
                    cur.execute(
                        "UPDATE documents SET storage_url = %s WHERE id = %s;",
                        (public_url, doc_id)
                    )
                    print(f"✅ Synced: {filename} -> {public_url}\n")
                    migrated_count += 1

                except Exception as e:
                    print(f"❌ Failed to migrate {filename}: {str(e)}\n")

    print(f"Migration finished! Successfully synced {migrated_count}/{len(documents)} files to Supabase.")

if __name__ == "__main__":
    migrate_local_files()