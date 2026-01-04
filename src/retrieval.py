
class SimpleDocument:
    """
    A simple document wrapper to decouple from specific RAG libraries (LangChain/LlamaIndex).
    Matches the interface expected by loader.py:
    - page_content: str
    - metadata: dict
    """
    def __init__(self, content: str, metadata: dict = None):
        self.page_content = content
        self.metadata = metadata or {}
    
    def __repr__(self):
        return f"SimpleDocument(content={self.page_content[:20]}..., metadata={self.metadata})"

class DocStore:
    def __init__(self):
        self._sticky_docs = []
        self._index = None
        self._nodes = []
        
        # Lazy import to avoid hard dependency if not used
        try:
            from llama_index.core import VectorStoreIndex, Document
            from llama_index.core.node_parser import SentenceSplitter
            self.VectorStoreIndex = VectorStoreIndex
            self.Document = Document
            self.SentenceSplitter = SentenceSplitter
            self._has_llama = True
        except ImportError:
            self._has_llama = False
            print("Warning: llama-index not installed. DocStore will operate in limited mode.")

    def add_sticky(self, text: str):
        """Add a sticky document that is always retrieved (or handled separately)."""
        self._sticky_docs.append(text)

    def sticky(self):
        """Return all sticky documents."""
        return self._sticky_docs

    def add_file(self, file_path: str):
        """Add a file to the RAG index."""
        if not self._has_llama:
            return
            
        try:
            from llama_index.core import SimpleDirectoryReader
            # Load specific file
            docs = SimpleDirectoryReader(input_files=[file_path]).load_data()
            self._update_index(docs)
        except Exception as e:
            print(f"Error adding file {file_path}: {e}")

    def add_dir(self, dir_path: str):
        """Add a directory to the RAG index."""
        if not self._has_llama:
            return

        try:
            from llama_index.core import SimpleDirectoryReader
            # Load directory
            docs = SimpleDirectoryReader(input_dir=dir_path, recursive=True).load_data()
            self._update_index(docs)
        except Exception as e:
            print(f"Error adding dir {dir_path}: {e}")

    def _update_index(self, docs):
        """Update the internal index with new documents."""
        if not docs:
            return
            
        # Parse documents into nodes
        parser = self.SentenceSplitter()
        new_nodes = parser.get_nodes_from_documents(docs)
        self._nodes.extend(new_nodes)
        
        # Rebuild index (Simplistic approach for demo; in production, use ingestion pipeline)
        # Note: This is expensive for large datasets; prefer incremental updates or persistent storage
        self._index = self.VectorStoreIndex(self._nodes)

    def retrieve(self, query: str, top_k: int = 3):
        """
        Retrieve documents relevant to the query.
        Returns a list of SimpleDocument objects with 'page_content' and 'metadata'.
        """
        if not self._has_llama or not self._index:
            return []

        retriever = self._index.as_retriever(similarity_top_k=top_k)
        results = retriever.retrieve(query)
        
        output = []
        for node_with_score in results:
            node = node_with_score.node
            # Extract content
            content = node.get_content()
            
            # Extract metadata and inject source URL/Path
            # LlamaIndex SimpleDirectoryReader puts file path in 'file_path' key by default
            metadata = node.metadata.copy() if node.metadata else {}
            
            # Map LlamaIndex 'file_path' to generic 'source' for loader.py
            if "file_path" in metadata:
                metadata["source"] = metadata["file_path"]
            elif "file_name" in metadata:
                metadata["source"] = metadata["file_name"]
            else:
                metadata["source"] = "unknown"

            output.append(SimpleDocument(content=content, metadata=metadata))
            
        return output
