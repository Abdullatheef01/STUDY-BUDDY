from langchain_text_splitters import RecursiveCharacterTextSplitter


def default_splitter():
    return RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        length_function=len,
    )
