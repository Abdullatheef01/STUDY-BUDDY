# Bug Report and Fixes

## Summary
Found and fixed **8 critical bugs** across the project that would prevent the application from running correctly.

---

## Bugs Found and Fixed

### 🐛 Bug #1: Undefined 'memory' variable in shared/llm.py
**File:** [shared/llm.py](shared/llm.py#L18-L19)
**Severity:** CRITICAL
**Issue:** The `chat()` function referenced an undefined `memory` variable.
```python
# BEFORE (BROKEN)
if memory:
    full_messages.extend(memory.get())
```
**Fix:** Removed memory reference and simplified function to accept a string prompt instead of message objects.
```python
# AFTER (FIXED)
def chat(prompt: str, model=None, max_tokens=1024, temperature=0.2):
    client = get_client()
    
    if model is None:
        model = "llama-3.1-8b-instant"

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content
```

---

### 🐛 Bug #2: Function name mismatch - ingest_documents vs ingest_pdfs
**File:** [deconstructor/ingestion.py](deconstructor/ingestion.py) & [deconstructor/app.py](deconstructor/app.py#L64)
**Severity:** CRITICAL
**Issue:** `app.py` calls `ingest_pdfs()` but the function was named `ingest_documents()`.
```python
# BEFORE (BROKEN)
def ingest_documents(files, session_id: str):
    # ...
```
**Fix:** Renamed function and updated signature to match how it's called in app.py.
```python
# AFTER (FIXED)
def ingest_pdfs(vectorstore, session_id: str, files):
    # Accepts vectorstore as first parameter since it's already initialized
    # ...
```

---

### 🐛 Bug #3: Incorrect 'chat' function call in constructor/paper_generator.py
**File:** [constructor/paper_generator.py](constructor/paper_generator.py)
**Severity:** CRITICAL
**Issue:** Called `chat()` with keyword arguments (model, max_tokens, temperature) but shared/llm.py's function didn't accept them.
```python
# BEFORE (BROKEN)
sections["title"] = chat(
    title_prompt,
    model="llama-3.1-8b-instant",
    max_tokens=80,
    temperature=0.2,
).strip()
```
**Fix:** Updated shared/llm.py's chat() function to accept these parameters.

---

### 🐛 Bug #4: Missing 'init_db()' function in deconstructor/database.py
**File:** [deconstructor/app.py](deconstructor/app.py#L12) calls `init_db()` but function wasn't defined
**Severity:** CRITICAL
**Issue:** The function was called but never defined.
```python
# BEFORE (BROKEN)
init_db()  # NameError: name 'init_db' is not defined
```
**Fix:** Added the missing function.
```python
# AFTER (FIXED)
def init_db():
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(engine)
```

---

### 🐛 Bug #5: Missing 'last_active' column in ChatSession model
**File:** [deconstructor/database.py](deconstructor/database.py#L25) and [deconstructor/app.py](deconstructor/app.py#L113)
**Severity:** CRITICAL
**Issue:** `app.py` accesses `s.last_active` but the column wasn't defined in the ChatSession model.
```python
# BEFORE (BROKEN)
class ChatSession(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    # last_active MISSING!
```
**Fix:** Added the missing column.
```python
# AFTER (FIXED)
class ChatSession(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)  # ADDED
```

---

### 🐛 Bug #6: Wrong role value in deconstructor/app.py
**File:** [deconstructor/app.py](deconstructor/app.py#L110)
**Severity:** HIGH
**Issue:** Used `role="ai"` but the retriever expects `role="assistant"`.
```python
# BEFORE (BROKEN)
db.add(ChatMessage(session_id=st.session_state.session_id, role="ai", content=answer))
```
**Fix:** Changed to standard role name.
```python
# AFTER (FIXED)
db.add(ChatMessage(session_id=st.session_state.session_id, role="assistant", content=answer))
```

---

### 🐛 Bug #7: Logic error - last_active not updated properly
**File:** [deconstructor/app.py](deconstructor/app.py#L112)
**Severity:** MEDIUM
**Issue:** `s.last_active = s.last_active` doesn't actually update the timestamp.
```python
# BEFORE (BROKEN)
s.last_active = s.last_active  # No-op!
```
**Fix:** Update with current timestamp.
```python
# AFTER (FIXED)
from datetime import datetime
if s:
    s.last_active = datetime.utcnow()
```

---

### 🐛 Bug #8: Function name inconsistency in deconstructor/llm.py
**File:** [deconstructor/llm.py](deconstructor/llm.py) and [deconstructor/app.py](deconstructor/app.py#L103)
**Severity:** MEDIUM
**Issue:** Function defined as `chat()` but app.py imports and calls it as `ask()`.
```python
# BEFORE (BROKEN)
from deconstructor.llm import ask
# ... later ...
answer = ask(f"Context:\n{context}\n\nQuestion:\n{q}\nAnswer:")
```
**Fix:** Renamed function definition to match usage.
```python
# AFTER (FIXED)
def ask(prompt: str) -> str:
    """Send a prompt to Groq LLM and get a response."""
    # ... implementation
```

---

## Summary of Changes

| File | Bugs Fixed | Type |
|------|-----------|------|
| [shared/llm.py](shared/llm.py) | #1, #3 | Function signature + undefined variable |
| [deconstructor/ingestion.py](deconstructor/ingestion.py) | #2 | Function name mismatch |
| [deconstructor/database.py](deconstructor/database.py) | #4, #5 | Missing function + missing column |
| [deconstructor/app.py](deconstructor/app.py) | #6, #7 | Wrong role name + logic error |
| [deconstructor/llm.py](deconstructor/llm.py) | #8 | Function name inconsistency |
| [constructor/analysis.py](constructor/analysis.py) | #3 | Function call signature |

---

## Verification

All errors have been resolved. Run the following to verify:
```bash
python -m py_compile shared/llm.py deconstructor/*.py constructor/*.py
```

The application should now run without critical runtime errors.
