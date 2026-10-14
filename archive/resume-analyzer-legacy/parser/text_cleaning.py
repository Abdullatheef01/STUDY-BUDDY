"""
Text Cleaning Module - Normalizes and cleans resume text for processing.
"""
import re
import unicodedata


def clean_text(text):
    """
    Clean and normalize resume text.
    
    Args:
        text: Raw text extracted from resume
    
    Returns:
        str: Cleaned text
    """
    if not text:
        return ""

    # Normalize unicode characters
    text = unicodedata.normalize('NFKD', text)

    # Replace multiple whitespace with single space
    text = re.sub(r'\s+', ' ', text)

    # Remove special characters but keep useful punctuation
    text = re.sub(r'[^\w\s@.,:;/\-+#()&|]', '', text)

    # Fix common encoding issues
    text = text.replace('â€™', "'")
    text = text.replace('â€"', "-")
    text = text.replace('â€œ', '"')
    text = text.replace('â€', '"')

    # Remove extra spaces around punctuation
    text = re.sub(r'\s*([,:;])\s*', r'\1 ', text)

    # Remove leading/trailing whitespace
    text = text.strip()

    return text


def normalize_text(text):
    """
    Normalize text for comparison (lowercase, remove extra spaces).
    
    Args:
        text: Text to normalize
    
    Returns:
        str: Normalized text
    """
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    return text


def extract_email(text):
    """Extract email addresses from text."""
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(pattern, text)
    return emails[0] if emails else None


def extract_phone(text):
    """Extract phone numbers from text."""
    pattern = r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
    phones = re.findall(pattern, text)
    return phones[0] if phones else None


def extract_links(text):
    """Extract URLs and links from text."""
    pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    links = re.findall(pattern, text)
    return links
