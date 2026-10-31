from datetime import datetime, timezone
from uuid import UUID
from app.models.entities import EntityRecord
from app.services.entity_resolution import (
    EntityResolutionService,
    HandleCandidate,
)
from app.services.diagnostics_service import generate_processing_diagnostics
from app.models.monitoring_api import MonitoringSummaryResponse, ProcessingDiagnosticsListResponse
from app.services.monitoring_service import generate_monitoring_summary
from app.models.report_api import IntelligenceReportResponse
from app.services.intelligence_report import generate_intelligence_report
from app.models.investigation_api import (
    EntityInvestigationResponse,
    InvestigationAnalysis,
    InvestigationEvidence,
    InvestigationObservation,
    InvestigationRelationship,
    InvestigationSource,
)
from app.models.graph_api import EntityGraphResponse,EntityGraphEdge
from app.models.timeline_api import EntityTimelineResponse, TimelineEvent
from app.models.entity_provenance_api import (
    EntityProvenanceRecord,
    EntityProvenanceResponse,
)
from app.models.entity_api import (
    AnalystEntitySearchResponse,
    AnalystEntitySearchResult,
    EntityCreate,
    EntityResponse,
)
from app.models.evidence import EvidenceRecord
from app.services.linkage_scoring import (
    ObservationSourceContext,
    calculate_linkage_score,
)
from app.models.db_models import EvidenceModel
from app.models.evidence_api import EvidenceCreate, EvidenceResponse
from app.models.enums import EvidencePolarity
from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.models.processing_run_api import (
    ProcessingRunListResponse,
    ProcessingRunResponse,
)
from sqlalchemy.orm import joinedload
from app.core.dependencies import get_db
from app.models.db_models import (
    EntityModel,
    ObservationModel,
    ObservationEntityModel,
    ProcessingRunModel,
    RelationshipModel,
    SourceModel,
)
from app.models.enums import EntityType, ObservationStatus
from app.models.observation_api import ObservationCreate, ObservationResponse
from app.models.observations import calculate_payload_sha256
from app.models.source_api import SourceCreate, SourceResponse
from app.models.relationship_api import (
    RelationshipCreate,
    RelationshipResponse,
)

app = FastAPI(
    title="Dark Intel API",
    description=(
        "Evidence-backed threat intelligence, entity resolution, "
        "and attribution assessment for authorized research."
    ),
    version="0.1.0",
)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    """Report whether the API process is responding."""
    return {
        "status": "ok",
        "service": "dark-intel-api",
        "version": app.version,
    }



@app.post(
    "/entities",
    response_model=EntityResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Entities"],
)
def create_entity(
    request: EntityCreate,
    db: Session = Depends(get_db),
) -> EntityResponse:
    """Register a distinct entity without automatically merging similar values."""

    entity = EntityModel(
        entity_type=request.entity_type.value,
        canonical_value=request.canonical_value,
        display_value=request.display_value,
        first_observed_at=request.first_observed_at,
        last_observed_at=request.last_observed_at,
    )

    try:
        db.add(entity)
        db.commit()
        db.refresh(entity)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The entity could not be saved.",
        ) from exc

    return EntityResponse.model_validate(entity)

