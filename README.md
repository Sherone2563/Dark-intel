
# Dark Intel

**Evidence-Backed Threat Intelligence, Entity Resolution and Attribution Assessment**

Dark Intel is a research-oriented threat-intelligence platform designed to organize authorized cyber-threat-intelligence data, identify relationships between entities, preserve evidence provenance, and support analyst-led attribution assessment.

The project focuses on explainable, evidence-backed analytical linkage rather than claiming guaranteed real-world identity identification or deanonymization.

## Project Objectives

- Ingest authorized public CTI sources and approved research datasets.
- Preserve observations with timestamps and integrity metadata.
- Extract and normalize entities from ingested observations.
- Identify potential relationships between entities.
- Generate explainable handle-matching candidates.
- Analyze supporting, contradicting and neutral evidence.
- Preserve source and observation provenance.
- Investigate entities through relationship graphs and timelines.
- Generate structured intelligence reports.
- Monitor ingestion and processing activity.

## Core Intelligence Workflow

```text
Authorized Source
       |
       v
   Observation
       |
       v
 Entity Extraction
       |
       v
     Entity
       |
       v
  Relationship
       |
       v
     Evidence
       |
       v
  Linkage Analysis
       |
       v
Confidence Assessment
       |
       v
 Intelligence Report
```

Raw observations, extracted entities, analytical relationships and analyst conclusions remain distinct.

## Implemented Features

### Backend and Data Management
- FastAPI REST API.
- PostgreSQL persistence using SQLAlchemy.
- Alembic database migrations.
- Source, entity, observation, relationship and evidence management.
- Source authorization checks for ingestion.
- Observation SHA-256 integrity hashes.
- Collection and observation timestamps.
- Processing-version metadata.

### Entity Resolution
- Handle candidate matching.
- Similarity-based candidate generation.
- Read-only candidate results.
- No automatic merging of similar entities.

### Evidence and Analysis
- Supporting, contradicting and neutral evidence.
- Evidence-backed relationship analysis.
- Observation and source-quality diagnostics.
- Distinct source and observation counts.
- Confidence eligibility checks based on qualifying source reliability.

### Investigation and Reporting
- Entity investigation endpoint.
- Entity relationship graph responses.
- Chronological investigation timelines.
- Entity provenance records.
- Intelligence report generation.

### Monitoring
- Processing-run records.
- Monitoring summaries.
- Processing diagnostics.
- Processing status and ingestion visibility.

### Frontend
- Overview workspace.
- Assets workspace.
- Intelligence workspace.
- Monitoring workspace.
- Alerts workspace.
- Entity investigation, graph, timeline and report views.

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | React, TypeScript, Vite |
| Styling | Tailwind CSS |
| Backend | Python, FastAPI |
| Database | PostgreSQL 17 |
| ORM | SQLAlchemy |
| Migrations | Alembic |
| API validation | Pydantic / FastAPI |
| Testing | Pytest |
| Frontend validation | ESLint, TypeScript |
| Containerization | Docker Compose |

## Repository Structure

```text
Dark-Intel/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── cli/
│   │   ├── core/
│   │   ├── models/
│   │   └── services/
│   ├── alembic/
│   └── tests/
├── frontend/
│   └── src/
│       └── components/
├── collectors/
├── configs/
├── database/
├── datasets/
│   └── synthetic/
├── docs/
│   └── architecture/
├── entity-resolution/
├── graph/
├── intelligence/
├── ml/
├── reports/
├── workers/
├── .env.example
├── alembic.ini
├── compose.yaml
└── pyproject.toml
```

Some directories are reserved for future architectural extensions and should not be interpreted as proof that those components are already implemented.

## Prerequisites

- Python 3.12
- uv
- Node.js and npm
- Docker Desktop or Docker Engine with Docker Compose
- Git

## Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/Sherone2563/Dark-intel.git
cd Dark-intel
```

### 2. Configure environment variables

Create a local environment file:

```bash
cp .env.example .env
```

Edit `.env` and configure a local database password:

```env
POSTGRES_DB=dark_intel
POSTGRES_USER=dark_intel_app
POSTGRES_PASSWORD=replace_with_a_local_secret
```

Do not commit `.env` or expose database credentials.

### 3. Set up the Python environment

```bash
uv python install 3.12
uv sync --extra dev
```

Activate the environment if desired:

```bash
source .venv/bin/activate
```

### 4. Start PostgreSQL

```bash
docker compose up -d postgres
```

Check container status:

```bash
docker compose ps
```

### 5. Apply database migrations

From the repository root:

```bash
PYTHONPATH=backend uv run alembic upgrade head
```

### 6. Start the backend

```bash
PYTHONPATH=backend uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend health endpoint:

