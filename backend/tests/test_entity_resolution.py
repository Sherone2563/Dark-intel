import pytest

from app.models.entities import EntityRecord
from app.models.enums import EntityType
from app.services.entity_resolution import (
    EntityResolutionService,
    HandleCandidate,
)


@pytest.fixture
def service():
    return EntityResolutionService()


def make_entity(value, entity_type=EntityType.HANDLE):
    return EntityRecord(
        entity_type=entity_type,
        canonical_value=value,
        display_value=value,
    )


def test_exact_match_scores_one(service):
    query = make_entity("shadow_x")
    candidate = make_entity("shadow_x")

    results = service.find_handle_candidates(query, [candidate])

    assert len(results) == 1
    assert results[0].entity_id == candidate.entity_id
    assert results[0].similarity_score == 1.0


def test_case_and_whitespace_are_normalized(service):
    query = make_entity("shadow_x")
    candidate = make_entity("  SHADOW_X  ")

    results = service.find_handle_candidates(query, [candidate])

    assert results[0].similarity_score == 1.0
    assert results[0].canonical_value == "  SHADOW_X  "


def test_near_match_ranks_above_unrelated_handle(service):
    query = make_entity("shadow_x")
    near_match = make_entity("shadowx")
    unrelated = make_entity("blue_elephant")

    results = service.find_handle_candidates(
        query, [unrelated, near_match]
    )

    assert results[0].entity_id == near_match.entity_id
    assert results[0].similarity_score > results[1].similarity_score


def test_similarity_threshold_filters_candidates(service):
    query = make_entity("shadow_x")
    candidate = make_entity("blue_elephant")

    results = service.find_handle_candidates(
        query, [candidate], min_similarity=0.8
    )

    assert results == []


def test_only_query_entity_id_is_excluded(service):
    query = make_entity("shadow_x")
    separate_entity = make_entity("shadow_x")

    results = service.find_handle_candidates(
        query, [query, separate_entity]
    )

    assert len(results) == 1
    assert results[0].entity_id == separate_entity.entity_id


def test_non_handle_entities_are_ignored(service):
    query = make_entity("shadow_x")
    actor = make_entity("shadow_x", EntityType.ACTOR)

    assert service.find_handle_candidates(query, [actor]) == []


def test_non_handle_query_is_rejected(service):
    query = make_entity("shadow_x", EntityType.ACTOR)

    with pytest.raises(ValueError, match="query entity must be a handle"):
        service.find_handle_candidates(query, [])


@pytest.mark.parametrize("threshold", [-0.1, 1.1])
def test_invalid_threshold_is_rejected(service, threshold):
    query = make_entity("shadow_x")

    with pytest.raises(ValueError, match="min_similarity"):
        service.find_handle_candidates(
            query, [], min_similarity=threshold
        )


def test_empty_candidates_return_empty_results(service):
    query = make_entity("shadow_x")

    assert service.find_handle_candidates(query, []) == []


def test_results_are_sorted_deterministically(service):
    query = make_entity("shadow_x")
    candidates = [
        make_entity("shadowy"),
        make_entity("shadowx"),
        make_entity("shadow_x"),
    ]

    results = service.find_handle_candidates(query, candidates)

    expected = sorted(
        results,
        key=lambda item: (
            -item.similarity_score,
            item.canonical_value.casefold(),
            str(item.entity_id),
        ),
    )
    assert results == expected


def test_candidate_model_rejects_invalid_score():
    with pytest.raises(ValueError):
        HandleCandidate(
            entity_id=make_entity("shadow_x").entity_id,
            canonical_value="shadow_x",
            display_value="shadow_x",
            similarity_score=1.5,
        )