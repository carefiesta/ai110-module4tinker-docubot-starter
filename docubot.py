"""
Core DocuBot class responsible for:
- Loading documents from the docs/ folder
- Building a simple retrieval index (Phase 1)
- Retrieving relevant snippets (Phase 1)
- Supporting retrieval only answers
- Supporting RAG answers when paired with Gemini (Phase 2)
"""

import os
import glob
import string

# Words that show up in almost every question or sentence, so they
# are not useful when we try to match a query to a document.
STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for",
    "is", "are", "was", "were", "be", "been", "being", "it", "its",
    "this", "that", "these", "those", "i", "you", "we", "they",
    "he", "she", "my", "your", "our", "how", "what", "where", "when",
    "which", "who", "why", "do", "does", "did", "can", "could",
    "should", "would", "will", "with", "from", "at", "by", "as",
    "if", "not", "no", "all", "any", "about", "into", "than",
    "there", "mention", "docs", "doc", "document", "documentation",
}


def tokenize(text):
    """
    Lowercase the text, replace punctuation with spaces, and drop
    common stopwords. Returns a list of remaining words.
    """
    cleaned = text.lower()
    for mark in string.punctuation:
        cleaned = cleaned.replace(mark, " ")

    words = []
    for word in cleaned.split():
        if word and word not in STOPWORDS:
            words.append(word)
    return words


# A snippet must overlap the query by at least this many words,
# otherwise retrieve() returns nothing and the answer methods refuse.
MIN_SCORE = 1


def split_into_snippets(documents):
    """
    Split each document into paragraph snippets on blank lines.
    Each snippet keeps the filename it came from.
    """
    snippets = []
    for filename, text in documents:
        for part in text.split("\n\n"):
            cleaned = part.strip()
            # Skip empty or very short pieces such as a heading alone
            if cleaned and len(cleaned.split()) >= 5:
                snippets.append((filename, cleaned))
    return snippets


class DocuBot:
    def __init__(self, docs_folder="docs", llm_client=None):
        """
        docs_folder: directory containing project documentation files
        llm_client: optional Gemini client for LLM based answers
        """
        self.docs_folder = docs_folder
        self.llm_client = llm_client

        # Load documents into memory
        self.documents = self.load_documents()  # List of (filename, text)

        # Split each document into smaller paragraph snippets
        self.snippets = split_into_snippets(self.documents)

        # Build a retrieval index (implemented in Phase 1)
        self.index = self.build_index(self.documents)

    # -----------------------------------------------------------
    # Document Loading
    # -----------------------------------------------------------

    def load_documents(self):
        """
        Loads all .md and .txt files inside docs_folder.
        Returns a list of tuples: (filename, text)
        """
        docs = []
        pattern = os.path.join(self.docs_folder, "*.*")
        for path in glob.glob(pattern):
            if path.endswith(".md") or path.endswith(".txt"):
                with open(path, "r", encoding="utf8") as f:
                    text = f.read()
                filename = os.path.basename(path)
                docs.append((filename, text))
        return docs

    # -----------------------------------------------------------
    # Index Construction (Phase 1)
    # -----------------------------------------------------------

    def build_index(self, documents):
        """
        Build a tiny inverted index mapping lowercase words to the
        documents they appear in.

        Example structure:
        {
            "token": ["AUTH.md", "API_REFERENCE.md"],
            "database": ["DATABASE.md"]
        }

        Split on whitespace, lowercase tokens, and ignore punctuation.
        """
        index = {}
        for filename, text in documents:
            for word in tokenize(text):
                if word not in index:
                    index[word] = []
                if filename not in index[word]:
                    index[word].append(filename)
        return index

    # -----------------------------------------------------------
    # Scoring and Retrieval (Phase 1)
    # -----------------------------------------------------------

    def score_document(self, query, text):
        """
        Return a simple relevance score for how well the text matches
        the query.

        The score is the number of unique query words that also appear
        in the text. Stopwords and punctuation are ignored.
        """
        query_words = set(tokenize(query))
        text_words = set(tokenize(text))
        score = 0
        for word in query_words:
            if word in text_words:
                score += 1
        return score

    def retrieve(self, query, top_k=3):
        """
        Use the index and scoring function to select top_k relevant
        paragraph snippets.

        Return a list of (filename, text) sorted by score descending.
        If no snippet meets MIN_SCORE, return an empty list so the
        answer methods can say they do not know.
        """
        query_words = set(tokenize(query))

        # Use the index to find documents that share at least one word
        # with the query, so we do not score every file blindly.
        candidate_files = set()
        for word in query_words:
            for filename in self.index.get(word, []):
                candidate_files.add(filename)

        results = []
        for filename, text in self.snippets:
            if candidate_files and filename not in candidate_files:
                continue
            score = self.score_document(query, text)
            # Guardrail: skip snippets that do not overlap the query enough
            if score >= MIN_SCORE:
                results.append((score, filename, text))

        results.sort(key=lambda item: item[0], reverse=True)
        return [(filename, text) for score, filename, text in results[:top_k]]

    # -----------------------------------------------------------
    # Answering Modes
    # -----------------------------------------------------------

    def answer_retrieval_only(self, query, top_k=3):
        """
        Phase 1 retrieval only mode.
        Returns raw snippets and filenames with no LLM involved.
        """
        snippets = self.retrieve(query, top_k=top_k)

        if not snippets:
            return "I do not know based on these docs."

        formatted = []
        for filename, text in snippets:
            formatted.append(f"[{filename}]\n{text}\n")

        return "\n---\n".join(formatted)

    def answer_rag(self, query, top_k=3):
        """
        Phase 2 RAG mode.
        Uses student retrieval to select snippets, then asks Gemini
        to generate an answer using only those snippets.
        """
        if self.llm_client is None:
            raise RuntimeError(
                "RAG mode requires an LLM client. Provide a GeminiClient instance."
            )

        snippets = self.retrieve(query, top_k=top_k)

        if not snippets:
            return "I do not know based on these docs."

        return self.llm_client.answer_from_snippets(query, snippets)

    # -----------------------------------------------------------
    # Bonus Helper: concatenated docs for naive generation mode
    # -----------------------------------------------------------

    def full_corpus_text(self):
        """
        Returns all documents concatenated into a single string.
        This is used in Phase 0 for naive 'generation only' baselines.
        """
        return "\n\n".join(text for _, text in self.documents)
