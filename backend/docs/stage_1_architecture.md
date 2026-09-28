# Maharashtra IGR e-Search: Stage 1 Architecture

## A. Current Project Assessment
The new project (`2.1 e-search IGR/backend`) is a FastAPI/Python application utilizing SQLAlchemy and Alembic. The database foundation has been rigorously structured to separate immutable source artifacts, request auditing (ledger), and processing lineage from the core domain entities (Registrations, Jobs). 

Currently, the `app/scraper` directory contains initial implementations (`client.py`, `igr_parser.py`, `solver.py`, `scrape_result.py`). These components loosely encapsulate the IGR HTML parsing, HTTP session, and CAPTCHA solving. However, they are currently tightly coupled. This architecture will evolve them into an independent, queue-driven worker topology managed by a robust `SourceAccessManager`.

## B. Legacy Flow Mapping
The legacy `2.1-script-main` codebase will be mapped to the new components as follows:
* `scrape.py` → **SearchJobCoordinator** & **SearchWorker**
* `session.py` / `portal.py` → **IgrSearchClient** (HTTP boundary)
* `netswitch.py` → **NetworkProvider**
* `captcha_solver.py` → **CaptchaProvider**
* `igr_parser.py` → **ResponseClassifier** & **PureHtmlParser**
* `fetch_properties.py` / CSV writing → **ArtifactStore** & **Persistence/IdentityResolver**

## C. Stage 1 Component Architecture
```text
  SearchJobCoordinator (Monitors IngestionRuns, spawns Jobs)
           ↓
     SearchWorker (Executes the Job lifecycle)
           ↓
  SourceAccessManager (Admission & Quota Control)
           ↓
   IgrSearchClient (Session, CSRF, HTTP Post)
           ↓
  ResponseClassifier (Detects Success, CAPTCHA fail, Rate Limit)
           ↓
    ArtifactStore (Durable HTML storage)
           ↓
   PureHtmlParser (No side-effects, extracts DTOs)
           ↓
 IdentityResolver (Matches candidates, decides Upsert/Insert)
           ↓
      PostgreSQL (via SQLAlchemy Repositories)
```
*(Note: `NetworkProvider` sits behind the `SourceAccessManager` and is only invoked when network context changes are required.)*

## D. Responsibility Matrix
| Component | Responsibility | Inputs | Outputs | MUST NOT |
| :--- | :--- | :--- | :--- | :--- |
| **SearchWorker** | Orchestrates the end-to-end search pipeline for a single `SearchJob`. | `SearchJob` | DB Updates | Directly invoke HTTP/Network. |
| **SourceAccessManager** | Acts as a gateway. Blocks workers if quota exhausted, triggers network rotation. | Request intents | `acquire()` token | Parse HTML or read DB domain logic. |
| **NetworkProvider** | Modifies underlying OS network state to rotate IP. | Rotate command | New Context Info | Know about IGR searches. |
| **IgrSearchClient** | Handles HTTP sessions, cookies, CSRF extraction, Captcha fetching, POST search. | Payload DTOs | Raw HTTP Response | Access the Database. |
| **ResponseClassifier** | Inspects HTTP response to determine outcome (`SUCCESS`, `RATE_LIMITED`, etc.) | HTTP Response | Classification Enum | Throw fatal errors for known bad states. |
| **ArtifactStore** | Writes raw bytes to persistent storage (Disk/S3). | Raw Bytes | `storage_path` | Modify the data. |
| **PureHtmlParser** | Extracts `tableparty` rows into `SearchResultDTO`. | HTML Bytes | List[`SearchResultDTO`] | Perform I/O or network requests. |
| **IdentityResolver** | Resolves DTOs against existing registrations to prevent destructive duplicates. | `SearchResultDTO` | Persisted Models | Make silent destructive merges. |

## E. Data Flow

**1. Successful Search**
```text
SearchJob
   ↓
SourceAccessManager.acquire()
   ↓
Create SourceRequestLedger row (request_started_at)
   ↓
IgrSearchClient executes HTTP POST
   ↓
Update SourceRequestLedger (completed_at, status, duration)
   ↓
ResponseClassifier detects SUCCESS
   ↓
ArtifactStore saves raw HTML and returns artifact_id
   ↓
PureHtmlParser extracts DTOs
   ↓
ParserRun created (SUCCESS)
   ↓
IdentityResolver analyzes DTOs vs Candidates
   ↓
Registration persistence (Insert/Soft Upsert)
   ↓
PdfTask creation
   ↓
SearchJob ➔ COMPLETED
```

**2. CAPTCHA Failure & Retry Model**
There are distinct, bounded counters for `captcha_attempt_count` and `search_attempt_count`.
If ResponseClassifier detects "Invalid CAPTCHA":
1. `CAPTCHA_FAILED` returned.
2. `captcha_attempt_count` increments.
3. If `< max_captcha_retries`, worker requests a new CAPTCHA and retries.
4. If `>= max_captcha_retries`, the current `search_attempt` fails.
5. `search_attempt_count` increments.
6. If `< max_search_retries`, the job requeues. Otherwise, `SearchJob` ➔ `FAILED`.
*(Note: Every search POST attempt, including CAPTCHA failures, updates its respective `SourceRequestLedger` entry).*

**3. Rate-Limited Search & Network Provider Flow**
Under normal operations, no network context changes occur. 
If ResponseClassifier detects "exceeded the limit" (RATE_LIMITED):
1. Ledger is updated with `rate_limited=True`.
2. Job is marked `RATE_LIMITED`.
3. `SourceAccessManager` state shifts to `EXHAUSTED` then `NETWORK_CHANGE_REQUIRED`.
4. Admission is paused; running/queued jobs wait.
5. `SourceAccessManager` invokes `NetworkProvider.change_context()`.
6. Upon connectivity validation, state shifts to `RECOVERING` ➔ `AVAILABLE`.
7. Interrupted `RATE_LIMITED` jobs revert to `QUEUED` and are cleanly retried. 
*(Workers NEVER invoke `netswitch.py` or Wi-Fi controls directly).*