@app.get(
    "/entities",
    response_model=list[EntityResponse],
    tags=["Entities"],
)
def list_entities(
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[EntityResponse]:
    """List registered entities, newest first, without merging records."""

    statement = (
        select(EntityModel)
        .order_by(
            EntityModel.created_at.desc(),
            EntityModel.entity_id.asc(),
        )
        .offset(offset)
        .limit(limit)
    )

    entities = db.scalars(statement).all()

    return [
        EntityResponse.model_validate(entity)
        for entity in entities
    ]

@app.get(
    "/entities/search",
    response_model=list[EntityResponse],
    tags=["Entities"],
)
def search_entities(
    value: str = Query(min_length=1, max_length=2048),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[EntityResponse]:
    """Search canonical and display values without merging entity records."""

    search_value = value.strip()
    if not search_value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Search value must not be blank.",
        )

    query = (
        select(EntityModel)
        .where(
            EntityModel.canonical_value.ilike(f"%{search_value}%")
            | EntityModel.display_value.ilike(f"%{search_value}%")
        )
        .order_by(EntityModel.created_at.desc())
        .limit(limit)
    )
    return [
        EntityResponse.model_validate(entity)
        for entity in db.scalars(query).all()
    ]
@app.get(
    "/entities/search/analyst",
    response_model=AnalystEntitySearchResponse,
    tags=["Entities"],
)
def search_entities_for_analysts(
    value: str = Query(min_length=1, max_length=2048),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    entity_type: EntityType | None = Query(default=None),
    db: Session = Depends(get_db),
) -> AnalystEntitySearchResponse:
    """Search entities with summaries from authorized research sources."""

    search_value = value.strip()
    if not search_value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Search value must not be blank.",
        )

    filters = (
        EntityModel.canonical_value.ilike(f"%{search_value}%")
        | EntityModel.display_value.ilike(f"%{search_value}%")
    )
    if entity_type is not None:
        filters = filters & (EntityModel.entity_type == entity_type)

    total = db.scalar(
        select(func.count())
        .select_from(EntityModel)
        .where(filters)
    ) or 0

    latest_authorized_observation = (
        select(
            ObservationEntityModel.entity_id.label("entity_id"),
            func.max(ObservationModel.observed_at).label("last_observed_at"),
        )
        .join(
            ObservationModel,
            ObservationModel.observation_id
            == ObservationEntityModel.observation_id,
        )
        .join(
            SourceModel,
            SourceModel.source_id == ObservationModel.source_id,
        )
        .where(SourceModel.authorized_for_use.is_(True))
        .group_by(ObservationEntityModel.entity_id)
        .subquery()
    )

    entities = db.scalars(
        select(EntityModel)
        .outerjoin(
            latest_authorized_observation,
            latest_authorized_observation.c.entity_id
            == EntityModel.entity_id,
        )
        .where(filters)
        .order_by(
            latest_authorized_observation.c.last_observed_at.desc().nulls_last(),
            EntityModel.created_at.desc(),
            EntityModel.entity_id.asc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()

    results = []

    for entity in entities:
        authorized_observations = (
            select(
                ObservationEntityModel.observation_id,
                ObservationModel.source_id,
                ObservationModel.observed_at,
            )
            .join(
                ObservationModel,
                ObservationModel.observation_id
                == ObservationEntityModel.observation_id,
            )
            .join(
                SourceModel,
                SourceModel.source_id == ObservationModel.source_id,
            )
            .where(
                ObservationEntityModel.entity_id == entity.entity_id,
                SourceModel.authorized_for_use.is_(True),
            )
            .distinct()
            .subquery()
        )

        observation_count = db.scalar(
            select(func.count())
            .select_from(authorized_observations)
        ) or 0

        source_count = db.scalar(
            select(func.count(func.distinct(authorized_observations.c.source_id)))
        ) or 0

        last_observed_at = db.scalar(
            select(func.max(authorized_observations.c.observed_at))
        )

        supported_relationships = (
            select(RelationshipModel.relationship_id)
            .join(
                EvidenceModel,
                EvidenceModel.relationship_id
                == RelationshipModel.relationship_id,
            )
            .join(
                ObservationModel,
                ObservationModel.observation_id
                == EvidenceModel.observation_id,
            )
            .join(
                SourceModel,
                SourceModel.source_id == ObservationModel.source_id,
            )
            .where(
                SourceModel.authorized_for_use.is_(True),
                EvidenceModel.polarity == "supports",
                (
                    (RelationshipModel.source_entity_id == entity.entity_id)
                    | (RelationshipModel.target_entity_id == entity.entity_id)
                ),
            )
            .distinct()
        )

        supported_count = db.scalar(
            select(func.count()).select_from(
                supported_relationships.subquery()
            )
        ) or 0

        contradicting_count = db.scalar(
            select(func.count(func.distinct(EvidenceModel.evidence_id)))
            .select_from(EvidenceModel)
            .join(
                ObservationModel,
                ObservationModel.observation_id
                == EvidenceModel.observation_id,
            )
            .join(
                SourceModel,
                SourceModel.source_id == ObservationModel.source_id,
            )
            .join(
                RelationshipModel,
                RelationshipModel.relationship_id
                == EvidenceModel.relationship_id,
            )
            .where(
                SourceModel.authorized_for_use.is_(True),
                EvidenceModel.polarity == "contradicts",
                (
                    (RelationshipModel.source_entity_id == entity.entity_id)
                    | (RelationshipModel.target_entity_id == entity.entity_id)
                ),
            )
        ) or 0

        results.append(
            AnalystEntitySearchResult(
                entity=EntityResponse.model_validate(entity),
                authorized_observation_count=observation_count,
                authorized_source_count=source_count,
                supported_relationship_count=supported_count,
                contradicting_evidence_count=contradicting_count,
                last_observed_at=last_observed_at,
            )
        )

    return AnalystEntitySearchResponse(
        results=results,
        result_count=total,
        query=search_value,
        limit=limit,
        offset=offset,
    )
@app.get(
    "/entities/{entity_id}/candidates",
    response_model=list[HandleCandidate],
    tags=["Entity Resolution"],
)
def find_entity_candidates(
    entity_id: UUID,
    limit: int = Query(default=10, ge=1, le=100),
    min_similarity: float = Query(default=0.4, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
) -> list[HandleCandidate]:
    """Find similar stored handles without modifying intelligence records."""

    entity = db.get(EntityModel, entity_id)

    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found.",
        )

    if entity.entity_type != EntityType.HANDLE.value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Candidate matching is currently supported for handles only.",
        )

    query_entity = EntityRecord(
        entity_id=entity.entity_id,
        entity_type=EntityType(entity.entity_type),
        canonical_value=entity.canonical_value,
        display_value=entity.display_value,
        first_observed_at=entity.first_observed_at,
        last_observed_at=entity.last_observed_at,
        created_at=entity.created_at,
    )

    candidate_rows = db.scalars(
        select(EntityModel)
        .where(EntityModel.entity_type == EntityType.HANDLE.value)
        .order_by(EntityModel.created_at.desc())
    ).all()

    candidate_entities = [
        EntityRecord(
            entity_id=row.entity_id,
            entity_type=EntityType(row.entity_type),
            canonical_value=row.canonical_value,
            display_value=row.display_value,
            first_observed_at=row.first_observed_at,
            last_observed_at=row.last_observed_at,
            created_at=row.created_at,
        )
        for row in candidate_rows
    ]

    matcher = EntityResolutionService()
    candidates = matcher.find_handle_candidates(
        query_entity,
        candidate_entities,
        min_similarity=min_similarity,
    )

    return candidates[:limit]


@app.get(
    "/entities/{entity_id}",
    response_model=EntityResponse,
    tags=["Entities"],
)
def get_entity(
    entity_id: UUID,
    db: Session = Depends(get_db),
) -> EntityResponse:
    """Retrieve one entity by its UUID."""

    entity = db.get(EntityModel, entity_id)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found.",
        )

    return EntityResponse.model_validate(entity)


