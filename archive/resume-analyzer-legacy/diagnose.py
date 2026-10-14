import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Testing parser imports...")
try:
    from parser.pdf_reader import extract_text_from_pdf
    from parser.docx_reader import extract_text_from_docx
    print("Parser imports OK")
except Exception as e:
    print(f"Parser import FAILED: {e}")

print("\nTesting model imports...")
try:
    from models.skill_extractor import extract_skills
    from models.bert_matcher import get_recommendations
    print("Model imports OK")
except Exception as e:
    print(f"Model import FAILED: {e}")

print("\nTesting BERT model loading...")
try:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print("BERT model loading OK")
except Exception as e:
    print(f"BERT model loading FAILED: {e}")

print("\nChecking data files...")
data_files = ['data/jobs.csv', 'data/skills_db.csv', 'data/coding_questions.csv', 'data/company_questions.csv']
for f in data_files:
    if os.path.exists(f):
        print(f"File {f} FOUND")
    else:
        print(f"File {f} MISSING")

print("\nChecking uploads directory...")
if os.path.exists('web_app/uploads'):
    print("Uploads directory exists")
else:
    print("Uploads directory MISSING - creating now")
    os.makedirs('web_app/uploads', exist_ok=True)
