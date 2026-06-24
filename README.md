# Atharva Pande

AI Engineer building production LLM systems — Text-to-SQL, RAG pipelines, agentic workflows, and backend APIs.

📍 Noida, India &nbsp;|&nbsp; [LinkedIn](https://www.linkedin.com/in/atharva-pande-5367632b9/) &nbsp;|&nbsp; [LeetCode](https://leetcode.com/u/blueHoax/) &nbsp;|&nbsp; atharvapande984@gmail.com

---

## About

Currently at **Axtria Pvt. Ltd.** as an AI Engineer, building production LLM systems for enterprise pharma analytics — Text-to-SQL pipelines, prompt engineering, NLU workflow refinement, and multi-layer FastAPI inference endpoints.

Interests: Agentic AI, LLM Infrastructure, RAG Systems, Backend Engineering, Distributed Systems.

---

## Projects

### [QueryMind](./QueryMind) — Multi-Source Agentic AI Analytics Platform

> Full-stack AI platform for querying structured (CSV) and unstructured (PDF) data in plain English. The core problem it solves: *what actually breaks when a question needs both a database lookup and a document lookup, in a specific order, with the first answer feeding the second.*

**Architecture:** A LangGraph `StateGraph` routes every query into one of five execution paths — `sql`, `rag`, `both_sql_first`, `both_rag_first`, or `both_parallel`. The conditional routes (`both_*`) decompose the question into a condition + branch plan, run the first pipeline against real data, evaluate the condition deterministically, then pass only the resolved instruction to the second pipeline. No LLM ever reasons across two data sources simultaneously.

**Key engineering decisions:**
- **No LangChain wrappers** — ChromaDB and Gemini SDK called directly; LangGraph used for orchestration only
- **Structured output enforcement** — router uses `response_mime_type="text/x.enum"` so the route is always a valid enum value, never free text
- **Three-stage SQL safety** — safety check (SELECT-only) → sqlglot AST schema validation → execution, with LLM self-repair on failures
- **Semantic table selection** — table descriptions embedded in ChromaDB; only relevant tables injected into the SQL prompt (fast-pathed for single-table sessions)
- **Grounded routing** — router probes the PDF vector store with the actual question before routing, so decisions are based on retrieved content, not keyword matching

**Measured latency (per-stage instrumentation):**
- SQL-only route: ~1.7s end-to-end
- RAG-only route: ~2.3s end-to-end
- Combined routes: 4–7s (two sequential pipelines + synthesis)
- SQL generation: ~800–1000ms after switching Gemini models (~3x speedup over baseline)

**Stack:** Python · FastAPI · LangGraph · LangSmith · Gemini API (`gemini-embedding-001`, `gemini-2.0-flash`) · ChromaDB · SQLite · sqlglot · React 18 · TypeScript · TailwindCSS · Vite · bcrypt · pypdf

---

### [Distributed File Sharing System](./Distributed-P2P-File-Transfer-main) — BitTorrent-Inspired P2P in C++

Peer-to-peer file sharing system with a centralized tracker for peer discovery and decentralized file transfer.

**How it works:**
- Centralized tracker maintains a registry of peers, groups, and file metadata (SHA1-keyed, `unordered_map`-backed)
- Clients download files in chunks from multiple peers simultaneously using multithreading and TCP sockets
- Rarest-first chunk selection prioritizes scarce chunks to improve swarm health
- SHA-1 integrity verification on every chunk; corrupt chunks are re-requested

**Stack:** C++ · Socket Programming · POSIX · Multithreading · SHA-1

---

### [POSIX Shell](./POSIX-Shell-main) — Unix Shell in C++

A POSIX-compliant shell supporting the full lifecycle of process management and I/O control.

**Implemented:** command execution, piping, I/O redirection, foreground/background process management, job control via process groups, signal handling (`SIGINT`, `SIGTSTP`), command history with arrow-key navigation, tab autosuggestion, and `ls`/`cd`/`echo`/`pinfo` builtins.

**Stack:** C++ · POSIX APIs (`fork`, `exec`, `pipe`, `wait`) · Linux syscalls · STL

---

### ML & NLP Projects (M.Tech @ IIIT Hyderabad)

| Project | What it does | Stack |
|---|---|---|
| **[POS Tagging](./Neural%20POS%20Tagging%20Pytorch)** | FFNN and LSTM trained on CoNLL-U for Part-of-Speech tagging; hyperparameter tuning + evaluation metrics | PyTorch · NumPy |
| **Semantic Textual Similarity** | Sentence similarity scoring using BERT and Siamese LSTM on STS + SICK datasets | PyTorch · HuggingFace Transformers |
| **[Background Subtraction](./ML_Background_subtraction)** | Custom GMM from scratch (EM algorithm, per-pixel multivariate Gaussians) for video foreground/background segmentation | NumPy · OpenCV · scikit-learn |
| **[Face Recognition](./ML_face_recognition_using%20_PCA)** | PCA-based Eigenfaces implementation from scratch; face recognition via Euclidean distance in eigenspace on AT&T dataset | NumPy · scikit-learn |
| **MNIST Denoising Autoencoder** | Convolutional autoencoder for image denoising | PyTorch |

---

## Tech Stack

**Languages:** Python · C++ · SQL · TypeScript

**AI / LLM:** LangGraph · LangSmith · Gemini API · ChromaDB · RAG · Text-to-SQL · Prompt Engineering · Agentic Workflows · OpenAI API · PyTorch · Hugging Face

**Backend:** FastAPI · REST APIs · SQLite · MySQL · Docker · bcrypt · Pydantic

**Frontend:** React 18 · TypeScript · TailwindCSS · Vite · Axios

**Core CS:** Data Structures & Algorithms · OOP · Distributed Systems · Socket Programming · System Design · Process Management

**DSA:** LeetCode rating 1492 · 590+ problems solved

---

*Humans invented distributed systems just to spend decades debugging distributed systems. I participate in this tradition professionally now.*