@app.post(
    "/observations",
    response_model=ObservationResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Observations"],
)
def create_observation(
    request: ObservationCreate,
    db: Session = Depends(get_db),
) -> ObservationResponse:
    """Persist an observation from a registered, authorized research source."""

    source = db.get(SourceModel, request.source_id)

    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The specified source is not registered.",
        )

    if not source.authorized_for_use:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The specified source is not authorized for ingestion.",
        )

    try:
        content_sha256 = calculate_payload_sha256(request.payload)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The observation payload must contain valid JSON values.",
        ) from exc

    observation = ObservationModel(
        source_id=request.source_id,
        collected_at=request.collected_at or datetime.now(timezone.utc),
        observed_at=request.observed_at,
        payload=request.payload,
        content_sha256=content_sha256,
        status=ObservationStatus.INGESTED.value,
        processing_version=request.processing_version,
    )

    try:
        db.add(observation)
        db.commit()
        db.refresh(observation)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The observation could not be saved.",
        ) from exc

    return ObservationResponse.model_validate(observation)

@app.get(
    "/observations",
    response_model=list[ObservationResponse],
    tags=["Observations"],
)
def list_observations(
    source_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[ObservationResponse]:
    """List observations, optionally filtered by source, newest first."""

    query = select(ObservationModel)

    if source_id is not None:
        query = query.where(ObservationModel.source_id == source_id)

    query = (
        query
        .order_by(
            ObservationModel.collected_at.desc(),
            ObservationModel.observation_id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    observations = db.scalars(query).all()

    return [
        ObservationResponse.model_validate(observation)
        for observation in observations
    ]

@app.get(
    "/observations/{observation_id}",
    response_model=ObservationResponse,
    tags=["Observations"],
)
def get_observation(
    observation_id: UUID,
    db: Session = Depends(get_db),
) -> ObservationResponse:
    """Retrieve one observation with its stored provenance fields."""

    observation = db.get(ObservationModel, observation_id)

    if observation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Observation not found.",
        )

    return ObservationResponse.model_validate(observation)

@app.post(
    "/sources",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Sources"],
)
def create_source(
    request: SourceCreate,
    db: Session = Depends(get_db),
) -> SourceResponse:
    """Register a research source with explicit authorization metadata."""

    duplicate_query = select(SourceModel.source_id).where(
        func.lower(SourceModel.name) == request.name.lower(),
        SourceModel.source_type == request.source_type.value,
        SourceModel.reference == request.reference
        if request.reference is not None
        else SourceModel.reference.is_(None),
    )

    if db.scalar(duplicate_query) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A source with this name, type, and reference already exists.",
        )

    source = SourceModel(
        name=request.name,
        source_type=request.source_type.value,
        reference=request.reference,
        reliability=request.reliability.value,
        authorized_for_use=request.authorized_for_use,
        authorization_note=request.authorization_note,
    )

    try:
        db.add(source)
        db.commit()
        db.refresh(source)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The source could not be saved.",
        ) from exc

    return SourceResponse.model_validate(source)


