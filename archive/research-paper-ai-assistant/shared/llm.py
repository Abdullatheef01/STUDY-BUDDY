from groq import Groq
import os
from langchain_core.messages import HumanMessage, AIMessage


def get_client():
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY not set")
    return Groq(api_key=key)


def chat(prompt: str, model=None, max_tokens=1024, temperature=0.2):
    client = get_client()
    
    if model is None:
        model = "llama-3.1-8b-instant"

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return response.choices[0].message.content