```text
http://127.0.0.1:8000/health
```

Interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

### 7. Start the frontend

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL printed in the terminal, normally:

```text
http://127.0.0.1:5173
```

The Vite development server proxies `/api` requests to the local FastAPI service on port `8000`.

## Dataset Ingestion

Dark Intel includes a command-line interface for importing local JSONL research datasets.

The dataset must come from an authorized source registered in the application.

First, register a source through the API documentation:

```text
http://127.0.0.1:8000/docs
```

Record its returned `source_id` and ensure that the source is authorized for use.

Import a JSONL dataset:

```bash
PYTHONPATH=backend uv run python -m app.cli.import_dataset \
  --file datasets/synthetic/cli_smoke_test.jsonl \
  --source-id YOUR_AUTHORIZED_SOURCE_UUID
```

To run the full import and handle-extraction pipeline:

```bash
PYTHONPATH=backend uv run python -m app.cli.import_dataset \
  --file datasets/synthetic/cli_smoke_test.jsonl \
  --source-id YOUR_AUTHORIZED_SOURCE_UUID \
  --full-pipeline
```

Replace the example source UUID with the ID of an existing authorized source.

## Important API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | API health |
| POST | `/sources` | Register a source |
| GET | `/sources` | List sources |
| POST | `/entities` | Register an entity |
| GET | `/entities` | List entities |
| GET | `/entities/search` | Search entities |
| GET | `/entities/search/analyst` | Analyst-oriented entity search |
| GET | `/entities/{id}/candidates` | Find handle candidates |
| POST | `/observations` | Create an observation |
| GET | `/observations` | List observations |
| POST | `/relationships` | Create a relationship |
| GET | `/relationships` | List relationships |
| POST | `/evidence` | Create evidence |
| GET | `/relationships/{id}/analysis` | Analyze a relationship |
| GET | `/entities/{id}/provenance` | Inspect entity provenance |
| GET | `/entities/{id}/investigation` | Investigate an entity |
| GET | `/entities/{id}/graph` | Retrieve its relationship graph |
| GET | `/entities/{id}/timeline` | Retrieve its timeline |
| GET | `/entities/{id}/report` | Generate an intelligence report |
| GET | `/monitoring/summary` | Retrieve monitoring summary |
| GET | `/monitoring/diagnostics` | Retrieve processing diagnostics |
| GET | `/processing-runs` | List processing runs |

For request parameters and response schemas, use the interactive Swagger documentation at `/docs`.

## Testing and Validation

### Backend tests

From the repository root:

```bash
PYTHONPATH=backend uv run pytest -q
```

### Frontend linting

```bash
cd frontend
npm run lint
```

### Frontend production build

```bash
npm run build
```

### Database migration consistency

From the repository root:

```bash
PYTHONPATH=backend uv run alembic check
```

## Analytical Methodology and Limitations

Dark Intel distinguishes between entity similarity, analytical linkage and real-world identity.

- Similar handles do not automatically establish common ownership.
- Candidate similarity does not prove that two accounts belong to the same actor.
- Supporting evidence must be evaluated alongside contradictory evidence.
- Multiple evidence records from one source do not constitute independent corroboration.
- Source reliability is reported separately from the numeric evidence-balance score.
- Confidence eligibility requires qualifying source evidence.
- A numerical linkage score is not a probability of real-world identity.
- Consequential attribution conclusions require human review.

The current implementation provides evidence-backed analytical workflows. It does not claim guaranteed attribution or deanonymization.

## Current Implementation Boundaries

The current application implements a PostgreSQL-backed API, research-dataset ingestion, entity extraction, evidence analysis, investigation workflows, reporting, monitoring and a React frontend.

The broader architecture document describes potential extensions, including:

- Neo4j graph database integration.
- Dedicated background processing workers.
- Live authorized-source collector adapters.
- Advanced machine-learning evaluation.
- Production deployment and security hardening.

These should be treated as future development work unless independently implemented and validated.

## Research and Ethical Use

Dark Intel is intended for authorized cybersecurity research, public cyber-threat intelligence and approved academic datasets.

Users should:

- Use only authorized sources and permitted datasets.
- Avoid collecting or exposing unnecessary personal information.
- Protect credentials and sensitive research material.
- Preserve evidence provenance.
- Distinguish analytical association from proof of identity.
- Require human review for consequential attribution assessments.

## License

No open-source license has been declared yet. All rights remain with the respective copyright holders unless a license is added to this repository.
