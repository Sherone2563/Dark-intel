import { useState } from 'react'

const API = '/api'

type Entity = {
  entity_id: string
  entity_type: string
  canonical_value: string
  display_value: string
}

type SearchResult = {
  entity: Entity
  authorized_observation_count: number
  authorized_source_count: number
  supported_relationship_count: number
  contradicting_evidence_count: number
  last_observed_at: string | null
}

type SearchResponse = {
  results: SearchResult[]
  result_count: number
  query: string
  limit: number
  offset: number
}

type Relationship = {
  relationship_id: string
  source_entity_id: string
  target_entity_id: string
  relationship_type: string
  description: string | null
  first_observed_at: string | null
  last_observed_at: string | null
}

type Evidence = {
  evidence_id: string
  relationship_id: string
  observation_id: string
  polarity: string
  evidence_description: string
  limitations: string | null
  observed_at: string | null
  created_at: string
}

type InvestigationSource = {
  source_id: string
  name: string
  source_type: string
  reference: string | null
  reliability: string
  authorized_for_use: boolean
  authorization_note: string | null
}

type InvestigationObservation = {
  observation_id: string
  source_id: string
  collected_at: string
  observed_at: string | null
  content_sha256: string
  status: string
  processing_version: string
}

type InvestigationEvidence = {
  evidence: Evidence
  observation: InvestigationObservation
  source: InvestigationSource
}

type InvestigationAnalysis = {
  relationship_id: string
  score: number | null
  confidence_band: string
  supporting_count: number
  contradicting_count: number
  neutral_count: number
  evidence_ids: string[]
  methodology: string
  qualifying_source_count: number
  confidence_reason: string
  distinct_source_count: number
  evidence_items_sharing_sources: number
  source_reliability_evidence_counts: Record<string, number>
  source_quality_note: string
  distinct_observation_count: number
}

type InvestigationRelationship = {
  relationship: Relationship
  connected_entity: Entity
  analysis: InvestigationAnalysis
  evidence_records: InvestigationEvidence[]
}

