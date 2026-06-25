import re
from typing import List, Dict, Any

class RecursiveCharacterTextSplitter:
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = ["\n\n", "\n", " ", ""]

    def split_text(self, text: str) -> List[str]:
        return self._split_text(text, self.separators)

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        """Recursively split text by separators until chunks are below chunk_size."""
        final_chunks = []
        
        # Base case: text is already small enough
        if len(text) <= self.chunk_size:
            return [text]

        # Get separator
        if not separators:
            # No separators left, force split by size
            return [text[i:i + self.chunk_size] for i in range(0, len(text), self.chunk_size)]
        
        separator = separators[0]
        next_separators = separators[1:]

        # Split text by separator
        if separator == "":
            splits = list(text)
        else:
            splits = text.split(separator)

        # Process each split
        current_chunk = []
        current_len = 0

        for split in splits:
            if len(split) > self.chunk_size:
                # If current builder is not empty, flush it
                if current_chunk:
                    final_chunks.append(separator.join(current_chunk))
                    current_chunk = []
                    current_len = 0
                # Recursively split the long chunk
                final_chunks.extend(self._split_text(split, next_separators))
            else:
                # If adding split would exceed chunk_size
                if current_len + len(split) + (len(separator) if current_chunk else 0) > self.chunk_size:
                    if current_chunk:
                        final_chunks.append(separator.join(current_chunk))
                    # Retain overlap if we have a previous chunk
                    current_chunk = self._keep_overlap(current_chunk, separator, len(split))
                    current_len = sum(len(c) for c in current_chunk) + (len(separator) * (len(current_chunk) - 1) if current_chunk else 0)
                
                current_chunk.append(split)
                current_len += len(split) + (len(separator) if len(current_chunk) > 1 else 0)

        if current_chunk:
            final_chunks.append(separator.join(current_chunk))

        return [c for c in final_chunks if c.strip()]

    def _keep_overlap(self, current_chunk: List[str], separator: str, next_split_len: int) -> List[str]:
        """Helper to retain a portion of the previous chunks to preserve overlap."""
        if not current_chunk or self.chunk_overlap <= 0:
            return []
            
        overlap_chunks = []
        curr_overlap_len = 0
        
        # Traverse backward to collect chunks for overlap
        for chunk in reversed(current_chunk):
            if curr_overlap_len + len(chunk) + (len(separator) if overlap_chunks else 0) <= self.chunk_overlap:
                overlap_chunks.insert(0, chunk)
                curr_overlap_len += len(chunk) + (len(separator) if len(overlap_chunks) > 1 else 0)
            else:
                break
                
        return overlap_chunks


def process_documents(documents: List[Dict[str, Any]], chunk_size: int = 500, chunk_overlap: int = 50) -> List[Dict[str, Any]]:
    """
    Takes a list of documents: [{"url": url, "title": title, "text": text}]
    Returns a list of chunks: [{"url": url, "title": title, "text": chunk_text, "chunk_index": idx}]
    """
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    all_chunks = []

    for doc in documents:
        url = doc.get("url", "")
        title = doc.get("title", "")
        text = doc.get("text", "")
        
        chunks = splitter.split_text(text)
        for idx, chunk_text in enumerate(chunks):
            all_chunks.append({
                "url": url,
                "title": title,
                "text": chunk_text,
                "chunk_index": idx
            })
            
    return all_chunks