@app.get(
    "/sources",
    response_model=list[SourceResponse],
    tags=["Sources"],
)
def list_sources(
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[SourceResponse]:
    """List registered sources, newest first."""

    query = (
        select(SourceModel)
        .order_by(SourceModel.created_at.desc())
        .limit(limit)
    )
    sources = db.scalars(query).all()

    return [SourceResponse.model_validate(source) for source in sources]

@app.post(
    "/relationships",
    response_model=RelationshipResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Relationships"],
)
def create_relationship(
    request: RelationshipCreate,
    db: Session = Depends(get_db),
) -> RelationshipResponse:
    """Create a relationship between two existing entities."""

    source = db.get(EntityModel, request.source_entity_id)
    target = db.get(EntityModel, request.target_entity_id)

    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source entity not found.",
        )

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target entity not found.",
        )

    relationship = RelationshipModel(
        source_entity_id=request.source_entity_id,
        target_entity_id=request.target_entity_id,
        relationship_type=request.relationship_type.value,
        description=request.description,
        first_observed_at=request.first_observed_at,
        last_observed_at=request.last_observed_at,
    )

    try:
        db.add(relationship)
        db.commit()
        db.refresh(relationship)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The relationship could not be saved.",
        ) from exc

    return RelationshipResponse.model_validate(relationship)


@app.get(
    "/relationships",
    response_model=list[RelationshipResponse],
    tags=["Relationships"],
)
def list_relationships(
    entity_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[RelationshipResponse]:
    """List relationships, optionally filtered by either endpoint entity."""

    query = select(RelationshipModel)

    if entity_id is not None:
        query = query.where(
            (RelationshipModel.source_entity_id == entity_id)
            | (RelationshipModel.target_entity_id == entity_id)
        )

    query = (
        query.order_by(RelationshipModel.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    relationships = db.scalars(query).all()

    return [
        RelationshipResponse.model_validate(relationship)
        for relationship in relationships
    ]


@app.get(
    "/relationships/{relationship_id}",
    response_model=RelationshipResponse,
    tags=["Relationships"],
)
def get_relationship(
    relationship_id: UUID,
    db: Session = Depends(get_db),
) -> RelationshipResponse:
    """Retrieve one relationship by its UUID."""

    relationship = db.get(RelationshipModel, relationship_id)

    if relationship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found.",
        )

    return RelationshipResponse.model_validate(relationship)

@app.post(
    "/evidence",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Evidence"],
)
def create_evidence(
    request: EvidenceCreate,
    db: Session = Depends(get_db),
) -> EvidenceResponse:
    """Create evidence only from an authorized source."""

    relationship = db.get(RelationshipModel, request.relationship_id)
    if relationship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found.",
        )

    observation = db.get(ObservationModel, request.observation_id)
    if observation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Observation not found.",
        )

    source = db.get(SourceModel, observation.source_id)
    if source is None or not source.authorized_for_use:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evidence cannot be created from an unauthorized source.",
        )

    evidence = EvidenceModel(
        relationship_id=request.relationship_id,
        observation_id=request.observation_id,
        polarity=request.polarity.value,
        evidence_description=request.evidence_description,
        limitations=request.limitations,
        observed_at=request.observed_at,
    )

    try:
        db.add(evidence)
        db.commit()
        db.refresh(evidence)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save evidence.",
        ) from exc

    return EvidenceResponse.model_validate(evidence)

@app.get(
    "/evidence/{evidence_id}",
    response_model=EvidenceResponse,
    tags=["Evidence"],
)
def get_evidence(
    evidence_id: UUID,
    db: Session = Depends(get_db),
) -> EvidenceResponse:
    evidence = db.get(EvidenceModel, evidence_id)

    if evidence is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found.",
        )

    return EvidenceResponse.model_validate(evidence)


