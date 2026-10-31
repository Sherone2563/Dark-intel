
from enum import StrEnum


class EntityType(StrEnum):
    ACTOR = "actor"
    HANDLE = "handle"
    PGP_KEY = "pgp_key"
    WALLET = "wallet"
    EMAIL = "email"
    DOMAIN = "domain"
    IP_ADDRESS = "ip_address"
    ONION_SERVICE = "onion_service"
    MARKETPLACE = "marketplace"
    FORUM = "forum"
    SERVICE = "service"
    POST = "post"
    LISTING = "listing"


class SourceReliability(StrEnum):
    VERY_RELIABLE = "very_reliable"
    USUALLY_RELIABLE = "usually_reliable"
    FAIRLY_RELIABLE = "fairly_reliable"
    NOT_USUALLY_RELIABLE = "not_usually_reliable"
    UNRELIABLE = "unreliable"
    UNKNOWN = "unknown"


class RelationshipType(StrEnum):
    USES = "uses"
    POSTED_ON = "posted_on"
    SOLD_ON = "sold_on"
    ASSOCIATED_WITH = "associated_with"
    MIGRATED_TO = "migrated_to"
    RELATED_TO = "related_to"


class EvidencePolarity(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"

class SourceType(StrEnum):
    RESEARCH_DATASET = "research_dataset"
    PUBLIC_CTI_FEED = "public_cti_feed"
    AUTHORIZED_API = "authorized_api"
    MANUAL_RESEARCH = "manual_research"
    SYNTHETIC = "synthetic"


class ObservationStatus(StrEnum):
    INGESTED = "ingested"
    VALIDATED = "validated"
    REJECTED = "rejected"
class ProcessingRunStatus(StrEnum):
    STARTED = "started"
    IMPORTING = "importing"
    EXTRACTING = "extracting"
    COMPLETED = "completed"
    COMPLETED_WITH_REJECTIONS = "completed_with_rejections"
    FAILED = "failed"