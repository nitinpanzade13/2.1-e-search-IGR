# Maharashtra IGR e-Search Database Architecture

## Overview
This document outlines the database foundation designed for the Maharashtra state-wide IGR e-Search platform. The architecture emphasizes robust separation of concerns, data immutability, explicit lineage, and configurability for future state-level scaling.

## Canonical Identity
- **Internal Database Identity**: All tables use **UUIDs** as primary keys to ensure global uniqueness and prevent collisions during distributed imports.
- **Source Identity**: While `source_token` (the decoded Index II URL token) and `(office_id, doc_no, year)` are strong candidates for natural keys, we intentionally do NOT enforce strict `UNIQUE` constraints yet. This prevents destructive deduplication until we empirically validate the uniqueness properties of the IGR source system at a state-wide level.

## Location Hierarchy
- Modeled strictly as `State` -> `District` -> `Taluka` -> `Village`.
- Canonical database location IDs are entirely separate from IGR source IDs. We preserve the source IDs (`source_id` / `igr_code`) because the source system may alter location configurations over time.

## Search Scope vs Property Location
- Search locations are strictly parameters used by a `SearchJob`.
- The actual `Property` location is parsed from the Index II PDF. A document discovered in a specific village's search may contain properties in other villages or lack structured village information altogether. The schema preserves this distinction (property location is not automatically inherited from the search job).

## Offices (SROs)
- Offices are modeled as independent entities (`offices`) rather than mere attributes of a Village. An SRO (Sub-Registrar Office) often serves multiple villages. 

## Raw Source Preservation & Processing Lineage
- **Immutability**: Raw source responses (HTML pages and Index II PDFs) are modeled as durable `Artifacts`.
- **Decoupled Parsing**: Parsing is treated as a separate lifecycle event (`ParserRun`). If parsing logic is updated (e.g., improved regex for Marathi addresses), the exact source artifact can be re-parsed without incurring new network requests to the IGR portal.

## Scale and Job Management
- The schema is designed for Maharashtra-wide operation. `IngestionRun` groups millions of `SearchJob` records. 
- `SearchJob` incorporates a 5000-record cap detection (`truncated` boolean) indicating whether sub-partitioning (e.g., by survey prefix) is necessary.
- `PdfTask` manages the independent retrieval of PDF files for each discovered registration.

## Network & Source Request Ledger
- The IGR portal enforces severe IP-based quotas. We model every outbound request in `SourceRequestLedger`.
- This ensures we have a precise audit trail of what was requested, when, with what IP context, and if a rate-limit page was encountered.
- **Future Integration**: The implementation of `netswitch.py` (or any proxy rotation logic) will act as a `NetworkProvider` controlled by a `SourceAccessManager`, remaining completely separate from the domain schema.