@app.get(
    "/relationships/{relationship_id}/evidence",
    response_model=list[EvidenceResponse],
    tags=["Evidence"],
)
def list_relationship_evidence(
    relationship_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[EvidenceResponse]:
    relationship = db.get(RelationshipModel, relationship_id)

    if relationship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found.",
        )

    statement = (
        select(EvidenceModel)
        .where(EvidenceModel.relationship_id == relationship_id)
        .order_by(EvidenceModel.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    evidence_records = db.scalars(statement).all()
    return [
        EvidenceResponse.model_validate(record)
        for record in evidence_records
    ]

@app.get(
    "/relationships/{relationship_id}/analysis",
    tags=["Analysis"],
)
def analyze_relationship(
    relationship_id: UUID,
    db: Session = Depends(get_db),
) -> dict:
    """Calculate linkage score and report source-quality diagnostics."""

    relationship = db.get(RelationshipModel, relationship_id)

    if relationship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found.",
        )

    query = (
        select(EvidenceModel, ObservationModel, SourceModel)
        .join(
            ObservationModel,
            EvidenceModel.observation_id == ObservationModel.observation_id,
        )
        .join(
            SourceModel,
            ObservationModel.source_id == SourceModel.source_id,
        )
        .where(
            EvidenceModel.relationship_id == relationship_id,
            SourceModel.authorized_for_use.is_(True),
            )
        .order_by(
            EvidenceModel.created_at.asc(),
            EvidenceModel.evidence_id.asc(),
        )
    )
    rows = db.execute(query).all()

    evidence_records = [
        EvidenceRecord(
            evidence_id=evidence.evidence_id,
            relationship_id=evidence.relationship_id,
            observation_id=evidence.observation_id,
            polarity=EvidencePolarity(evidence.polarity),
            evidence_description=evidence.evidence_description,
            limitations=evidence.limitations,
            observed_at=evidence.observed_at,
            created_at=evidence.created_at,
        )
        for evidence, _, _ in rows
    ]
    observation_sources = {
        observation.observation_id: ObservationSourceContext(
            source_id=source.source_id,
            reliability=source.reliability,
        )
        for _, observation, source in rows
    }

    result = calculate_linkage_score(
        relationship_id=relationship_id,
        evidence=evidence_records,
        observation_sources=observation_sources,
    )

    source_ids = {
        observation.source_id
        for _, observation, _ in rows
    }
    observation_ids = {
    observation.observation_id
    for _, observation, _ in rows
    }

    reliability_counts: dict[str, int] = {}
    for _, _, source in rows:
        reliability = source.reliability
        reliability_counts[reliability] = (
            reliability_counts.get(reliability, 0) + 1
        )

    return {
        **result.model_dump(mode="json"),
        "distinct_source_count": len(source_ids),
        "evidence_items_sharing_sources": len(rows) - len(source_ids),
        "distinct_observation_count": len(observation_ids),
        "source_reliability_evidence_counts": reliability_counts,
        "source_quality_note": (
            "Source reliability determines whether a source qualifies "
            "toward independent corroboration. It does not change the "
            "numeric evidence-balance score. Multiple observations from "
            "one source count as one source."
        ),
    }


@app.get(
    "/entities/{entity_id}/provenance",
    response_model=EntityProvenanceResponse,
    tags=["Entity Provenance"],
)
def get_entity_provenance(
    entity_id: UUID,
    db: Session = Depends(get_db),
) -> EntityProvenanceResponse:
    """Return extraction provenance without exposing raw observation payloads."""

    entity = db.get(EntityModel, entity_id)

    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found.",
        )

    provenance_query = (
        select(
            ObservationEntityModel,
            ObservationModel,
            SourceModel,
        )
        .join(
            ObservationModel,
            ObservationEntityModel.observation_id
            == ObservationModel.observation_id,
        )
        .join(
            SourceModel,
            ObservationModel.source_id == SourceModel.source_id,
        )
        .where(ObservationEntityModel.entity_id == entity_id)
        .order_by(
            ObservationEntityModel.created_at.asc(),
            ObservationEntityModel.association_id.asc(),
        )
    )

    rows = db.execute(provenance_query).all()

    records = [
        EntityProvenanceRecord(
            association_id=association.association_id,
            association_type=association.association_type,
            field_name=association.field_name,
            normalization_method=association.normalization_method,
            association_created_at=association.created_at,
            observation_id=observation.observation_id,
            collected_at=observation.collected_at,
            observed_at=observation.observed_at,
            content_sha256=observation.content_sha256,
            processing_version=observation.processing_version,
            source_id=source.source_id,
            source_name=source.name,
            source_type=source.source_type,
            authorized_for_use=source.authorized_for_use,
        )
        for association, observation, source in rows
    ]

    return EntityProvenanceResponse(
        entity=EntityResponse.model_validate(entity),
        records=records,
        record_count=len(records),
    )