type InvestigationResponse = {
  entity: Entity
  relationships: InvestigationRelationship[]
  relationship_count: number
  evidence_record_count: number
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API}${path}`)

  if (!response.ok) {
    let message = `API returned ${response.status}`

    try {
      const body = await response.json()
      if (typeof body.detail === 'string') {
        message = body.detail
      }
    } catch {
      // Keep the HTTP status message.
    }

    throw new Error(message)
  }

  return response.json() as Promise<T>
}

function formatDate(value: string | null | undefined): string {
  if (!value) return 'Not recorded'

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return 'Invalid date'
  }

  return date.toLocaleString()
}

function displayEntity(entity: Entity): string {
  return entity.display_value || entity.canonical_value
}

function formatLabel(value: string): string {
  return value.replaceAll('_', ' ')
}

function confidenceColor(value: string): string {
  switch (value.toLowerCase()) {
    case 'high':
    case 'high_confidence':
      return 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'

    case 'strong':
      return 'text-sky-400 border-sky-500/30 bg-sky-500/10'

    case 'possible':
      return 'text-amber-400 border-amber-500/30 bg-amber-500/10'

    case 'weak':
      return 'text-orange-400 border-orange-500/30 bg-orange-500/10'

    default:
      return 'text-[var(--text-muted)] border-[var(--border-primary)] bg-white/[0.03]'
  }
}

function polarityColor(value: string): string {
  switch (value.toLowerCase()) {
    case 'supports':
      return 'text-emerald-400'

    case 'contradicts':
      return 'text-rose-400'

    default:
      return 'text-[var(--text-muted)]'
  }
}

function Metric({
  label,
  value,
}: {
  label: string
  value: string | number
}) {
  return (
    <div className="rounded-lg border border-[var(--border-primary)] bg-white/[0.02] p-4">
      <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
        {label}
      </p>

      <p className="mt-2 text-xl font-semibold text-[var(--text-primary)]">
        {value}
      </p>
    </div>
  )
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-dashed border-[var(--border-primary)] px-5 py-10 text-center">
      <p className="text-xs text-[var(--text-muted)]">{message}</p>
    </div>
  )
}

export default function InvestigationsWorkspace() {
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] =
    useState<SearchResponse | null>(null)

  const [selectedEntity, setSelectedEntity] =
    useState<Entity | null>(null)

  const [investigation, setInvestigation] =
    useState<InvestigationResponse | null>(null)

  const [searchLoading, setSearchLoading] = useState(false)
  const [investigationLoading, setInvestigationLoading] =
    useState(false)

  const [searchError, setSearchError] = useState('')
  const [investigationError, setInvestigationError] = useState('')

  const [expandedRelationship, setExpandedRelationship] =
    useState<string | null>(null)

  async function searchEntities(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const value = query.trim()

    if (!value) {
      setSearchError('Enter an entity or identifier to search.')
      setSearchResults(null)
      return
    }

    setSearchLoading(true)
    setSearchError('')
    setSearchResults(null)
    setSelectedEntity(null)
    setInvestigation(null)
    setInvestigationError('')
    setExpandedRelationship(null)

    try {
      const params = new URLSearchParams({
        value,
        limit: '10',
        offset: '0',
      })

      const result = await getJson<SearchResponse>(
        `/entities/search/analyst?${params.toString()}`,
      )

      setSearchResults(result)
    } catch (error) {
      setSearchError(
        error instanceof Error
          ? error.message
          : 'Entity search failed.',
      )
    } finally {
      setSearchLoading(false)
    }
  }

  async function openInvestigation(entity: Entity) {
    setSelectedEntity(entity)
    setInvestigation(null)
    setInvestigationError('')
    setInvestigationLoading(true)
    setExpandedRelationship(null)

    try {
      const result = await getJson<InvestigationResponse>(
        `/entities/${encodeURIComponent(entity.entity_id)}/investigation`,
      )

      setInvestigation(result)
    } catch (error) {
      setInvestigationError(
        error instanceof Error
          ? error.message
          : 'Could not retrieve the investigation.',
      )
    } finally {
      setInvestigationLoading(false)
    }
  }

  async function refreshInvestigation() {
    if (!selectedEntity) return
    await openInvestigation(selectedEntity)
  }

  return (
    <section className="mt-7 space-y-5">
      {/* WORKSPACE HEADER */}

      <div className="panel">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[10px] font-semibold tracking-[0.16em] text-[var(--accent-secondary)]">
              EVIDENCE-BASED ANALYSIS
            </p>

            <h2 className="mt-2 text-lg font-semibold text-[var(--text-primary)]">
              Investigation workspace
            </h2>

            <p className="mt-2 max-w-2xl text-xs leading-6 text-[var(--text-secondary)]">
              Investigate registered entities, examine connected
              relationships, and review the evidence and provenance
              behind each analytical linkage assessment.
            </p>
          </div>

          <span className="rounded border border-[var(--border-primary)] px-3 py-2 text-[10px] tracking-wider text-[var(--text-muted)]">
            READ-ONLY ANALYSIS
          </span>
        </div>
      </div>

      {/* ENTITY SEARCH */}

      <div className="panel">
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">
            Find an entity
          </h3>

          <p className="mt-1 text-xs text-[var(--text-muted)]">
            Search registered handles, actors, identifiers, and other entities.
          </p>
        </div>

        <form
          onSubmit={searchEntities}
          className="flex flex-col gap-3 sm:flex-row"
        >
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Enter an entity name or identifier..."
            className="min-w-0 flex-1 rounded border border-[var(--border-primary)] bg-[var(--bg-primary)] px-4 py-3 text-xs text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)] focus:border-[var(--accent-primary)]"
          />

          <button
            type="submit"
            disabled={searchLoading}
            className="rounded border border-[var(--accent-primary)] bg-[var(--accent-primary)]/10 px-5 py-3 text-xs font-medium text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/20 disabled:opacity-50"
          >
            {searchLoading ? 'Searching...' : 'Search entities'}
          </button>
        </form>

        {searchError && (
          <p className="mt-3 text-xs text-rose-400">{searchError}</p>
        )}

        {searchResults && (
          <div className="mt-5">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-xs text-[var(--text-secondary)]">
                Search results
              </p>

              <span className="text-[10px] text-[var(--text-muted)]">
                {searchResults.result_count} found
              </span>
            </div>

            {searchResults.results.length === 0 ? (
              <EmptyState message="No matching registered entities were found." />
            ) : (
              <div className="space-y-2">
                {searchResults.results.map((result) => (
                  <button
                    key={result.entity.entity_id}
                    type="button"
                    onClick={() => void openInvestigation(result.entity)}
                    className={`w-full rounded-lg border p-4 text-left transition ${
                      selectedEntity?.entity_id === result.entity.entity_id
                        ? 'border-[var(--accent-primary)] bg-[var(--accent-primary)]/[0.06]'
                        : 'border-[var(--border-primary)] bg-white/[0.02] hover:bg-white/[0.04]'
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="break-all text-sm font-medium text-[var(--text-primary)]">
                          {displayEntity(result.entity)}
                        </p>

                        <p className="mt-1 font-mono text-[10px] text-[var(--text-muted)]">
                          {formatLabel(result.entity.entity_type)}
                        </p>
                      </div>

                      <span className="text-[10px] text-[var(--accent-primary)]">
                        Investigate →
                      </span>
                    </div>

                    <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-[10px] text-[var(--text-secondary)]">
                      <span>
                        {result.authorized_observation_count} observations
                      </span>

                      <span>
                        {result.authorized_source_count} sources
                      </span>

                      <span>
                        {result.supported_relationship_count} supported links
                      </span>

                      <span>
                        {result.contradicting_evidence_count} contradictions
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* INVESTIGATION RESULTS */}

      {selectedEntity && (
        <>
          <div className="panel">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-[10px] tracking-[0.16em] text-[var(--accent-secondary)]">
                  SELECTED ENTITY
                </p>

                <h3 className="mt-2 break-all text-base font-semibold text-[var(--text-primary)]">
                  {displayEntity(selectedEntity)}
                </h3>

                <p className="mt-2 break-all font-mono text-[10px] text-[var(--text-muted)]">
                  {selectedEntity.entity_id}
                </p>
              </div>

              <button
                type="button"
                onClick={() => void refreshInvestigation()}
                disabled={investigationLoading}
                className="rounded border border-[var(--border-primary)] px-3 py-2 text-xs text-[var(--accent-primary)] hover:bg-white/[0.04] disabled:opacity-50"
              >
                {investigationLoading ? 'Loading...' : '↻ Refresh'}
              </button>
            </div>
          </div>

          {investigationLoading && (
            <EmptyState message="Retrieving investigation data from the backend..." />
          )}

          {investigationError && (
            <div className="panel">
              <p className="text-xs text-rose-400">
                {investigationError}
              </p>
            </div>
          )}

          {investigation && (
            <>
              {/* SUMMARY */}

              <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                <Metric
                  label="Relationships"
                  value={investigation.relationship_count}
                />

                <Metric
                  label="Evidence records"
                  value={investigation.evidence_record_count}
                />

                <Metric
                  label="Connected entities"
                  value={investigation.relationships.length}
                />

                <Metric
                  label="Evidence sources"
                  value={
                    new Set(
                      investigation.relationships.flatMap((item) =>
                        item.evidence_records.map(
                          (record) => record.source.source_id,
                        ),
                      ),
                    ).size
                  }
                />
              </div>

              {/* RELATIONSHIPS */}

              <div className="panel">
                <div className="mb-5">
                  <p className="text-[10px] tracking-[0.16em] text-[var(--accent-secondary)]">
                    RELATIONSHIP ANALYSIS
                  </p>

                  <h3 className="mt-2 text-sm font-semibold text-[var(--text-primary)]">
                    Connected entities and assessments
                  </h3>
                </div>

                {investigation.relationships.length === 0 ? (
                  <EmptyState message="No stored relationships were found for this entity." />
                ) : (
                  <div className="space-y-3">
                    {investigation.relationships.map((item) => {
                      const relationship = item.relationship
                      const analysis = item.analysis
                      const isExpanded =
                        expandedRelationship === relationship.relationship_id

                      return (
                        <div
                          key={relationship.relationship_id}
                          className="overflow-hidden rounded-lg border border-[var(--border-primary)]"
                        >
                          <button
                            type="button"
                            onClick={() =>
                              setExpandedRelationship(
                                isExpanded
                                  ? null
                                  : relationship.relationship_id,
                              )
                            }
                            className="w-full p-4 text-left hover:bg-white/[0.03]"
                          >
                            <div className="flex flex-wrap items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
                                  {formatLabel(relationship.relationship_type)}
                                </p>

                                <p className="mt-2 break-all text-sm font-medium text-[var(--text-primary)]">
                                  {displayEntity(item.connected_entity)}
                                </p>

                                {relationship.description && (
                                  <p className="mt-2 text-xs leading-5 text-[var(--text-secondary)]">
                                    {relationship.description}
                                  </p>
                                )}
                              </div>

                              <div className="flex flex-col items-end gap-2">
                                <span
                                  className={`rounded border px-2 py-1 text-[10px] capitalize ${confidenceColor(analysis.confidence_band)}`}
                                >
                                  {formatLabel(analysis.confidence_band)}
                                </span>

                                <span className="text-[10px] text-[var(--text-muted)]">
                                  {isExpanded ? 'Collapse ↑' : 'Details ↓'}
                                </span>
                              </div>
                            </div>

                            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                              <div>
                                <p className="text-[10px] text-[var(--text-muted)]">
                                  Score
                                </p>

                                <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">
                                  {analysis.score === null
                                    ? 'N/A'
                                    : `${analysis.score.toFixed(1)}%`}
                                </p>
                              </div>

                              <div>
                                <p className="text-[10px] text-[var(--text-muted)]">
                                  Supporting
                                </p>

                                <p className="mt-1 text-sm font-semibold text-emerald-400">
                                  {analysis.supporting_count}
                                </p>
                              </div>

                              <div>
                                <p className="text-[10px] text-[var(--text-muted)]">
                                  Contradicting
                                </p>

                                <p className="mt-1 text-sm font-semibold text-rose-400">
                                  {analysis.contradicting_count}
                                </p>
                              </div>

                              <div>
                                <p className="text-[10px] text-[var(--text-muted)]">
                                  Neutral
                                </p>

                                <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">
                                  {analysis.neutral_count}
                                </p>
                              </div>
                            </div>
                          </button>

                          {/* EXPANDED ASSESSMENT */}

                          {isExpanded && (
                            <div className="space-y-5 border-t border-[var(--border-primary)] bg-white/[0.015] p-4">
                              <div>
                                <h4 className="text-xs font-semibold text-[var(--text-primary)]">
                                  Confidence assessment
                                </h4>

                                <p className="mt-2 text-xs leading-6 text-[var(--text-secondary)]">
                                  {analysis.confidence_reason}
                                </p>

                                <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                                  <Metric
                                    label="Qualifying sources"
                                    value={analysis.qualifying_source_count}
                                  />

                                  <Metric
                                    label="Distinct sources"
                                    value={analysis.distinct_source_count}
                                  />

                                  <Metric
                                    label="Distinct observations"
                                    value={analysis.distinct_observation_count}
                                  />

                                  <Metric
                                    label="Shared-source items"
                                    value={analysis.evidence_items_sharing_sources}
                                  />
                                </div>
                              </div>

                              <div>
                                <h4 className="text-xs font-semibold text-[var(--text-primary)]">
                                  Methodology
                                </h4>

                                <p className="mt-2 whitespace-pre-wrap text-xs leading-6 text-[var(--text-secondary)]">
                                  {analysis.methodology}
                                </p>
                              </div>

                              <div>
                                <h4 className="text-xs font-semibold text-[var(--text-primary)]">
                                  Source quality
                                </h4>

                                <p className="mt-2 text-xs leading-6 text-[var(--text-secondary)]">
                                  {analysis.source_quality_note}
                                </p>

                                <div className="mt-3 space-y-2">
                                  {Object.entries(
                                    analysis.source_reliability_evidence_counts,
                                  ).map(([reliability, count]) => (
                                    <div
                                      key={reliability}
                                      className="flex justify-between text-xs"
                                    >
                                      <span className="text-[var(--text-secondary)]">
                                        {formatLabel(reliability)}
                                      </span>

                                      <span className="text-[var(--text-primary)]">
                                        {count} evidence items
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              </div>

                              {/* EVIDENCE RECORDS */}

                              <div>
                                <h4 className="mb-3 text-xs font-semibold text-[var(--text-primary)]">
                                  Evidence records ({item.evidence_records.length})
                                </h4>

                                {item.evidence_records.length === 0 ? (
                                  <EmptyState message="No authorized evidence records are available for this relationship." />
                                ) : (
                                  <div className="space-y-3">
                                    {item.evidence_records.map((record) => (
                                      <div
                                        key={record.evidence.evidence_id}
                                        className="rounded-lg border border-[var(--border-primary)] p-4"
                                      >
                                        <div className="flex flex-wrap items-center justify-between gap-2">
                                          <span
                                            className={`text-[10px] font-semibold uppercase tracking-wider ${polarityColor(record.evidence.polarity)}`}
                                          >
                                            {formatLabel(record.evidence.polarity)}
                                          </span>

                                          <span className="text-[10px] text-[var(--text-muted)]">
                                            {formatDate(record.evidence.observed_at)}
                                          </span>
                                        </div>

                                        <p className="mt-3 text-xs leading-6 text-[var(--text-primary)]">
                                          {record.evidence.evidence_description}
                                        </p>

                                        {record.evidence.limitations && (
                                          <p className="mt-3 text-xs leading-5 text-amber-400">
                                            Limitation: {record.evidence.limitations}
                                          </p>
                                        )}

                                        <div className="mt-4 grid gap-2 border-t border-[var(--border-primary)] pt-3 sm:grid-cols-2">
                                          <div>
                                            <p className="text-[10px] text-[var(--text-muted)]">
                                              Source
                                            </p>

                                            <p className="mt-1 break-all text-xs text-[var(--text-secondary)]">
                                              {record.source.name}
                                            </p>
                                          </div>

                                          <div>
                                            <p className="text-[10px] text-[var(--text-muted)]">
                                              Reliability
                                            </p>

                                            <p className="mt-1 text-xs text-[var(--text-secondary)]">
                                              {formatLabel(record.source.reliability)}
                                            </p>
                                          </div>

                                          <div>
                                            <p className="text-[10px] text-[var(--text-muted)]">
                                              Observation collected
                                            </p>

                                            <p className="mt-1 text-xs text-[var(--text-secondary)]">
                                              {formatDate(record.observation.collected_at)}
                                            </p>
                                          </div>

                                          <div>
                                            <p className="text-[10px] text-[var(--text-muted)]">
                                              Processing version
                                            </p>

                                            <p className="mt-1 text-xs text-[var(--text-secondary)]">
                                              {record.observation.processing_version}
                                            </p>
                                          </div>
                                        </div>

                                        <div className="mt-3">
                                          <p className="text-[10px] text-[var(--text-muted)]">
                                            Evidence ID
                                          </p>

                                          <p className="mt-1 break-all font-mono text-[10px] text-[var(--text-muted)]">
                                            {record.evidence.evidence_id}
                                          </p>
                                        </div>

                                        <div className="mt-3">
                                          <p className="text-[10px] text-[var(--text-muted)]">
                                            Observation SHA-256
                                          </p>

                                          <p className="mt-1 break-all font-mono text-[10px] text-[var(--text-muted)]">
                                            {record.observation.content_sha256}
                                          </p>
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              <p className="px-1 text-[10px] leading-5 text-[var(--text-muted)]">
                Linkage scores represent evidence-balance assessments, not
                probabilities of real-world identity. Source reliability
                affects corroboration eligibility, not the numeric score.
              </p>
            </>
          )}
        </>
      )}
    </section>
  )
}