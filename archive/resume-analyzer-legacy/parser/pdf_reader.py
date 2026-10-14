"""
PDF Resume Reader - Extracts text from PDF files using PyPDF2.
"""
import PyPDF2
import io


def extract_text_from_pdf(file_path=None, file_stream=None):
    """
    Extract text content from a PDF file.
    
    Args:
        file_path: Path to PDF file on disk
        file_stream: File-like object (for uploaded files)
    
    Returns:
        str: Extracted text content
    """
    text = ""
    try:
        if file_stream:
            reader = PyPDF2.PdfReader(file_stream)
        elif file_path:
            reader = PyPDF2.PdfReader(file_path)
        else:
            return ""

        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    except Exception as e:
        print(f"Error reading PDF: {e}")
        return ""

    return text.strip()