@app.get(
    "/entities/{entity_id}/investigation",
    response_model=EntityInvestigationResponse,
    tags=["Investigation"],
)
def investigate_entity(
    entity_id: UUID,
    db: Session = Depends(get_db),
) -> EntityInvestigationResponse:
    """Return an entity's relationships, linkage assessments, and full provenance."""

    entity = db.get(EntityModel, entity_id)

    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found.",
        )

    relationship_query = (
        select(RelationshipModel)
        .where(
            (RelationshipModel.source_entity_id == entity_id)
            | (RelationshipModel.target_entity_id == entity_id)
        )
        .order_by(
            RelationshipModel.created_at.desc(),
            RelationshipModel.relationship_id,
        )
    )
    relationship_rows = db.scalars(relationship_query).all()

    relationship_results = []
    total_evidence_records = 0

    for relationship in relationship_rows:
        connected_entity_id = (
            relationship.target_entity_id
            if relationship.source_entity_id == entity_id
            else relationship.source_entity_id
        )
        connected_entity = db.get(EntityModel, connected_entity_id)

        if connected_entity is None:
            continue

        evidence_query = (
            select(EvidenceModel, ObservationModel, SourceModel)
            .join(
                ObservationModel,
                EvidenceModel.observation_id
                == ObservationModel.observation_id,
            )
            .join(
                SourceModel,
                ObservationModel.source_id == SourceModel.source_id,
            )
            .where(
                EvidenceModel.relationship_id
                == relationship.relationship_id,
                SourceModel.authorized_for_use.is_(True),
            )
            .order_by(
                EvidenceModel.created_at.asc(),
                EvidenceModel.evidence_id.asc(),
            )
        )
        evidence_rows = db.execute(evidence_query).all()

        evidence_records = [
            EvidenceRecord(
                evidence_id=evidence.evidence_id,
                relationship_id=evidence.relationship_id,
                observation_id=evidence.observation_id,
                polarity=EvidencePolarity(evidence.polarity),
                evidence_description=evidence.evidence_description,
                limitations=evidence.limitations,
                observed_at=evidence.observed_at,
                created_at=evidence.created_at,
            )
            for evidence, _, _ in evidence_rows
        ]
        observation_sources = {
            observation.observation_id: ObservationSourceContext(
                source_id=source.source_id,
                reliability=source.reliability,
            )
            for _, observation, source in evidence_rows
        }

        score = calculate_linkage_score(
            relationship_id=relationship.relationship_id,
            evidence=evidence_records,
            observation_sources=observation_sources,
        )

        source_ids = {
            observation.source_id
            for _, observation, _ in evidence_rows
        }
        observation_ids = {
    observation.observation_id
    for _, observation, _ in evidence_rows
        }

        reliability_counts: dict[str, int] = {}
        for _, _, source in evidence_rows:
            reliability = source.reliability
            reliability_counts[reliability] = (
                reliability_counts.get(reliability, 0) + 1
            )

        full_evidence = [
            InvestigationEvidence(
                evidence=EvidenceResponse.model_validate(evidence),
                observation=InvestigationObservation.model_validate(
                    observation
                ),
                source=InvestigationSource.model_validate(source),
            )
            for evidence, observation, source in evidence_rows
        ]

        total_evidence_records += len(full_evidence)

        analysis = InvestigationAnalysis(
            **score.model_dump(),
            distinct_source_count=len(source_ids),
            distinct_observation_count=len(observation_ids),
            evidence_items_sharing_sources=(
                len(evidence_rows) - len(source_ids)
            ),
            source_reliability_evidence_counts=reliability_counts,
            source_quality_note=(
                "Evidence records, observations, and sources are distinct "
                "counts. Multiple evidence records may reference the same "
                "observation, and multiple observations may originate from "
                "the same source. At least two distinct sources with "
                "qualifying reliability are required for a confidence band. "
                "Source reliability affects corroboration eligibility, "
                "not the numeric evidence-balance score."
            ),
        )

        relationship_results.append(
            InvestigationRelationship(
                relationship=RelationshipResponse.model_validate(
                    relationship
                ),
                connected_entity=EntityResponse.model_validate(
                    connected_entity
                ),
                analysis=analysis,
                evidence_records=full_evidence,
            )
        )

    return EntityInvestigationResponse(
        entity=EntityResponse.model_validate(entity),
        relationships=relationship_results,
        relationship_count=len(relationship_results),
        evidence_record_count=total_evidence_records,
    )

