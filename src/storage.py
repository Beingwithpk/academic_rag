from supabase import create_client, Client
from src.config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_BUCKET

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def upload_pdf_to_supabase(file_bytes: bytes, file_path_in_bucket: str) -> str:
    """
    Uploads a file directly from memory to Supabase Storage.
    Returns the public URL of the uploaded document.
    """
    # Upload binary content directly
    response = supabase.storage.from_(SUPABASE_BUCKET).upload(
        path=file_path_in_bucket,
        file=file_bytes,
        file_options={"content-type": "application/pdf", "upsert": "true"}
    )
    
    # Retrieve direct public URL for viewing
    public_url = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(file_path_in_bucket)
    return public_url

def delete_pdf_from_supabase(file_path_in_bucket: str):
    """Removes a file from the Supabase Storage bucket."""
    supabase.storage.from_(SUPABASE_BUCKET).remove([file_path_in_bucket])