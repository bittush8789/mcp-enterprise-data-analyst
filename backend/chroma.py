"""ChromaDB Vector Store & Document Ingestion Pipeline.

Handles document loading, cleaning, chunking with metadata preservation,
embedding generation, persistent storage, and semantic vector retrieval.
"""

import os
import re
import glob
import logging
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions

from backend.config import settings

logger = logging.getLogger("enterprise_analyst.chroma")


class ChromaManager:
    """Manages document chunking, indexing, and vector similarity retrieval."""

    def __init__(self):
        self.client = self._init_client()
        self.embedding_fn = self._init_embedding_function()
        self.collection = self._get_or_create_collection()
        self._ensure_documents_ingested()

    def _init_client(self):
        """Initializes HttpClient if host is configured, otherwise PersistentClient."""
        if settings.CHROMA_HOST and settings.CHROMA_PORT:
            try:
                logger.info("Connecting to ChromaDB server at %s:%s...", settings.CHROMA_HOST, settings.CHROMA_PORT)
                return chromadb.HttpClient(
                    host=settings.CHROMA_HOST,
                    port=settings.CHROMA_PORT,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
            except Exception as e:
                logger.warning("Remote ChromaDB connection failed: %s. Falling back to local persist dir.", e)

        persist_dir = os.path.abspath(settings.CHROMA_PERSIST_DIR)
        os.makedirs(persist_dir, exist_ok=True)
        logger.info("Using local persistent ChromaDB at %s", persist_dir)
        return chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

    def _init_embedding_function(self):
        """Initializes a local embedding function."""
        try:
            return embedding_functions.DefaultEmbeddingFunction()
        except Exception as e:
            logger.warning("DefaultEmbeddingFunction error: %s. Using simple fallback.", e)
            return None

    def _get_or_create_collection(self):
        try:
            if self.embedding_fn:
                return self.client.get_or_create_collection(
                    name=settings.CHROMA_COLLECTION_NAME,
                    embedding_function=self.embedding_fn,
                    metadata={"hnsw:space": "cosine"},
                )
            return self.client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as e:
            logger.error("Failed to get/create ChromaDB collection: %s", e)
            raise

    def parse_document_header(self, content: str) -> Dict[str, str]:
        """Extracts structured metadata from document header."""
        meta = {
            "document_title": "Enterprise Document",
            "document_type": "Policy",
            "effective_date": "2024-01-01",
            "version": "1.0",
            "customer_segment": "All",
        }
        for line in content.split("\n")[:15]:
            line = line.strip()
            if line.startswith("Document Title:"):
                meta["document_title"] = line.split(":", 1)[1].strip()
            elif line.startswith("Policy Type:"):
                meta["document_type"] = line.split(":", 1)[1].strip()
            elif line.startswith("Effective Date:"):
                meta["effective_date"] = line.split(":", 1)[1].strip()
            elif line.startswith("Version:"):
                meta["version"] = line.split(":", 1)[1].strip()
            elif line.startswith("Applicable Customer Segment:"):
                meta["customer_segment"] = line.split(":", 1)[1].strip()
        return meta

    def chunk_document(self, text: str, chunk_size: int = 600, overlap: int = 100) -> List[str]:
        """Splits document text into semantic section-aware chunks."""
        # Split primarily by Markdown headers or double newlines
        sections = re.split(r"(?=\n## |\n# )", text)
        chunks = []

        for section in sections:
            section = section.strip()
            if not section:
                continue
            if len(section) <= chunk_size:
                chunks.append(section)
            else:
                # Sub-chunk by paragraphs or sentences
                paragraphs = section.split("\n\n")
                current_chunk = ""
                for para in paragraphs:
                    para = para.strip()
                    if not para:
                        continue
                    if len(current_chunk) + len(para) + 2 <= chunk_size:
                        current_chunk = f"{current_chunk}\n\n{para}".strip()
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = para
                if current_chunk:
                    chunks.append(current_chunk)

        return chunks

    def ingest_documents(self, docs_dir: str = "data/documents", force: bool = False):
        """Loads and indexes all documents into ChromaDB."""
        doc_files = glob.glob(os.path.join(docs_dir, "*.txt"))
        if not doc_files:
            logger.warning("No document files found in %s", docs_dir)
            return

        current_count = self.collection.count()
        if current_count > 0 and not force:
            logger.info("ChromaDB collection '%s' already contains %d chunks. Skipping re-ingestion.", settings.CHROMA_COLLECTION_NAME, current_count)
            return

        logger.info("Ingesting %d documents from %s into ChromaDB...", len(doc_files), docs_dir)
        ids = []
        documents = []
        metadatas = []

        for filepath in doc_files:
            doc_name = os.path.basename(filepath)
            doc_slug = os.path.splitext(doc_name)[0]
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            parsed_meta = self.parse_document_header(content)
            chunks = self.chunk_document(content)

            for idx, chunk in enumerate(chunks):
                chunk_id = f"{doc_slug}_chk_{idx+1}"
                meta = {
                    "document_name": doc_name,
                    "document_slug": doc_slug,
                    "document_title": parsed_meta["document_title"],
                    "document_type": parsed_meta["document_type"],
                    "version": parsed_meta["version"],
                    "effective_date": parsed_meta["effective_date"],
                    "customer_segment": parsed_meta["customer_segment"],
                    "chunk_id": chunk_id,
                }
                ids.append(chunk_id)
                documents.append(chunk)
                metadatas.append(meta)

        if ids:
            self.collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )
            logger.info("Successfully indexed %d chunks in ChromaDB.", len(ids))

    def _ensure_documents_ingested(self):
        try:
            self.ingest_documents()
        except Exception as e:
            logger.error("Error during automatic document ingestion: %s", e)

    def search_semantic(
        self,
        query: str,
        top_k: Optional[int] = None,
        where_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Performs vector similarity search against ChromaDB."""
        k = top_k or settings.TOP_K
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=min(k, max(1, self.collection.count())),
                where=where_filter,
            )

            hits = []
            if results and "documents" in results and results["documents"]:
                docs = results["documents"][0]
                metas = results["metadatas"][0] if "metadatas" in results else [{}] * len(docs)
                distances = results["distances"][0] if "distances" in results and results["distances"] else [0.0] * len(docs)
                ids = results["ids"][0] if "ids" in results else [""] * len(docs)

                for doc_id, doc, meta, dist in zip(ids, docs, metas, distances):
                    # Cosine distance to similarity score: 1 - dist (or normalize)
                    score = max(0.0, min(1.0, 1.0 - (dist / 2.0)))
                    hits.append({
                        "id": doc_id,
                        "content": doc,
                        "score": round(score, 4),
                        "metadata": meta,
                    })
            return hits
        except Exception as e:
            logger.error("ChromaDB semantic search failed: %s", e)
            return []

    def check_health(self) -> Dict[str, Any]:
        """Returns ChromaDB status and chunk count."""
        try:
            count = self.collection.count()
            return {
                "status": "healthy",
                "collection": settings.CHROMA_COLLECTION_NAME,
                "total_chunks": count,
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


# Global Singleton Instance
chroma_manager = ChromaManager()
