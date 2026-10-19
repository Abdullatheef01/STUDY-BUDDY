# Quickstart

## Hosted demo

Visit [the live demo](https://study-buddy-3m16.onrender.com).
First load may take ~30s (free-tier cold start).

## Local development

```bash
git clone <repo-url>
cd <repo>
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env  # add your keys
.venv/bin/python unified_app.py
```

## Docker

```bash
docker build -t study-buddy .
docker run -p 5000:5000 --env-file .env study-buddy
```
