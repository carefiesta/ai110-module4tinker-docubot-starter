# DocuBot Model Card

This model card is a short reflection on your DocuBot system. Fill it out after you have implemented retrieval and experimented with all three modes:

1. Naive LLM over full docs  
2. Retrieval only  
3. RAG (retrieval plus LLM)

Use clear, honest descriptions. It is fine if your system is imperfect.

---

## 1. System Overview

**What is DocuBot trying to do?**  
Describe the overall goal in 2 to 3 sentences.

> DocuBot is a small helper that answers questions about a project's documentation. It can search the docs folder, return the most relevant snippets, and optionally ask a language model to write an answer using only those snippets. If the docs do not support an answer, it should say that it does not know instead of guessing.

**What inputs does DocuBot take?**  
For example: user question, docs in folder, environment variables.

> It takes a developer question and the `.md` and `.txt` files in the `docs/` folder. Modes 1 and 3 also need a `GEMINI_API_KEY` so the language model can run.

**What outputs does DocuBot produce?**

> Retrieval only mode prints the top matching snippets and their filenames. Naive LLM mode and RAG mode print a written answer. If no snippet is strong enough, DocuBot returns "I do not know based on these docs."

---

## 2. Retrieval Design

**How does your retrieval system work?**  
Describe your choices for indexing and scoring.

- How do you turn documents into an index?
- How do you score relevance for a query?
- How do you choose top snippets?

> I lowercase the text, replace punctuation with spaces, and drop common stopwords. `build_index` makes a simple inverted index that maps each remaining word to the document filenames it appears in. `score_document` counts how many unique query words also appear in a piece of text. Before scoring, I split each document into paragraph snippets on blank lines and skip very short pieces such as a heading by itself. `retrieve` uses the index to find candidate files, scores the paragraphs in those files, drops any snippet below a minimum score of 1, and returns the top 3 by score.

**What tradeoffs did you make?**  
For example: speed vs precision, simplicity vs accuracy.

> I kept the design simple and easy to explain, instead of using ranking methods such as TF-IDF or embeddings. That made the code easy to test, but exact word matching can miss useful text when the query uses a slightly different form of a word, like "connect" versus "connection." Splitting on blank lines also sometimes separates a heading from the paragraph that actually answers the question.

---

## 3. Use of the LLM (Gemini)

**When does DocuBot call the LLM and when does it not?**  
Briefly describe how each mode behaves.

- Naive LLM mode:
- Retrieval only mode:
- RAG mode:

> Naive LLM mode sends the question to Gemini and does not use the retrieval index. In the starter code, this mode does not even include the docs in the prompt, so the model answers from general knowledge. Retrieval only mode never calls the model. It just returns the ranked snippets, or a refusal if none of them meet the minimum score. RAG mode runs retrieval first. If snippets are found, Gemini answers using only those snippets. If retrieval returns nothing, RAG refuses without calling the model.

**What instructions do you give the LLM to keep it grounded?**  
Summarize the rules from your prompt. For example: only use snippets, say "I do not know" when needed, cite files.

> The RAG prompt tells the model to use only the retrieved snippets, not to invent functions, endpoints, or configuration values, to reply "I do not know based on the docs I have." when the snippets are not enough, and to mention which files it used when it does answer.

---

## 4. Experiments and Comparisons

Run the **same set of queries** in all three modes. Fill in the table with short notes.

You can reuse or adapt the queries from `dataset.py`.

| Query | Naive LLM: helpful or harmful? | Retrieval only: helpful or harmful? | RAG: helpful or harmful? | Notes |
|------|---------------------------------|--------------------------------------|---------------------------|-------|
| Where is the auth token generated? | Harmful or incomplete. It asked for a codebase and did not use AUTH.md. | Helpful, but raw. It returned the `generate_access_token` paragraph from AUTH.md along with two other token snippets. | Helpful. It clearly said the token is created by `generate_access_token` in `auth_utils.py` and cited AUTH.md. | This is the best example of RAG being clearer than raw snippets. |
| How do I connect to the database? | Harmful. It sounded sure and suggested `DB_HOST`, `DB_PORT`, Prisma, and Mongoose, which are not in these docs. | Helpful but incomplete. The snippets were from DATABASE.md and mentioned SQLite, PostgreSQL, and `db.py`, but the `DATABASE_URL` paragraph was not in the top 3. | Helpful. It summarized that `db.py` handles connecting and that local development uses SQLite, with PostgreSQL in production, and cited DATABASE.md. | Naive mode invented setup steps that do not match this project. |
| Which endpoint returns all users? | Harmful or weakly grounded. It asked for more context and then guessed an example like `GET /api/v1/users`. | Partly helpful. The first snippet correctly said "Returns a list of all users. Only accessible to admins," but it did not include the `/api/users` path. | Failed in a careful way. It refused to name a URL because the snippets never showed the path. | The path is in API_REFERENCE.md, but it was split onto a nearby heading, so both retrieval and RAG missed it. |
| What is the capital of France? | Harmful for this tool. It confidently answered "Paris," which is not in the docs. | Helpful as a refusal. It said "I do not know based on these docs." | Helpful as a refusal. Same message, because no snippet met the minimum score. | This shows why a guardrail matters. |
| How do I deploy to Kubernetes? | Harmful. It wrote a long deployment guide even though the docs never mention Kubernetes. | Helpful as a refusal. It said it does not know based on these docs. | Helpful as a refusal. Same as retrieval only, with no model call. | Naive mode will answer questions the docs cannot support. |

