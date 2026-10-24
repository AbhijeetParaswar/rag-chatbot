# System Architecture

## Architecture Overview

DocuRAG is an enterprise-grade, grounded Retrieval-Augmented Generation (RAG) platform designed to provide strictly factual answers over PDFs with verified inline and double-ended citations, persistent conversations, and dual-layer memory.

```mermaid
flowchart TD
    subgraph Client["Frontend (React + Vite + TypeScript + Tailwind)"]
        UI["ChatGPT-style UI\n(Sidebar, ChatArea, Drawer)"]
        StreamConsumer["Fetch + ReadableStream\n(SSE Parser & AbortController)"]
        UI <--> StreamConsumer
    end

    subgraph API["FastAPI Application (Uvicorn)"]
        Main["main.py\n(CORS, SlowAPI Limiter, Lifespan)"]
        ChatRouter["/chat & /chat/stream"]
        ThreadRouter["/threads CRUD"]
        DocRouter["/documents & /upload"]
        MemRouter["/memory CRUD"]
    end

    subgraph MemoryLayer["Dual-Tier Memory System"]
        STM["Short-Term Memory\n(Rolling 10 msgs + LLM Summary)"]
        QueryRewriter["Query Rewriter\n(Contextual Disambiguation)"]
        LTM["Long-Term Memory\n(Fact Extraction Background Task)"]
    end

    subgraph RetrievalLayer["Retrieval & Ranking Pipeline"]
        Embedder["Sentence-Transformers\n(BAAI/bge-small-en-v1.5)"]
        ChromaDocs["ChromaDB Collection: 'documents'\n(Cosine Similarity HNSW)"]
        ChromaMems["ChromaDB Collection: 'memories'"]
        Reranker["Cross-Encoder Reranker\n(BAAI/bge-reranker-base)"]
        ThresholdGuard["Similarity Threshold Guard\n(Honest 'Not Answerable' Filter)"]
    end

    subgraph LLMLayer["LLM & Citations Engine"]
        PromptEngine["Prompt Engine\n(Untrusted Data Fences & Injection Defense)"]
        LLMProvider["LLM Provider Adapter\n(Gemini / OpenAI / Anthropic / Ollama)"]
        CitationEngine["Citation Validator & Parser\n([n] extraction & chunk verification)"]
    end

    subgraph Storage["Persistent Relational Storage"]
        SQLite[("SQLite 2.0 via aiosqlite\nthreads, messages, documents, memories")]
    end

    %% Flow connections
    StreamConsumer <-->|SSE Stream / JSON| ChatRouter
    UI <-->|HTTP REST| ThreadRouter
    UI <-->|HTTP Multipart| DocRouter
    UI <-->|HTTP REST| MemRouter

    ChatRouter --> STM
    STM --> QueryRewriter
    QueryRewriter --> Embedder
    Embedder --> ChromaDocs
    ChromaDocs --> Reranker
    Reranker --> ThresholdGuard

    ChatRouter --> LTM
    LTM <--> ChromaMems
    LTM <--> SQLite

    ThresholdGuard -->|Filtered Chunks| PromptEngine
    PromptEngine --> LLMProvider
    LLMProvider -->|Token Stream| CitationEngine
    CitationEngine -->|sources_start -> token* -> sources_end -> done| ChatRouter

    ThreadRouter <--> SQLite
    DocRouter <--> SQLite
    ChatRouter <--> SQLite
```

## Detailed Data Flows

### 1. Ingestion Pipeline
1. **Document Upload**: PDF is saved to `data/pdfs/` and a SHA-256 hash is computed.
2. **Idempotency Guard**: If the hash already matches an indexed document record, re-indexing is skipped.
3. **Extraction & Heading Detection**: PyMuPDF (`fitz`) extracts text per page and discovers section headers via regex heuristics (`Chapter`, `Unit`, `Section`, numbered headings).
4. **Recursive Chunking**: Chunks of ~800 characters with ~120 overlap are formed without crossing page boundaries.
5. **Metadata Tagging**: Each chunk is tagged with `chunk_id`, `doc_id`, `file_name`, `page_start`, `page_end`, `section_title`, `chunk_index`, and character offsets.
6. **Vector Persistence**: Vectors are computed with `BAAI/bge-small-en-v1.5` and written to ChromaDB's `documents` collection.

### 2. Retrieval & Query Rewriting
1. **Follow-Up Resolution**: Short-term memory (last 10 messages) is used to rewrite queries like *"What is the late penalty for it?"* into *"What is the late penalty for CS101 assignments?"*.
2. **Hybrid Search**: ChromaDB retrieves candidate chunks using cosine similarity.
3. **Optional Cross-Encoder Reranker**: `BAAI/bge-reranker-base` re-scores candidate pairs `(query, passage)` for high semantic precision.
4. **Answerability Guard**: If the top score falls below the configurable threshold (default `0.35`), the query is flagged as unanswerable, preventing hallucination.

### 3. Generation & Double-Ended Citations
1. **Sources Start**: Before generation begins, `sources_start` emits all candidate passages with page numbers and snippets.
2. **Token Streaming**: Tokens stream via SSE directly to the frontend.
3. **Inline Citation Chips**: Any `[n]` output is verified against retrieved chunks. Invalid or hallucinated indices are stripped.
4. **Sources End**: After generation, `sources_end` delivers the final verified citation list containing only the passages the model actually relied on.

### 4. Dual-Layer Memory
- **Short-Term Memory**: Scoped to the current thread. Stores recent messages. Once past the window limit, an LLM generates a rolling summary of older messages.
- **Long-Term Memory**: Scoped across threads to `user_id`. An asynchronous background task extracts durable preferences/facts, deduplicates them against existing memories, and stores them in SQLite and ChromaDB (`memories` collection). At query time, top-3 memories are injected into the system prompt to guide response style without being cited as factual document sources.
