import hashlib

def calculate_file_hash(file_content: bytes) -> str:
    """Calculate SHA256 hash of file"""
    return hashlib.sha256(file_content).hexdigest()