**4. Parser Failure**
If parser logic crashes or raises an exception:
1. The raw HTML is **already persisted** as an `Artifact`.
2. A `ParserRun` is recorded as `FAILED`.
3. `SearchJob` ➔ `FAILED` (or retried per policy).
4. **No data is lost**. A future parser update can safely re-process the exact `Artifact` without repeating the IGR request.

## F. Attempt & Recovery Model
The system distinctly tracks lifecycle attempts:
* **SearchJob**: Represents the high-level intent. It can span multiple search attempts.
* **HTTP Request Attempt**: Represented uniquely in the `SourceRequestLedger`.
* **CAPTCHA Attempt**: A sub-retry loop within a single HTTP request setup.
* **Parser Attempt**: Tracked as a `ParserRun` against an `Artifact`.

If a worker crashes mid-flight (e.g. Ledger row created but HTTP request unfinished), the Ledger row remains incomplete (lacking `completed_at`). A recovery sweep can flag these as `ABANDONED/CRASHED`, and the `SearchJob` (still `RUNNING`) will eventually time out and revert to `QUEUED`.

## G. Request Ledger Lifecycle
The `SourceRequestLedger` represents an **outbound request attempt**, not merely a successful one.
The lifecycle is:
1. Intent to search.
2. **CREATE Ledger Row** (record `request_started_at`, `job_id`, `endpoint`).
3. HTTP request begins.
4. Response, Timeout, or Exception occurs.
5. **UPDATE Ledger Row** (record `completed_at`, `duration_ms`, `http_status`, `rate_limited`, `failure_category`, etc.).
6. If response bytes exist, create `Artifact` and link `artifact_id`.

## H. Identity Resolution
**CRITICAL**: `source_token` and `(office_id, doc_no, year)` are **CANDIDATE IDENTITIES**. They are not yet proven globally unique across the state. The internal UUID is the only canonical identity.

The `IdentityResolver` operates as follows:
1. Search by candidate `source_token`.
2. Search by candidate `(office_id, doc_no, year)`.
3. Evaluate match evidence.
4. Decision: `EXISTING_CONFIRMED`, `NEW_REGISTRATION`, `POSSIBLE_DUPLICATE`, or `AMBIGUOUS`.

The policy is strictly conservative: **NO DESTRUCTIVE DEDUPLICATION**. If there is insufficient evidence to safely merge records, a new Registration is created. We will not silently overwrite distinct records just because an upstream identifier collided.

## I. State Machines

**SearchJob**
```text
QUEUED
  ↓
RUNNING
  ├── COMPLETED
  ├── TRUNCATED
  ├── RATE_LIMITED
  │      ↓
  │   QUEUED (Recovery State)
  └── FAILED (Exhausted retries)
```

**SourceAccessManager**
```text
AVAILABLE ➔ EXHAUSTED ➔ NETWORK_CHANGE_REQUIRED ➔ RECOVERING ➔ AVAILABLE
```

## J. 5000-Result Cap Strategy (Truncation)
The `ResponseClassifier` extracts the "5000 Records found" string. If `reported_count >= 5000` or `retrieved_count == 5000`, the `SearchWorker` marks the `SearchJob` as `TRUNCATED`. Stage 1 **will not** attempt to partition or fix this automatically. It simply flags the boundary for a future partitioning coordinator to handle.

## K. Testing Strategy
* **Unit Tests**: Pass local static HTML fixtures (e.g., `test_response_2026_1.html`) into the `PureHtmlParser` to verify robust Marathi text extraction and row logic.
* **Mocked Clients**: Test the `SourceAccessManager` and `SearchWorker` by injecting a mock `IgrSearchClient` that simulates returning `RATE_LIMITED` on the 6th call, asserting that network rotation is properly requested.
* **No real HTTP requests** to the IGR portal will be executed during CI/automated test runs.

## L. Implementation Plan
* **Stage 1A** — Define Data Transfer Objects (DTOs) and Domain Exceptions.
* **Stage 1B** — Implement `IgrSearchClient` & `CaptchaProvider` boundaries.
* **Stage 1C** — Implement `ResponseClassifier`.
* **Stage 1D** — Implement `ArtifactStore` and `PureHtmlParser`.
* **Stage 1E** — Implement `IdentityResolver` and Repositories.
* **Stage 1F** — Implement `SourceAccessManager` & mock `NetworkProvider`.
* **Stage 1G** — Implement `SearchWorker` orchestration.
* **Stage 1H** — Controlled integration test against IGR portal (Single Request).

## M. Design Invariants
1. Internal UUID is the canonical database identity.
2. `source_token` is a candidate identity, not yet a proven unique key.
3. `(office_id, doc_no, year)` is a candidate identity, not a proven unique key.
4. **No destructive deduplication.**
5. Every outbound source request has a ledger attempt record created *before* the request fires whenever practical.
6. Raw HTML is durably persisted *before* parsing begins.
7. Parser failures never delete or rollback raw artifacts.
8. CAPTCHA retries are bounded and separate from search retries.
9. Search retries are bounded.
10. Rate limits never cause tight retry loops (they trigger admission control).
11. `SearchWorker` never directly controls or interacts with the OS network/IP state.
12. Network changes happen strictly and only through `NetworkProvider`.
13. Stage 1 discovery never assumes or parses PDF-only fields (e.g. market value).
14. Stage 1 never assumes or implements the 5000-result survey partitioning strategy automatically.
15. No real source HTTP requests occur in automated test suites.
