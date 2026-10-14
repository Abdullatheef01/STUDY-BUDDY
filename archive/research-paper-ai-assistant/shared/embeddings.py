from langchain_community.embeddings import HuggingFaceEmbeddings
from shared.config import EMBEDDING_MODEL_NAME
import streamlit as st

@st.cache_resource
def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