@app.get(
    "/entities/{entity_id}/graph",
    response_model=EntityGraphResponse,
    tags=["Graph Intelligence"],
)
def get_entity_graph(
    entity_id: UUID,
    depth: int = Query(default=1, ge=1, le=3),
    db: Session = Depends(get_db),
) -> EntityGraphResponse:
    """Return a bounded, read-only graph of stored entity relationships."""

    max_nodes = 100

    root = db.get(EntityModel, entity_id)
    if root is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found.",
        )

    # Keep nodes in discovery order for predictable output.
    nodes_by_id: dict[UUID, EntityModel] = {
        root.entity_id: root,
    }
    edges_by_id: dict[UUID, RelationshipModel] = {}

    frontier = [root.entity_id]

    for _ in range(depth):
        if not frontier or len(nodes_by_id) >= max_nodes:
            break

        frontier_ids = set(frontier)

        relationship_query = (
            select(RelationshipModel)
            .where(
                (
                    RelationshipModel.source_entity_id.in_(frontier_ids)
                )
                | (
                    RelationshipModel.target_entity_id.in_(frontier_ids)
                )
            )
            .order_by(
                RelationshipModel.created_at.asc(),
                RelationshipModel.relationship_id.asc(),
            )
        )

        relationships = db.scalars(relationship_query).all()
        next_frontier = []
        next_frontier_ids = set()

        for relationship in relationships:
            source_id = relationship.source_entity_id
            target_id = relationship.target_entity_id

            # Every returned edge must connect two returned nodes.
            if (
                source_id not in nodes_by_id
                and source_id not in frontier_ids
            ):
                if len(nodes_by_id) >= max_nodes:
                    continue

                source_entity = db.get(EntityModel, source_id)
                if source_entity is None:
                    continue

                nodes_by_id[source_id] = source_entity
                if source_id not in next_frontier_ids:
                    next_frontier.append(source_id)
                    next_frontier_ids.add(source_id)

            if (
                target_id not in nodes_by_id
                and target_id not in frontier_ids
            ):
                if len(nodes_by_id) >= max_nodes:
                    continue

                target_entity = db.get(EntityModel, target_id)
                if target_entity is None:
                    continue

                nodes_by_id[target_id] = target_entity
                if target_id not in next_frontier_ids:
                    next_frontier.append(target_id)
                    next_frontier_ids.add(target_id)

            if (
                source_id in nodes_by_id
                and target_id in nodes_by_id
            ):
                edges_by_id[relationship.relationship_id] = relationship

        frontier = next_frontier

    graph_edges = []

    for relationship in edges_by_id.values():
        evidence_query = (
            select(EvidenceModel, ObservationModel, SourceModel)
            .join(
                ObservationModel,
                EvidenceModel.observation_id == ObservationModel.observation_id,
            )
            .join(
                SourceModel,
                ObservationModel.source_id == SourceModel.source_id,
            )
            .where(
                EvidenceModel.relationship_id == relationship.relationship_id,
                SourceModel.authorized_for_use.is_(True),
            )
            .order_by(
                EvidenceModel.created_at.asc(),
                EvidenceModel.evidence_id.asc(),
            )
        )
        evidence_rows = db.execute(evidence_query).all()

        evidence_records = [
            EvidenceRecord(
                evidence_id=evidence.evidence_id,
                relationship_id=evidence.relationship_id,
                observation_id=evidence.observation_id,
                polarity=EvidencePolarity(evidence.polarity),
                evidence_description=evidence.evidence_description,
                limitations=evidence.limitations,
                observed_at=evidence.observed_at,
                created_at=evidence.created_at,
            )
            for evidence, _, _ in evidence_rows
        ]
        observation_sources = {
            observation.observation_id: ObservationSourceContext(
                source_id=source.source_id,
                reliability=source.reliability,
            )
            for _, observation, source in evidence_rows
        }

        analysis_result = calculate_linkage_score(
            relationship_id=relationship.relationship_id,
            evidence=evidence_records,
            observation_sources=observation_sources,
        )

        source_ids = {
            observation.source_id
            for _, observation, _ in evidence_rows
        }
        observation_ids = {
            observation.observation_id
            for _, observation, _ in evidence_rows
        }

        reliability_counts: dict[str, int] = {}
        for _, _, source in evidence_rows:
            reliability = source.reliability
            reliability_counts[reliability] = (
                reliability_counts.get(reliability, 0) + 1
            )

        analysis = InvestigationAnalysis(
            **analysis_result.model_dump(),
            distinct_source_count=len(source_ids),
            evidence_items_sharing_sources=len(evidence_rows) - len(source_ids),
            distinct_observation_count=len(observation_ids),
            source_reliability_evidence_counts=reliability_counts,
            source_quality_note=(
                "Evidence records, observations, and sources are distinct "
                "counts. Multiple evidence records may reference the same "
                "observation, and multiple observations may originate from "
                "the same source. Distinct observations do not necessarily "
                "represent independent corroboration. Source reliability is "
                "reported but is not yet weighted in the linkage score."
            ),
        )

        graph_edges.append(
            EntityGraphEdge(
                relationship=RelationshipResponse.model_validate(relationship),
                evidence=[
                    EvidenceResponse.model_validate(evidence)
                    for evidence, _, _ in evidence_rows
                ],
                analysis=analysis,
            )
        )

    return EntityGraphResponse(
        root_entity_id=root.entity_id,
        depth=depth,
        nodes=[
            EntityResponse.model_validate(entity)
            for entity in nodes_by_id.values()
        ],
        edges=graph_edges,
        node_count=len(nodes_by_id),
        edge_count=len(graph_edges),
    )

