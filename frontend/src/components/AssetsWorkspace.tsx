
import { useState } from 'react'

const API = '/api'
const PAGE_SIZE = 10
const INVENTORY_LIMIT = 100

type Entity = {
  entity_id: string
  entity_type: string
  canonical_value: string
  display_value: string
  first_observed_at: string | null
  last_observed_at: string | null
  created_at: string
}

type EntitySearchResult = {
  entity: Entity
  authorized_observation_count: number
  authorized_source_count: number
  supported_relationship_count: number
  contradicting_evidence_count: number
  last_observed_at: string | null
}

type EntitySearchResponse = {
  results: EntitySearchResult[]
  result_count: number
  query: string
  limit: number
  offset: number
}

type Source = {
  source_id: string
  name: string
  source_type: string
  reference: string | null
  reliability: string
  authorized_for_use: boolean
  authorization_note: string | null
  created_at: string
}

type Observation = {
  observation_id: string
  source_id: string
  collected_at: string
  observed_at: string | null
  content_sha256: string
  status: string
  processing_version: string
}

type EntityType =
  | 'actor'
  | 'handle'
  | 'pgp_key'
  | 'wallet'
  | 'email'
  | 'domain'
  | 'ip_address'
  | 'onion_service'
  | 'marketplace'
  | 'forum'
  | 'service'
  | 'post'
  | 'listing'

const entityTypes: EntityType[] = [
  'actor',
  'handle',
  'pgp_key',
  'wallet',
  'email',
  'domain',
  'ip_address',
  'onion_service',
  'marketplace',
  'forum',
  'service',
  'post',
  'listing',
]

