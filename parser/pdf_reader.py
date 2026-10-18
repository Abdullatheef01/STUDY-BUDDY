"""
PDF Resume Reader - Extracts text from PDF files using pypdf.
"""
import re

import pypdf


def extract_text_from_pdf(file_path=None, file_stream=None):
    """
    Extract text content from a PDF file with layout-aware normalization.
    """
    text = ""
    try:
        if file_stream:
            reader = pypdf.PdfReader(file_stream)
        elif file_path:
            reader = pypdf.PdfReader(file_path)
        else:
            return ""

        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                # Basic text reconstruction: fix spaced-out characters like "S u m m a r y"
                # but preserve legitimate single spaces
                page_text = re.sub(r'(?<=[A-Z])\s(?=[A-Z]\s|[A-Z]$)', '', page_text)
                text += page_text + "\n"

    except Exception as e:
        print(f"Error reading PDF: {e}")
        return ""

    return text.strip()