**What patterns did you notice?**  

- When does naive LLM look impressive but untrustworthy?  
- When is retrieval only clearly better?  
- When is RAG clearly better than both?

> Naive mode looks impressive on questions like connecting to a database or deploying to Kubernetes, but those answers are not tied to this project's docs. Retrieval only is clearly better on off-topic questions, because it refuses instead of guessing, and it is also accurate on the auth-token question, even if the raw snippets are harder to read. RAG is clearly better when the right snippet is retrieved, like the auth-token question, because it turns those fragments into a short answer and names the file it used.

---

## 5. Failure Cases and Guardrails

**Describe at least two concrete failure cases you observed.**  
For each one, say:

- What was the question?  
- What did the system do?  
- What should have happened instead?

> Failure case 1: For "Which endpoint returns all users?", retrieval returned the sentence about returning all users but not the `GET /api/users` heading, which had been split into a different snippet. RAG then said it did not know the specific URL. It should have returned the path `/api/users`, which is in API_REFERENCE.md.

> Failure case 2: For "How do I connect to the database?", naive mode gave generic advice using environment variables and tools that are not in the docs. Even in retrieval and RAG, the best `DATABASE_URL` paragraph did not rank in the top 3 because the query word "connect" does not exactly match "connection." The system should have surfaced the `DATABASE_URL` instructions more clearly.

**When should DocuBot say “I do not know based on the docs I have”?**  
Give at least two specific situations.

> It should refuse when the question is not covered by the docs at all, such as "What is the capital of France?" or "How do I deploy to Kubernetes?" It should also refuse when a query has no meaningful keyword overlap with any snippet, like asking about payment processing, which these docs never mention.

**What guardrails did you implement?**  
Examples: refusal rules, thresholds, limits on snippets, safe defaults.

> A snippet must share at least one non-stopword with the query, or it is not returned. If no snippet meets that minimum score, `retrieve()` returns an empty list, and both retrieval-only mode and RAG mode print that they do not know. RAG also tells the model not to invent details and to refuse when the snippets are not enough. I also drop very short heading-only snippets so they do not take the place of real paragraphs.

---

## 6. Limitations and Future Improvements

**Current limitations**  
List at least three limitations of your DocuBot system.

1. Scoring uses exact word overlap, so related words like "connect" and "connection" or "endpoint" and "endpoints" are not treated as a match.
2. Splitting on blank lines can separate a heading from the paragraph that contains the real answer, which hid the `/api/users` path.
3. The simple score can tie many paragraphs at 1, so a useful sentence such as the `DATABASE_URL` line may fall outside the top 3.

**Future improvements**  
List two or three changes that would most improve reliability or usefulness.

1. Keep a markdown heading with the paragraph that follows it, so endpoint paths stay attached to the description.
2. Use a slightly smarter score, such as counting word stems or giving extra weight to exact phrases like `/api/users`.
3. Show the numeric score next to each snippet so it is easier to see why a weak match was returned.

---

## 7. Responsible Use

**Where could this system cause real world harm if used carelessly?**  
Think about wrong answers, missing information, or over trusting the LLM.

> A developer might follow a confident but wrong answer about authentication or database setup and misconfigure a real system. Naive mode is especially risky because it can invent endpoints, environment variables, or tools that are not in the project. Missing a real endpoint path, like `/api/users`, could also send someone to the wrong place.

**What instructions would you give real developers who want to use DocuBot safely?**  
Write 2 to 4 short bullet points.

- Treat every answer as a pointer back to the docs, and open the cited file before you rely on it.
- Prefer retrieval only or RAG over naive generation, and do not trust an answer that does not name its source.
- If DocuBot says it does not know, check the docs yourself instead of asking the model to guess.
- Remember that a fluent answer can still be incomplete if retrieval missed part of the page.

---
