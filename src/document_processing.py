# src/document_processing.py
import fitz
import spacy
import re as r
from typing import List

class PDFExtractor:
    """Extrai texto de arquivos PDF."""
    def extract(self, file_path: str) -> str:
        try:
            document = fitz.open(file_path)
            full_text = "".join([page.get_text() for page in document])
            document.close()
            return full_text
        except Exception as e:
            print(f"Erro ao extrair texto do PDF '{file_path}': {e}")
            return ""

class SemanticChunker:
    """Divide o texto em chunks semânticos baseados em sentenças."""
    def __init__(self, model_name: str, max_chunk_size: int):
        try:
            self.nlp = spacy.load(model_name, disable=["tagger", "parser", "ner", "lemmatizer", "textcat"])
            self.nlp.add_pipe('sentencizer')
        except OSError:
            print(f"Modelo SpaCy '{model_name}' não encontrado. Por favor, execute: python -m spacy download {model_name}")
            self.nlp = None
        self.max_chunk_size = max_chunk_size

    def chunk(self, text: str) -> List[str]:
        if not self.nlp or not text:
            return []
        
        clean_text = r.sub(r'\s+', ' ', text).strip()
        doc = self.nlp(clean_text)
        sentences = [s.text.strip() for s in doc.sents]
        
        chunks = []
        current_chunk = ""
        for sentence in sentences:
            if len(current_chunk.split()) + len(sentence.split()) <= self.max_chunk_size:
                current_chunk += " " + sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        return chunks