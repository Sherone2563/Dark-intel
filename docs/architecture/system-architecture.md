
# Dark Intel — System Architecture

## 1. Purpose

Dark Intel is a research-oriented threat-intelligence platform for
entity resolution, potential persona linkage, relationship analysis,
temporal investigation, and evidence-backed attribution assessment.

The platform supports authorized public cyber-threat-intelligence
sources, historical research datasets, and controlled or sanitized
academic data. It does not guarantee real-person identification or
deanonymization.

## 2. Core Evidence Principle

Every analytical conclusion must be traceable through:

Source → Observation → Entity → Relationship → Evidence
→ Analysis → Confidence Assessment → Intelligence Report

Raw source material must remain distinguishable from normalized
records, inferred relationships, and analyst conclusions.

## 3. High-Level Data Flow

1. Authorized source or research dataset
2. Collection and ingestion
3. Raw evidence preservation and integrity metadata
4. Parsing and normalization
5. Entity and identifier extraction
6. Candidate generation and entity resolution
7. Relationship and temporal analysis
8. Evidence-backed confidence assessment
9. Analyst-facing investigation interface
10. Intelligence report generation

## 4. Component Responsibilities

### Backend API
FastAPI endpoints, request validation, orchestration, and access control.

### Collectors
Adapters for authorized sources and approved research datasets.

### Intelligence Processing
Parsing, normalization, feature extraction, and evidence preparation.

### Entity Resolution
Candidate matching, explainable feature comparison, contradiction
handling, and analyst-reviewable linkage assessments.

### Graph Analysis
Relationships among handles, identifiers, posts, listings, sources,
and other supported entities.

### Data Layer
PostgreSQL for structured records and provenance.
Neo4j for relationship-oriented queries.
Raw evidence storage is logically separate from analytical records.

### Frontend
Search, entity profiles, evidence inspection, relationship graphs,
timelines, and report review.

### Workers
Background ingestion and processing tasks, with retry and audit handling.

## 5. Initial Entity Types

- ACTOR
- HANDLE
- PGP_KEY
- WALLET
- EMAIL
- DOMAIN
- IP
- ONION_SERVICE
- MARKETPLACE
- FORUM
- SERVICE
- POST
- LISTING
- SOURCE
- OBSERVATION
- EVIDENCE

Only entities supported by the source data should be created.

## 6. Provenance and Integrity

An observation should retain, where available:

- Stable observation identifier
- Source identifier and source reference
- Collection timestamp
- Original event timestamp, if known
- Normalized entity references
- Evidence references
- Source reliability assessment
- Content integrity hash
- Parser and processing version
- Processing history and errors

Preserve original timestamps and distinguish them from ingestion time.
Do not silently overwrite source evidence during normalization.

## 7. Entity Resolution and Confidence

Candidate linkage assessments should expose:

- Candidate entities and identifiers
- Supporting signals
- Contradictory signals
- Missing or unavailable evidence
- Source reliability and evidence quality
- Scoring method and version
- Final score and interpretation
- Analyst review status

A similarity score is not a probability of real-world identity.
Confidence bands must be calibrated against documented evaluation data
before being described as calibrated confidence.

Similar handles alone must not trigger automatic entity merging.

## 8. Security and Research Boundaries

- Use authorized sources and approved datasets.
- Keep credentials outside version control.
- Restrict access to sensitive research material.
- Minimize personal data and retain only what is justified.
- Record provenance and processing history.
- Do not treat analytical association as proof of identity.
- Require human review for consequential attribution conclusions.

## 9. Initial Implementation Sequence

1. Backend skeleton and health endpoint
2. Automated backend tests
3. Structured source and observation schemas
4. Database integration and migrations
5. Research-dataset ingestion
6. Entity extraction and normalization
7. Explainable candidate-linkage engine
8. Relationship and timeline queries
9. Graph database integration
10. Frontend investigation workflow
11. Evidence-backed report generation
12. Evaluation, security checks, and documentation

## 10. Initial Acceptance Criteria

The initial backend must start successfully, expose a health endpoint,
and pass automated tests.

Subsequent features are accepted only when their behavior is tested
and their analytical output can be traced to recorded evidence.