@app.get(
    "/entities/{entity_id}/timeline",
    response_model=EntityTimelineResponse,
    tags=["Timeline"],
)
def get_entity_timeline(
    entity_id: UUID,
    db: Session = Depends(get_db),
) -> EntityTimelineResponse:
    """Return chronological, evidence-backed events for an entity."""

    entity = db.get(EntityModel, entity_id)

    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found.",
        )

    relationship_query = (
        select(RelationshipModel)
        .where(
            (RelationshipModel.source_entity_id == entity_id)
            | (RelationshipModel.target_entity_id == entity_id)
        )
    )
    relationships = db.scalars(relationship_query).all()

    events = []

    for relationship in relationships:
        connected_entity_id = (
            relationship.target_entity_id
            if relationship.source_entity_id == entity_id
            else relationship.source_entity_id
        )
        connected_entity = db.get(EntityModel, connected_entity_id)

        if connected_entity is None:
            continue

        evidence_query = (
            select(EvidenceModel, ObservationModel, SourceModel)
            .join(
                ObservationModel,
                EvidenceModel.observation_id == ObservationModel.observation_id,
            )
            .join(
                SourceModel,
                ObservationModel.source_id == SourceModel.source_id,
            )
            .where(
                EvidenceModel.relationship_id == relationship.relationship_id,
                SourceModel.authorized_for_use.is_(True),
            )
        )
        rows = db.execute(evidence_query).all()

        for evidence, observation, source in rows:
            if evidence.observed_at is not None:
                event_timestamp = evidence.observed_at
                timestamp_basis = "evidence_observed_at"
            elif observation.observed_at is not None:
                event_timestamp = observation.observed_at
                timestamp_basis = "observation_observed_at"
            else:
                event_timestamp = observation.collected_at
                timestamp_basis = "observation_collected_at"

            events.append(
                TimelineEvent(
                    event_id=evidence.evidence_id,
                    event_timestamp=event_timestamp,
                    timestamp_basis=timestamp_basis,
                    relationship_id=relationship.relationship_id,
                    relationship_type=relationship.relationship_type,
                    relationship_description=relationship.description,
                    connected_entity=EntityResponse.model_validate(
                        connected_entity
                    ),
                    evidence_id=evidence.evidence_id,
                    evidence_polarity=evidence.polarity,
                    evidence_description=evidence.evidence_description,
                    evidence_limitations=evidence.limitations,
                    observation_id=observation.observation_id,
                    observation_observed_at=observation.observed_at,
                    observation_collected_at=observation.collected_at,
                    content_sha256=observation.content_sha256,
                    source=InvestigationSource.model_validate(source),
                )
            )

    events.sort(
        key=lambda event: (
            event.event_timestamp,
            str(event.relationship_id),
            str(event.evidence_id),
        )
    )

    return EntityTimelineResponse(
        entity=EntityResponse.model_validate(entity),
        events=events,
        event_count=len(events),
    )

@app.get(
    "/entities/{entity_id}/report",
    response_model=IntelligenceReportResponse,
    tags=["Reports"],
)
def get_entity_report(
    entity_id: UUID,
    db: Session = Depends(get_db),
) -> IntelligenceReportResponse:
    """Generate an on-demand intelligence report for an entity."""

    investigation = investigate_entity(entity_id, db)
    timeline = get_entity_timeline(entity_id, db)

    return generate_intelligence_report(
        investigation=investigation,
        timeline=timeline,
    )
@app.get(
    "/processing-runs",
    response_model=ProcessingRunListResponse,
    tags=["Processing Runs"],
)
def list_processing_runs(
    status_filter: str | None = Query(default=None, alias="status"),
    source_id: UUID | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> ProcessingRunListResponse:
    """List persisted processing runs with their registered source details."""

    valid_statuses = {
        "started",
        "importing",
        "extracting",
        "completed",
        "completed_with_rejections",
        "failed",
    }

    if status_filter is not None and status_filter not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid processing-run status.",
        )

    statement = (
        select(ProcessingRunModel, SourceModel)
        .join(
            SourceModel,
            ProcessingRunModel.source_id == SourceModel.source_id,
        )
    )

    if status_filter is not None:
        statement = statement.where(
            ProcessingRunModel.status == status_filter
        )

    if source_id is not None:
        statement = statement.where(
            ProcessingRunModel.source_id == source_id
        )

    count_statement = (
        select(func.count())
        .select_from(ProcessingRunModel)
    )

    if status_filter is not None:
        count_statement = count_statement.where(
            ProcessingRunModel.status == status_filter
        )

    if source_id is not None:
        count_statement = count_statement.where(
            ProcessingRunModel.source_id == source_id
        )

    result_count = db.scalar(count_statement) or 0

    statement = (
        statement
        .order_by(
            ProcessingRunModel.started_at.desc(),
            ProcessingRunModel.run_id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    rows = db.execute(statement).all()

    results = [
        ProcessingRunResponse(
            **{
                **{
                    column.name: getattr(run, column.name)
                    for column in ProcessingRunModel.__table__.columns
                },
                "source_name": source.name,
                "source_type": source.source_type,
                "source_reliability": source.reliability,
                "source_authorized_for_use": source.authorized_for_use,
            }
        )
        for run, source in rows
    ]

    return ProcessingRunListResponse(
        results=results,
        result_count=result_count,
        limit=limit,
        offset=offset,
    )
@app.get(
    "/monitoring/summary",
    response_model=MonitoringSummaryResponse,
    tags=["Operational Monitoring"],
)
def get_monitoring_summary(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> MonitoringSummaryResponse:
    """Return aggregated operational metrics for processing runs."""

    return generate_monitoring_summary(
        db=db,
        days=days,
    )

@app.get(
    "/monitoring/diagnostics",
    response_model=ProcessingDiagnosticsListResponse,
    tags=["Operational Monitoring"],
)
def get_processing_diagnostics(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> ProcessingDiagnosticsListResponse:
    """Return failed and rejected processing runs with diagnostic details."""

    return generate_processing_diagnostics(
        db=db,
        days=days,
        limit=limit,
        offset=offset,
    )