type AssetTab = 'Entities' | 'Sources' | 'Observations'

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API}${path}`)

  if (!response.ok) {
    throw new Error(`API returned ${response.status} for ${path}`)
  }

  return response.json() as Promise<T>
}

function formatDate(value: string | null | undefined) {
  if (!value) return 'Not recorded'

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return 'Invalid date'
  }

  return date.toLocaleString()
}

function label(value: string) {
  return value.replaceAll('_', ' ')
}

function shortId(value: string) {
  return value.length > 14
    ? `${value.slice(0, 10)}…`
    : value
}

function StatusLabel({
  value,
  positive = false,
}: {
  value: string
  positive?: boolean
}) {
  return (
    <span
      className={`inline-flex rounded border px-2 py-1 text-[9px] uppercase tracking-wider ${
        positive
          ? 'border-emerald-400/20 text-emerald-300'
          : 'border-[var(--border-primary)] text-[var(--text-secondary)]'
      }`}
    >
      {value}
    </span>
  )
}

function EmptyMessage({
  children,
}: {
  children: string
}) {
  return (
    <div className="py-12 text-center text-xs text-[var(--text-muted)]">
      {children}
    </div>
  )
}

export default function AssetsWorkspace({
  onOpenEntity,
}: {
  onOpenEntity: (entity: Entity) => void
}) {
  const [activeTab, setActiveTab] =
    useState<AssetTab>('Entities')

  // Entity inventory state
  const [entityQuery, setEntityQuery] = useState('')
  const [entityType, setEntityType] = useState('')
  const [entityResults, setEntityResults] =
    useState<EntitySearchResponse | null>(null)
  const [entityOffset, setEntityOffset] = useState(0)
  const [entityLoading, setEntityLoading] = useState(false)
  const [entityError, setEntityError] = useState('')

  // Source inventory state
  const [sources, setSources] = useState<Source[]>([])
  const [sourceLoading, setSourceLoading] = useState(false)
  const [sourceError, setSourceError] = useState('')
  const [sourceFilter, setSourceFilter] = useState('all')
  const [sourceOffset, setSourceOffset] = useState(0)

  // Observation inventory state
  const [observations, setObservations] =
    useState<Observation[]>([])
  const [observationLoading, setObservationLoading] =
    useState(false)
  const [observationError, setObservationError] = useState('')
  const [observationOffset, setObservationOffset] = useState(0)

  // ENTITY SEARCH

  async function searchEntities(
    query: string,
    type: string,
    offset: number,
  ) {
    if (!query.trim()) {
      setEntityResults(null)
      setEntityOffset(0)
      setEntityError(
        'Enter an entity value to search the inventory.',
      )
      return
    }

    setEntityLoading(true)
    setEntityError('')

    try {
      const params = new URLSearchParams({
        value: query.trim(),
        limit: String(PAGE_SIZE),
        offset: String(offset),
      })

      if (type) {
        params.set('entity_type', type)
      }

      const result = await getJson<EntitySearchResponse>(
        `/entities/search/analyst?${params.toString()}`,
      )

      setEntityResults(result)
      setEntityOffset(offset)
    } catch (error) {
      setEntityError(
        error instanceof Error
          ? error.message
          : 'Unable to search entities.',
      )
      setEntityResults(null)
    } finally {
      setEntityLoading(false)
    }
  }

  // SOURCE INVENTORY

  async function loadSources() {
    setSourceLoading(true)
    setSourceError('')

    try {
      const result = await getJson<Source[]>(
        `/sources?limit=${INVENTORY_LIMIT}`,
      )

      setSources(result)
      setSourceOffset(0)
    } catch (error) {
      setSourceError(
        error instanceof Error
          ? error.message
          : 'Unable to retrieve sources.',
      )
    } finally {
      setSourceLoading(false)
    }
  }

  // OBSERVATION INVENTORY

  async function loadObservations() {
    setObservationLoading(true)
    setObservationError('')

    try {
      const result = await getJson<Observation[]>(
        `/observations?limit=${INVENTORY_LIMIT}&offset=0`,
      )

      setObservations(result)
      setObservationOffset(0)
    } catch (error) {
      setObservationError(
        error instanceof Error
          ? error.message
          : 'Unable to retrieve observations.',
      )
    } finally {
      setObservationLoading(false)
    }
  }

  // DERIVED INVENTORY DATA

  const filteredSources = sources.filter((source) => {
    if (sourceFilter === 'authorized') {
      return source.authorized_for_use
    }

    if (sourceFilter === 'unauthorized') {
      return !source.authorized_for_use
    }

    return true
  })

  const visibleSources = filteredSources.slice(
    sourceOffset,
    sourceOffset + PAGE_SIZE,
  )

  const visibleObservations = observations.slice(
    observationOffset,
    observationOffset + PAGE_SIZE,
  )

  const sourceNames = new Map(
    sources.map((source) => [
      source.source_id,
      source.name,
    ]),
  )

  const tabs: AssetTab[] = [
    'Entities',
    'Sources',
    'Observations',
  ]

  // MAIN WORKSPACE

  return (
    <section className="mt-7 space-y-5">

      {/* PAGE HEADER */}

      <div>
        <p className="text-[10px] tracking-[0.16em] text-[var(--accent-secondary)]">
          INTELLIGENCE RESOURCE MANAGEMENT
        </p>

        <h2 className="mt-2 text-xl font-semibold text-[var(--text-primary)]">
          Asset inventory
        </h2>

        <p className="mt-2 text-xs leading-6 text-[var(--text-muted)]">
          Explore registered entities, research sources, and
          collected observations from the intelligence database.
        </p>
      </div>

      {/* ASSET TABS */}

      <div className="flex flex-wrap gap-2 border-b border-white/[0.07] pb-3">
        {tabs.map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => {
              setActiveTab(tab)

              if (tab === 'Sources' && sources.length === 0) {
                void loadSources()
              }

              if (
                tab === 'Observations' &&
                observations.length === 0
              ) {
                if (sources.length === 0) {
                  void loadSources()
                }

                void loadObservations()
              }
            }}
            className={`rounded px-4 py-2 text-xs transition ${
              activeTab === tab
                ? 'border border-[var(--accent-primary)] bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]'
                : 'border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:bg-white/[0.04]'
            }`}
            aria-pressed={activeTab === tab}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* ENTITY INVENTORY */}

      {activeTab === 'Entities' && (
        <div className="panel">

          <div className="border-b border-white/[0.07] pb-4">
            <h3 className="panel-title">
              Entity inventory
            </h3>

            <p className="panel-description">
              REGISTERED INTELLIGENCE ENTITIES · AUTHORIZED DATA SUMMARY
            </p>
          </div>

          {/* ENTITY SEARCH FORM */}

          <form
            className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-[minmax(0,1fr)_200px_auto]"
            onSubmit={(event) => {
              event.preventDefault()
              void searchEntities(entityQuery, entityType, 0)
            }}
          >
            <input
              value={entityQuery}
              onChange={(event) =>
                setEntityQuery(event.target.value)
              }
              placeholder="Search canonical or display value..."
              aria-label="Search entities"
              className="min-w-0 rounded border border-[var(--border-primary)] bg-[var(--bg-secondary)] px-3 py-2.5 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--accent-primary)]"
            />

            <select
              value={entityType}
              onChange={(event) =>
                setEntityType(event.target.value)
              }
              aria-label="Filter by entity type"
              className="rounded border border-[var(--border-primary)] bg-[var(--bg-secondary)] px-3 py-2.5 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--accent-primary)]"
            >
              <option value="">All entity types</option>

              {entityTypes.map((type) => (
                <option key={type} value={type}>
                  {label(type)}
                </option>
              ))}
            </select>

            <button
              type="submit"
              disabled={entityLoading}
              className="rounded border border-[var(--accent-primary)] bg-[var(--accent-primary)]/10 px-5 py-2.5 text-xs font-semibold text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/20 disabled:opacity-50"
            >
              {entityLoading ? 'Searching…' : 'Search entities'}
            </button>
          </form>

          {entityError && (
            <p
              role="alert"
              className="mt-4 text-xs text-rose-300"
            >
              {entityError}
            </p>
          )}

          {entityLoading ? (
            <EmptyMessage>
              Searching the entity inventory…
            </EmptyMessage>
          ) : entityResults &&
            entityResults.results.length > 0 ? (
            <>

              <div className="mt-5 flex flex-wrap items-center justify-between gap-2">
                <p className="text-[10px] text-[var(--text-muted)]">
                  {entityResults.result_count} matching entities
                </p>

                <p className="text-[10px] text-[var(--text-muted)]">
                  Showing {entityOffset + 1}–
                  {entityOffset + entityResults.results.length}
                </p>
              </div>

              <div className="mt-3 space-y-3">
                {entityResults.results.map((result) => (
                  <article
                    key={result.entity.entity_id}
                    className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-4"
                  >

                    <div className="flex flex-wrap items-start justify-between gap-3">

                      <div className="min-w-0">
                        <StatusLabel
                          value={label(result.entity.entity_type)}
                        />

                        <h4 className="mt-3 break-all text-sm font-semibold text-[var(--text-primary)]">
                          {result.entity.display_value}
                        </h4>

                        <p className="mt-1 break-all font-mono text-[9px] text-[var(--text-muted)]">
                          {result.entity.canonical_value}
                        </p>
                      </div>

                      <button
                        type="button"
                        onClick={() =>
                          onOpenEntity(result.entity)
                        }
                        className="shrink-0 rounded border border-[var(--accent-primary)] px-3 py-2 text-[10px] text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/10"
                      >
                        Open investigation →
                      </button>

                    </div>

                    {/* ENTITY METRICS */}

                    <div className="mt-4 grid grid-cols-2 gap-3 border-t border-white/[0.06] pt-3 sm:grid-cols-4">

                      <div>
                        <p className="text-[9px] text-[var(--text-muted)]">
                          AUTHORIZED OBSERVATIONS
                        </p>

                        <p className="mt-1 text-sm text-[var(--text-primary)]">
                          {result.authorized_observation_count}
                        </p>
                      </div>

                      <div>
                        <p className="text-[9px] text-[var(--text-muted)]">
                          AUTHORIZED SOURCES
                        </p>

                        <p className="mt-1 text-sm text-[var(--text-primary)]">
                          {result.authorized_source_count}
                        </p>
                      </div>

                      <div>
                        <p className="text-[9px] text-[var(--text-muted)]">
                          SUPPORTING RELATIONSHIPS
                        </p>

                        <p className="mt-1 text-sm text-emerald-300">
                          {result.supported_relationship_count}
                        </p>
                      </div>

                      <div>
                        <p className="text-[9px] text-[var(--text-muted)]">
                          CONTRADICTING EVIDENCE
                        </p>

                        <p className="mt-1 text-sm text-rose-300">
                          {result.contradicting_evidence_count}
                        </p>
                      </div>

                    </div>

                    <p className="mt-3 text-[10px] text-[var(--text-muted)]">
                      Last authorized observation:{' '}
                      {formatDate(result.last_observed_at)}
                    </p>

                  </article>
                ))}
              </div>

              {/* ENTITY PAGINATION */}

              <div className="mt-5 flex items-center justify-between border-t border-white/[0.07] pt-4">

                <button
                  type="button"
                  disabled={
                    entityOffset === 0 || entityLoading
                  }
                  onClick={() =>
                    void searchEntities(
                      entityQuery,
                      entityType,
                      Math.max(0, entityOffset - PAGE_SIZE),
                    )
                  }
                  className="rounded border border-[var(--border-primary)] px-3 py-2 text-[10px] text-[var(--text-secondary)] disabled:opacity-30"
                >
                  ← Previous
                </button>

                <span className="text-[10px] text-[var(--text-muted)]">
                  Page {Math.floor(entityOffset / PAGE_SIZE) + 1}{' '}
                  of{' '}
                  {Math.max(
                    1,
                    Math.ceil(
                      entityResults.result_count / PAGE_SIZE,
                    ),
                  )}
                </span>

                <button
                  type="button"
                  disabled={
                    entityOffset + PAGE_SIZE >=
                      entityResults.result_count ||
                    entityLoading
                  }
                  onClick={() =>
                    void searchEntities(
                      entityQuery,
                      entityType,
                      entityOffset + PAGE_SIZE,
                    )
                  }
                  className="rounded border border-[var(--border-primary)] px-3 py-2 text-[10px] text-[var(--text-secondary)] disabled:opacity-30"
                >
                  Next →
                </button>

              </div>

            </>
          ) : entityResults ? (
            <EmptyMessage>
              No matching entities were found.
            </EmptyMessage>
          ) : (
            <EmptyMessage>
              Search by an entity handle, identifier, domain,
              or other registered value to explore the inventory.
            </EmptyMessage>
          )}

        </div>
      )}

      {/* SOURCE INVENTORY */}

      {activeTab === 'Sources' && (
        <div className="panel">

          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/[0.07] pb-4">

            <div>
              <h3 className="panel-title">
                Source inventory
              </h3>

              <p className="panel-description">
                REGISTERED RESEARCH SOURCES AND AUTHORIZATION
              </p>
            </div>

            <button
              type="button"
              onClick={() => void loadSources()}
              disabled={sourceLoading}
              className="text-[10px] text-[var(--accent-primary)] disabled:opacity-50"
            >
              Refresh
            </button>

          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">

            <p className="text-[10px] text-[var(--text-muted)]">
              {filteredSources.length} sources shown in retrieved inventory
            </p>

            <select
              value={sourceFilter}
              onChange={(event) => {
                setSourceFilter(event.target.value)
                setSourceOffset(0)
              }}
              aria-label="Filter source authorization"
              className="rounded border border-[var(--border-primary)] bg-[var(--bg-secondary)] px-3 py-2 text-xs text-[var(--text-primary)]"
            >
              <option value="all">All sources</option>
              <option value="authorized">Authorized</option>
              <option value="unauthorized">Not authorized</option>
            </select>

          </div>

          {sourceError && (
            <p
              role="alert"
              className="mt-4 text-xs text-rose-300"
            >
              {sourceError}
            </p>
          )}

          {sourceLoading ? (
            <EmptyMessage>
              Loading registered sources…
            </EmptyMessage>
          ) : filteredSources.length === 0 ? (
            <EmptyMessage>
              No sources match this filter.
            </EmptyMessage>
          ) : (
            <>

              <div className="mt-4 space-y-3">
                {visibleSources.map((source) => (
                  <article
                    key={source.source_id}
                    className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-4"
                  >

                    <div className="flex flex-wrap items-start justify-between gap-3">

                      <div>
                        <h4 className="text-sm font-semibold text-[var(--text-primary)]">
                          {source.name}
                        </h4>

                        <p className="mt-1 text-[10px] text-[var(--text-muted)]">
                          {label(source.source_type)}
                        </p>
                      </div>

                      <StatusLabel
                        value={
                          source.authorized_for_use
                            ? 'Authorized'
                            : 'Not authorized'
                        }
                        positive={source.authorized_for_use}
                      />

                    </div>

                    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">

                      <div>
                        <p className="text-[9px] text-[var(--text-muted)]">
                          RELIABILITY
                        </p>

                        <p className="mt-1 text-xs text-[var(--text-secondary)]">
                          {label(source.reliability)}
                        </p>
                      </div>

                      <div>
                        <p className="text-[9px] text-[var(--text-muted)]">
                          REGISTERED
                        </p>

                        <p className="mt-1 text-xs text-[var(--text-secondary)]">
                          {formatDate(source.created_at)}
                        </p>
                      </div>

                    </div>

                    {source.reference && (
                      <p className="mt-3 break-all font-mono text-[10px] text-[var(--text-muted)]">
                        {source.reference}
                      </p>
                    )}

                    {source.authorization_note && (
                      <p className="mt-3 text-[10px] leading-5 text-[var(--text-secondary)]">
                        {source.authorization_note}
                      </p>
                    )}

                    <p className="mt-3 break-all font-mono text-[9px] text-[var(--text-muted)]">
                      {source.source_id}
                    </p>

                  </article>
                ))}
              </div>

              {/* SOURCE PAGINATION */}

              <div className="mt-5 flex items-center justify-between border-t border-white/[0.07] pt-4">

                <button
                  type="button"
                  disabled={sourceOffset === 0}
                  onClick={() =>
                    setSourceOffset(
                      Math.max(0, sourceOffset - PAGE_SIZE),
                    )
                  }
                  className="rounded border border-[var(--border-primary)] px-3 py-2 text-[10px] text-[var(--text-secondary)] disabled:opacity-30"
                >
                  ← Previous
                </button>

                <span className="text-[10px] text-[var(--text-muted)]">
                  Page {Math.floor(sourceOffset / PAGE_SIZE) + 1}{' '}
                  of{' '}
                  {Math.max(
                    1,
                    Math.ceil(filteredSources.length / PAGE_SIZE),
                  )}
                </span>

                <button
                  type="button"
                  disabled={
                    sourceOffset + PAGE_SIZE >=
                    filteredSources.length
                  }
                  onClick={() =>
                    setSourceOffset(sourceOffset + PAGE_SIZE)
                  }
                  className="rounded border border-[var(--border-primary)] px-3 py-2 text-[10px] text-[var(--text-secondary)] disabled:opacity-30"
                >
                  Next →
                </button>

              </div>

            </>
          )}

        </div>
      )}

      {/* OBSERVATION INVENTORY */}

      {activeTab === 'Observations' && (
        <div className="panel">

          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/[0.07] pb-4">

            <div>
              <h3 className="panel-title">
                Observation inventory
              </h3>

              <p className="panel-description">
                INGESTED RECORDS · COLLECTION HISTORY · INTEGRITY
              </p>
            </div>

            <button
              type="button"
              onClick={() => void loadObservations()}
              disabled={observationLoading}
              className="text-[10px] text-[var(--accent-primary)] disabled:opacity-50"
            >
              Refresh
            </button>

          </div>

          <p className="mt-4 text-[10px] text-[var(--text-muted)]">
            {observations.length} observations retrieved · maximum{' '}
            {INVENTORY_LIMIT}
          </p>

          {observationError && (
            <p
              role="alert"
              className="mt-4 text-xs text-rose-300"
            >
              {observationError}
            </p>
          )}

          {observationLoading ? (
            <EmptyMessage>
              Loading observations…
            </EmptyMessage>
          ) : observations.length === 0 ? (
            <EmptyMessage>
              No observations are available.
            </EmptyMessage>
          ) : (
            <>

              <div className="mt-4 space-y-3">
                {visibleObservations.map((observation) => (
                  <article
                    key={observation.observation_id}
                    className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-4"
                  >

                    <div className="flex flex-wrap items-start justify-between gap-3">

                      <div>
                        <p className="font-mono text-xs text-[var(--text-primary)]">
                          {shortId(observation.observation_id)}
                        </p>

                        <p className="mt-1 text-[10px] text-[var(--text-muted)]">
                          {sourceNames.get(observation.source_id) ??
                            shortId(observation.source_id)}
                        </p>
                      </div>

                      <StatusLabel value={observation.status} />

                    </div>

                    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">

                      <div>
                        <p className="text-[9px] text-[var(--text-muted)]">
                          COLLECTED
                        </p>

                        <p className="mt-1 text-[10px] text-[var(--text-secondary)]">
                          {formatDate(observation.collected_at)}
                        </p>
                      </div>

                      <div>
                        <p className="text-[9px] text-[var(--text-muted)]">
                          OBSERVED
                        </p>

                        <p className="mt-1 text-[10px] text-[var(--text-secondary)]">
                          {formatDate(observation.observed_at)}
                        </p>
                      </div>

                      <div>
                        <p className="text-[9px] text-[var(--text-muted)]">
                          PROCESSING VERSION
                        </p>

                        <p className="mt-1 text-[10px] text-[var(--text-secondary)]">
                          {observation.processing_version}
                        </p>
                      </div>

                    </div>

                    <div className="mt-4 border-t border-white/[0.06] pt-3">

                      <p className="text-[9px] text-[var(--text-muted)]">
                        CONTENT SHA-256
                      </p>

                      <p className="mt-1 break-all font-mono text-[9px] leading-5 text-[var(--text-secondary)]">
                        {observation.content_sha256}
                      </p>

                    </div>

                  </article>
                ))}
              </div>

              {/* OBSERVATION PAGINATION */}

              <div className="mt-5 flex items-center justify-between border-t border-white/[0.07] pt-4">

                <button
                  type="button"
                  disabled={observationOffset === 0}
                  onClick={() =>
                    setObservationOffset(
                      Math.max(0, observationOffset - PAGE_SIZE),
                    )
                  }
                  className="rounded border border-[var(--border-primary)] px-3 py-2 text-[10px] text-[var(--text-secondary)] disabled:opacity-30"
                >
                  ← Previous
                </button>

                <span className="text-[10px] text-[var(--text-muted)]">
                  Page{' '}
                  {Math.floor(observationOffset / PAGE_SIZE) + 1}{' '}
                  of{' '}
                  {Math.max(
                    1,
                    Math.ceil(observations.length / PAGE_SIZE),
                  )}
                </span>

                <button
                  type="button"
                  disabled={
                    observationOffset + PAGE_SIZE >=
                    observations.length
                  }
                  onClick={() =>
                    setObservationOffset(
                      observationOffset + PAGE_SIZE,
                    )
                  }
                  className="rounded border border-[var(--border-primary)] px-3 py-2 text-[10px] text-[var(--text-secondary)] disabled:opacity-30"
                >
                  Next →
                </button>

              </div>

            </>
          )}

        </div>
      )}

    </section>
  )
}
