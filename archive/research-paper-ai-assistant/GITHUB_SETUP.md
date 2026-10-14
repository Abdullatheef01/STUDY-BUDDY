# Pushing to GitHub

Follow these steps to push your Research Paper AI Assistant project to GitHub:

## 1. Initialize Git (if not already done)

```bash
cd d:\PYTHON\Research_paper_project_with_API
git init
```

## 2. Add All Files to Git

```bash
git add .
```

## 3. Create Initial Commit

```bash
git commit -m "Initial commit: Research Paper AI Assistant with Constructor and Deconstructor"
```

## 4. Create a GitHub Repository

1. Go to https://github.com/new
2. Enter repository name: `research-paper-assistant`
3. Add description: "AI-powered research assistant that generates IEEE papers from GitHub repos and analyzes research papers"
4. Choose **Public** (recommended for open source)
5. **Do NOT** initialize with README, .gitignore, or license (we already have them)
6. Click **Create repository**

## 5. Add Remote and Push

```bash
# Replace YOUR_USERNAME with your GitHub username
git remote add origin https://github.com/YOUR_USERNAME/research-paper-assistant.git

# Rename main branch if needed
git branch -M main

# Push to GitHub
git push -u origin main
```

## 6. Verify

Visit: `https://github.com/YOUR_USERNAME/research-paper-assistant`

Your project should now be visible on GitHub! ✅

---

## Important Files

### Protected by .gitignore (NOT pushed):
- `.env` - Contains your API keys
- `data/` - User data, chat history, embeddings
- `venv/` - Virtual environment
- `__pycache__/` - Python cache
- `.vscode/` - IDE settings

### Shared with .gitignore:
- `README.md` - Project documentation ✅
- `requirements.txt` - Dependencies ✅
- `.env.example` - Template for environment setup ✅
- Source code (all Python files) ✅
- Documentation files ✅

---

## For Collaborators

When someone clones your repo, they need to:

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/research-paper-assistant.git
cd research-paper-assistant

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env from example
cp .env.example .env
# Edit .env with their own API keys

# Run the app
streamlit run home.py
```

---

## Setting Up GitHub Actions (Optional)

To add automated testing/linting, create `.github/workflows/tests.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest flake8
      - name: Lint
        run: flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```

---

## Updating Your Repository

```bash
# Make changes to your code
git add .
git commit -m "Description of changes"
git push origin main
```

---

## Useful Git Commands

```bash
# Check status
git status

# View commits
git log --oneline

# Revert last commit (if needed)
git reset --soft HEAD~1

# Create a new branch for features
git checkout -b feature/my-feature
git push origin feature/my-feature
```

---

**Your project is now on GitHub and ready for collaboration! 🚀**
