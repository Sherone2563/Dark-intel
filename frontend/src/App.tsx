import { useEffect, useMemo, useState } from 'react'
import './App.css'
import AssetsWorkspace from './components/AssetsWorkspace'
import InvestigationsWorkspace from './components/InvestigationsWorkspace'
import AlertsWorkspace from './components/AlertsWorkspace'
import MonitoringWorkspace from './components/MonitoringWorkspace'

const API = '/api'

type Source = {
  source_id: string
  name: string
  source_type: string
  reliability: string
  authorized_for_use: boolean
  created_at?: string
}

type Observation = {
  observation_id: string
  source_id: string
  collected_at: string
  observed_at: string | null
  status: string
  content_sha256: string
  processing_version: string
}

type Relationship = {
  relationship_id: string
  source_entity_id: string
  target_entity_id: string
  relationship_type: string
  description?: string | null
  created_at?: string
}

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

type Evidence = {
  evidence_id: string
  relationship_id: string
  observation_id: string
  polarity: string
  evidence_description: string
  limitations: string | null
  observed_at: string | null
}

type GraphAnalysis = {
  relationship_id: string
  score: number | null
  confidence_band: string
  supporting_count: number
  contradicting_count: number
  neutral_count: number
  evidence_ids: string[]
  methodology: string
  distinct_source_count: number
  evidence_items_sharing_sources: number
  source_reliability_evidence_counts: Record<string, number>
  source_quality_note: string
  distinct_observation_count: number
}

type GraphEdge = {
  relationship: Relationship
  evidence: Evidence[]
  analysis: GraphAnalysis
}

type EntityGraph = {
  root_entity_id: string
  depth: number
  nodes: Entity[]
  edges: GraphEdge[]
  node_count: number
  edge_count: number
}

type EntityProvenanceRecord = {
  association_id: string
  association_type: string
  field_name: string
  normalization_method: string
  association_created_at: string

  observation_id: string
  collected_at: string
  observed_at: string | null
  content_sha256: string
  processing_version: string

  source_id: string
  source_name: string
  source_type: string
  authorized_for_use: boolean
}

type EntityProvenanceResponse = {
  entity: Entity
  records: EntityProvenanceRecord[]
  record_count: number
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

type TimelineEvent = {
  event_id: string
  event_timestamp: string
  timestamp_basis: string

  relationship_id: string
  relationship_type: string
  relationship_description: string | null
  connected_entity: Entity

  evidence_id: string
  evidence_polarity: string
  evidence_description: string
  evidence_limitations: string | null

  observation_id: string
  observation_observed_at: string | null
  observation_collected_at: string
  content_sha256: string

  source: InvestigationSource
}

type EntityTimelineResponse = {
  entity: Entity
  events: TimelineEvent[]
  event_count: number
}
type IntelligenceReport = {
  metadata: {
    report_id: string
    report_version: string
    generated_at: string
    report_type: string
  }

  subject: Entity

  summary: {
    relationship_count: number
    evidence_record_count: number
    timeline_event_count: number
    distinct_source_count: number
    supporting_evidence_count: number
    contradicting_evidence_count: number
    neutral_evidence_count: number
  }

  methodology: string[]
}
type DashboardData = {
  sources: Source[]
  observations: Observation[]
  entities: Entity[]
  relationships: Relationship[]
}

const navigation = [
  { name: 'Overview', icon: '◫' },
  { name: 'Monitoring', icon: '⌁' },
  { name: 'Intelligence', icon: '⌘' },
  { name: 'Assets', icon: '◎' },
  { name: 'Alerts', icon: '△' },
  { name: 'Investigations', icon: '⌕' },
]

function formatDate(value?: string | null) {
  if (!value) return 'Not recorded'

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) return value

  return date.toLocaleString(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function shortId(value: string) {
  return value.length > 12 ? `${value.slice(0, 8)}…` : value
}

function displayEntity(entity: Entity) {
  return entity.display_value || entity.canonical_value
}

function formatEntityType(value: string) {
  return value.replaceAll('_', ' ')
}

function formatScore(score: number | null) {
  if (score === null || !Number.isFinite(score)) {
    return 'Not calculated'
  }

  return `${score.toFixed(1)}%`
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API}${path}`)

  if (!response.ok) {
    throw new Error(`API returned ${response.status} for ${path}`)
  }

  return response.json() as Promise<T>
}

export default function App() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [activePage, setActivePage] = useState('Overview')

  const [search, setSearch] = useState('')
  const [searchResults, setSearchResults] =
    useState<SearchResponse | null>(null)
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState('')

  const [selectedEntity, setSelectedEntity] =
    useState<Entity | null>(null)

  // Graph exploration state
  const [graph, setGraph] = useState<EntityGraph | null>(null)
  const [graphLoading, setGraphLoading] = useState(false)
  const [graphError, setGraphError] = useState('')
  const [graphDepth, setGraphDepth] = useState(2)
  const [selectedRelationshipId, setSelectedRelationshipId] =
    useState<string | null>(null)

  // Entity investigation data
  const [provenance, setProvenance] =
    useState<EntityProvenanceResponse | null>(null)
  const [timeline, setTimeline] =
    useState<EntityTimelineResponse | null>(null)
  const [report, setReport] =
    useState<IntelligenceReport | null>(null)

  const [provenanceLoading, setProvenanceLoading] = useState(false)
  const [timelineLoading, setTimelineLoading] = useState(false)
  const [reportLoading, setReportLoading] = useState(false)

  const [provenanceError, setProvenanceError] = useState('')
  const [timelineError, setTimelineError] = useState('')
  const [reportError, setReportError] = useState('')

  async function loadDashboard() {
    setLoading(true)
    setError('')

    try {
      const [sources, observations, relationships, entities] = await Promise.all([
        getJson<Source[]>('/sources?limit=100'),
        getJson<Observation[]>('/observations?limit=100'),
        getJson<Relationship[]>('/relationships?limit=100&offset=0'),
        getJson<Entity[]>('/entities?limit=100&offset=0'),
      ])

      setData({
        sources,
        observations,
        relationships,
        entities,
      })
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Could not load dashboard data.',
      )
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // Initial dashboard synchronization with the FastAPI backend.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadDashboard()
  }, [])

  // Fetch a graph whenever the selected entity or graph depth changes.
  useEffect(() => {
    if (activePage !== 'Intelligence' || !selectedEntity) {
      return
    }

    let cancelled = false

    async function fetchGraph() {
      setGraphLoading(true)
      setGraphError('')
      setGraph(null)
      setSelectedRelationshipId(null)

      try {
        const result = await getJson<EntityGraph>(
          `/entities/${encodeURIComponent(selectedEntity!.entity_id)}/graph?depth=${graphDepth}`,
        )

        if (!cancelled) {
          setGraph(result)
        }
      } catch (err) {
        if (!cancelled) {
          setGraphError(
            err instanceof Error
              ? err.message
              : 'Could not retrieve the entity graph.',
          )
        }
      } finally {
        if (!cancelled) {
          setGraphLoading(false)
        }
      }
    }

    void fetchGraph()

    return () => {
      cancelled = true
    }
  }, [activePage, selectedEntity, graphDepth])
    // Fetch provenance, timeline, and intelligence report
  // whenever an entity is selected in the Intelligence workspace.
  useEffect(() => {
    if (activePage !== 'Intelligence' || !selectedEntity) {
      return
    }

    let cancelled = false
    const entityId = encodeURIComponent(selectedEntity.entity_id)

    async function loadInvestigationDetails() {
      setProvenance(null)
      setTimeline(null)
      setReport(null)

      setProvenanceError('')
      setTimelineError('')
      setReportError('')

      setProvenanceLoading(true)
      setTimelineLoading(true)
      setReportLoading(true)

      const results = await Promise.allSettled([
        getJson<EntityProvenanceResponse>(
          `/entities/${entityId}/provenance`,
        ),
        getJson<EntityTimelineResponse>(
          `/entities/${entityId}/timeline`,
        ),
        getJson<IntelligenceReport>(
          `/entities/${entityId}/report`,
        ),
      ])

      if (cancelled) {
        return
      }

      const [provenanceResult, timelineResult, reportResult] = results

      if (provenanceResult.status === 'fulfilled') {
        setProvenance(provenanceResult.value)
      } else {
        setProvenanceError(
          provenanceResult.reason instanceof Error
            ? provenanceResult.reason.message
            : 'Could not retrieve entity provenance.',
        )
      }

      if (timelineResult.status === 'fulfilled') {
        setTimeline(timelineResult.value)
      } else {
        setTimelineError(
          timelineResult.reason instanceof Error
            ? timelineResult.reason.message
            : 'Could not retrieve entity timeline.',
        )
      }

      if (reportResult.status === 'fulfilled') {
        setReport(reportResult.value)
      } else {
        setReportError(
          reportResult.reason instanceof Error
            ? reportResult.reason.message
            : 'Could not generate the intelligence report.',
        )
      }

      setProvenanceLoading(false)
      setTimelineLoading(false)
      setReportLoading(false)
    }

    void loadInvestigationDetails()

    return () => {
      cancelled = true
    }
  }, [activePage, selectedEntity])

  async function runSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!search.trim()) {
      setSearchError('Enter an entity or identifier to search.')
      setSearchResults(null)
      return
    }

    setSearching(true)
    setSearchError('')
    setSelectedEntity(null)
    setGraph(null)

    try {
      const params = new URLSearchParams({
        value: search.trim(),
        limit: '10',
        offset: '0',
      })

      const result = await getJson<SearchResponse>(
        `/entities/search/analyst?${params.toString()}`,
      )

      setSearchResults(result)
    } catch (err) {
      setSearchResults(null)

      setSearchError(
        err instanceof Error
          ? err.message
          : 'Entity search failed.',
      )
    } finally {
      setSearching(false)
    }
  }

  function openEntity(entity: Entity) {
    setSelectedEntity(entity)
    setActivePage('Intelligence')
    setSearchResults(null)
    setSelectedRelationshipId(null)
  }

  function returnToOverview() {
    setSelectedEntity(null)
    setGraph(null)
    setSelectedRelationshipId(null)
    setActivePage('Overview')
  }

  const sourceNames = useMemo(() => {
    const names = new Map<string, string>()

    data?.sources.forEach((source) => {
      names.set(source.source_id, source.name)
    })

    return names
  }, [data])

  const authorizedSources =
    data?.sources.filter((source) => source.authorized_for_use).length ?? 0

  const recentObservations = [...(data?.observations ?? [])]
    .sort(
      (a, b) =>
        new Date(b.collected_at).getTime() -
        new Date(a.collected_at).getTime(),
    )
    .slice(0, 6)

  const totalRetrieved =
    (data?.sources.length ?? 0) +
    (data?.observations.length ?? 0) +
    (data?.relationships.length ?? 0)

  const selectedEdge = graph?.edges.find(
    (edge) => edge.relationship.relationship_id === selectedRelationshipId,
  )
  type GraphPoint = {
  entity: Entity
  x: number
  y: number
  }

    const constellationPoints = useMemo<GraphPoint[]>(() => {
    const entities = data?.entities ?? []

    if (entities.length === 0) {
      return []
    }

    const centerX = 450
    const centerY = 225
    const radiusX = 350
    const radiusY = 165

    // Place entities with more stored connections closer to the center.
    const degree = new Map<string, number>()

    for (const relationship of data?.relationships ?? []) {
      degree.set(
        relationship.source_entity_id,
        (degree.get(relationship.source_entity_id) ?? 0) + 1,
      )
      degree.set(
        relationship.target_entity_id,
        (degree.get(relationship.target_entity_id) ?? 0) + 1,
      )
    }

    const sortedEntities = [...entities].sort((a, b) => {
      const degreeDifference =
        (degree.get(b.entity_id) ?? 0) -
        (degree.get(a.entity_id) ?? 0)

      return degreeDifference ||
        a.entity_id.localeCompare(b.entity_id)
    })

    return sortedEntities.map((entity, index) => {
      const angle =
        (2 * Math.PI * index) / sortedEntities.length -
        Math.PI / 2

      const entityDegree = degree.get(entity.entity_id) ?? 0
      const distanceFactor = entityDegree > 0 ? 0.72 : 1

      return {
        entity,
        x: centerX + radiusX * distanceFactor * Math.cos(angle),
        y: centerY + radiusY * distanceFactor * Math.sin(angle),
      }
    })
  }, [data?.entities, data?.relationships])

  const constellationPointMap = useMemo(() => {
    const map = new Map<string, GraphPoint>()

    constellationPoints.forEach((point) => {
      map.set(point.entity.entity_id, point)
    })

    return map
  }, [constellationPoints])

  const constellationEdges = useMemo(() => {
    return (data?.relationships ?? []).filter(
      (relationship) =>
        constellationPointMap.has(relationship.source_entity_id) &&
        constellationPointMap.has(relationship.target_entity_id),
    )
  }, [data?.relationships, constellationPointMap])
  // Overview-only layout: group entities by actual connected components.
const overviewConstellationPoints = useMemo<GraphPoint[]>(() => {
  const entities = data?.entities ?? []
  const relationships = data?.relationships ?? []

  if (entities.length === 0) return []

  const entityMap = new Map(
    entities.map((entity) => [entity.entity_id, entity]),
  )

  const adjacency = new Map<string, Set<string>>()

  entities.forEach((entity) => {
    adjacency.set(entity.entity_id, new Set())
  })

  relationships.forEach((relationship) => {
    const source = adjacency.get(relationship.source_entity_id)
    const target = adjacency.get(relationship.target_entity_id)

    if (source && target) {
      source.add(relationship.target_entity_id)
      target.add(relationship.source_entity_id)
    }
  })

  // Discover actual connected components using BFS.
  const visited = new Set<string>()
  const components: string[][] = []

  entities.forEach((entity) => {
    if (visited.has(entity.entity_id)) return

    const component: string[] = []
    const queue = [entity.entity_id]

    visited.add(entity.entity_id)

    while (queue.length > 0) {
      const current = queue.shift()!
      component.push(current)

      adjacency.get(current)?.forEach((neighbor) => {
        if (!visited.has(neighbor)) {
          visited.add(neighbor)
          queue.push(neighbor)
        }
      })
    }

    components.push(component)
  })

  // Larger connected groups receive earlier, central positions.
  components.sort((a, b) => {
    return b.length - a.length || a[0].localeCompare(b[0])
  })

  const columns = Math.ceil(Math.sqrt(components.length))
  const rows = Math.ceil(components.length / columns)

  const cellWidth = 760 / columns
  const cellHeight = 340 / rows

  const result: GraphPoint[] = []

  components.forEach((component, componentIndex) => {
    const column = componentIndex % columns
    const row = Math.floor(componentIndex / columns)

    const centerX = 70 + cellWidth * (column + 0.5)
    const centerY = 55 + cellHeight * (row + 0.5)

    // Single entities remain visible as isolated points.
    if (component.length === 1) {
      const entity = entityMap.get(component[0])

      if (entity) {
        result.push({
          entity,
          x: centerX,
          y: centerY,
        })
      }

      return
    }

    // Arrange members around their component's local center.
    const radius = Math.min(
      68,
      24 + component.length * 9,
      cellWidth * 0.32,
      cellHeight * 0.32,
    )

    component.forEach((entityId, index) => {
      const entity = entityMap.get(entityId)
      if (!entity) return

      const angle =
        (2 * Math.PI * index) / component.length -
        Math.PI / 2

      result.push({
        entity,
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle),
      })
    })
  })

  return result
}, [data?.entities, data?.relationships])

const overviewConstellationPointMap = useMemo(() => {
  const map = new Map<string, GraphPoint>()

  overviewConstellationPoints.forEach((point) => {
    map.set(point.entity.entity_id, point)
  })

  return map
}, [overviewConstellationPoints])

const overviewConstellationEdges = useMemo(() => {
  return (data?.relationships ?? []).filter(
    (relationship) =>
      overviewConstellationPointMap.has(relationship.source_entity_id) &&
      overviewConstellationPointMap.has(relationship.target_entity_id),
  )
}, [data?.relationships, overviewConstellationPointMap])

  return (
    <div className="app-shell">
      {/* TOP HEADER */}

      <header className="top-header">
        <div className="brand">
          <div className="brand-mark">
            <span className="brand-symbol">◐</span>
          </div>

          <div className="brand-copy">
            <h1 className="brand-name">ECLIPSE NEXUS</h1>
            <p className="brand-subtitle">
              DARK WEB INTELLIGENCE
            </p>
          </div>
        </div>

        <form
          onSubmit={runSearch}
          className="global-search"
        >
          <span className="search-icon">⌕</span>

          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search domains, handles, emails, indicators..."
            maxLength={2048}
            aria-label="Search intelligence entities"
          />

          <button
            type="submit"
            disabled={searching}
            className="search-submit"
          >
            {searching ? 'SEARCHING...' : 'SEARCH'}
          </button>
        </form>

        <div className="header-actions">
          <div className="status-live">
            <span className="status-dot" />
            <span>API CONNECTED</span>
          </div>

          <button
            type="button"
            onClick={() => {
              if (activePage === 'Intelligence' && selectedEntity) {
                setGraph(null)
                setGraphError('')
                setGraphDepth((current) => current)
              } else {
                void loadDashboard()
              }
            }}
            disabled={loading || graphLoading}
            className="header-refresh"
            title="Refresh current data"
            aria-label="Refresh current data"
          >
            <span className="refresh-icon">↻</span>
            <span>Refresh</span>
          </button>

          <div
            className="profile-avatar"
            title="Analyst profile"
            aria-label="Analyst profile"
          >
            AL
          </div>
        </div>
      </header>

      {/* HORIZONTAL NAVIGATION */}

      <div className="navigation-bar">
        <nav
          className="navigation-items"
          aria-label="Main navigation"
        >
          {navigation.map((item) => (
            <button
              key={item.name}
              type="button"
              onClick={() => {
                setActivePage(item.name)

                if (item.name !== 'Intelligence') {
                  setSelectedEntity(null)
                  setGraph(null)
                  setSelectedRelationshipId(null)
                }
              }}
              className={`navigation-item ${
                activePage === item.name ? 'active' : ''
              }`}
              aria-current={
                activePage === item.name ? 'page' : undefined
              }
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.name}</span>

              {item.name === 'Alerts' && data && (
                <span className="nav-count">
                  {data.observations.length}
                </span>
              )}
            </button>
          ))}
        </nav>

        <div className="workspace-indicator">
          <span className="workspace-dot" />
          <span>AUTHORIZED RESEARCH</span>
        </div>
      </div>

      {/* MAIN CONTENT */}

      <main className="main-content">
        <div className="page-intro">
          <div>
            <p className="page-eyebrow">
              SEE THE CONNECTION. STOP THE EXPOSURE.
            </p>

            <h2 className="page-title">
              {activePage === 'Intelligence' && selectedEntity
                ? displayEntity(selectedEntity)
                : activePage === 'Overview'
                  ? 'Your perimeter, connected.'
                  : activePage}
            </h2>

            <p className="page-description">
              {activePage === 'Intelligence' && selectedEntity
                ? `Entity record · ${formatEntityType(selectedEntity.entity_type)} · ${selectedEntity.canonical_value}`
                : activePage === 'Intelligence'
                  ? 'Explore registered entities and evidence-backed connections.'
                  : 'Explore registered entities, collected observations, and evidence-backed relationships.'}
            </p>
          </div>

          <div className="page-data-status">
            <span className="status-dot" />
            <span>LIVE DATA FROM YOUR API</span>
          </div>
        </div>

        {/* SEARCH ERROR */}

        {searchError && (
          <div
            role="alert"
            className="mt-5 rounded border border-rose-400/20 bg-rose-400/[0.06] p-3 text-xs text-rose-300"
          >
            {searchError}
          </div>
        )}

        {/* SEARCH RESULTS */}

        {searchResults && (
          <section className="mt-5 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-secondary)] p-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-medium text-[var(--text-primary)]">
                Entity search results
              </h3>

              <button
                type="button"
                onClick={() => setSearchResults(null)}
                className="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)]"
              >
                Close ×
              </button>
            </div>

            <p className="mb-3 text-[11px] text-[var(--text-muted)]">
              {searchResults.result_count} matching records
            </p>

            {searchResults.results.length === 0 ? (
              <p className="text-xs text-[var(--text-secondary)]">
                No matching entities found.
              </p>
            ) : (
              <div className="divide-y divide-white/[0.06]">
                {searchResults.results.map((result) => (
                  <button
                    key={result.entity.entity_id}
                    type="button"
                    onClick={() => openEntity(result.entity)}
                    className="flex w-full flex-wrap items-center justify-between gap-3 py-3 text-left hover:bg-white/[0.025]"
                  >
                    <span>
                      <span className="block text-xs text-[var(--text-primary)]">
                        {displayEntity(result.entity)}
                      </span>

                      <span className="mt-1 block font-mono text-[10px] text-[var(--text-muted)]">
                        {result.entity.entity_type} ·{' '}
                        {result.entity.canonical_value}
                      </span>
                    </span>

                    <span className="text-[10px] text-[var(--text-secondary)]">
                      {result.authorized_observation_count} observations
                      {' · '}
                      {result.supported_relationship_count} supported links
                      {' · '}
                      {result.contradicting_evidence_count} contradictions
                    </span>
                  </button>
                ))}
              </div>
            )}
          </section>
        )}

        {/* INTELLIGENCE CONSTELLATION */}

        {activePage === 'Intelligence' ? (
          <section className="mt-7 space-y-5">
            {!selectedEntity ? (
              <div className="panel py-16 text-center">
                <p className="text-sm font-medium text-[var(--text-primary)]">
                  Intelligence graph explorer
                </p>

                <p className="mx-auto mt-3 max-w-lg text-xs leading-6 text-[var(--text-secondary)]">
                  Search for a registered entity above and select a result
                  to explore its stored relationships and authorized
                  evidence.
                </p>

                <p className="mt-5 text-[10px] text-[var(--text-muted)]">
                  GRAPH DATA IS RETRIEVED FROM THE FASTAPI BACKEND
                </p>
              </div>
            ) : (
              <>
                <div className="panel">
                  <div className="flex flex-wrap items-center justify-between gap-4">
                    <div>
                      <p className="text-[10px] font-semibold tracking-[0.16em] text-[var(--accent-secondary)]">
                        ENTITY GRAPH EXPLORER
                      </p>

                      <h3 className="mt-2 text-sm font-semibold text-[var(--text-primary)]">
                        {displayEntity(selectedEntity)}
                      </h3>

                      <p className="mt-1 break-all font-mono text-[10px] text-[var(--text-muted)]">
                        {selectedEntity.entity_id}
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                      <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                        Graph depth

                        <select
                          value={graphDepth}
                          onChange={(event) =>
                            setGraphDepth(Number(event.target.value))
                          }
                          className="rounded border border-[var(--border-primary)] bg-[var(--bg-primary)] px-3 py-2 text-xs text-[var(--text-primary)]"
                        >
                          <option value={1}>1 level</option>
                          <option value={2}>2 levels</option>
                          <option value={3}>3 levels</option>
                        </select>
                      </label>

                      <button
                        type="button"
                        onClick={() => {
                          setGraph(null)
                          setGraphError('')
                          setGraphDepth((current) =>
                            current === 1 ? 2 : 1,
                          )
                        }}
                        className="rounded border border-[var(--border-primary)] px-3 py-2 text-xs text-[var(--accent-primary)] hover:bg-white/[0.04]"
                      >
                        Reload graph
                      </button>

                      <button
                        type="button"
                        onClick={returnToOverview}
                        className="rounded border border-[var(--border-subtle)] px-3 py-2 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                      >
                        Back to overview
                      </button>
                    </div>
                  </div>
                </div>

                {graphLoading && (
                  <div className="panel py-16 text-center">
                    <p className="text-sm text-[var(--accent-primary)]">
                      Loading entity graph…
                    </p>

                    <p className="mt-2 text-xs text-[var(--text-muted)]">
                      Retrieving stored entities, relationships, and
                      authorized evidence.
                    </p>
                  </div>
                )}

                {graphError && (
                  <div
                    role="alert"
                    className="rounded border border-rose-400/20 bg-rose-400/[0.06] p-4"
                  >
                    <p className="text-sm text-rose-300">
                      Graph retrieval failed
                    </p>

                    <p className="mt-2 break-words text-xs text-rose-200/70">
                      {graphError}
                    </p>

                    <button
                      type="button"
                      onClick={() => {
                        setGraph(null)
                        setGraphError('')
                        setGraphDepth((current) =>
                          current === 1 ? 2 : 1,
                        )
                      }}
                      className="mt-4 text-xs text-rose-300 underline"
                    >
                      Retry graph retrieval
                    </button>
                  </div>
                )}

                {graph && !graphLoading && (
                  <>
                    {/* GRAPH SUMMARY */}

                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                      <MetricCard
                        label="GRAPH NODES"
                        value={String(graph.node_count)}
                        detail="Entities returned by API"
                        loading={false}
                        accent
                      />

                      <MetricCard
                        label="RELATIONSHIPS"
                        value={String(graph.edge_count)}
                        detail="Stored relationship records"
                        loading={false}
                      />

                      <MetricCard
                        label="GRAPH DEPTH"
                        value={String(graph.depth)}
                        detail="Requested traversal depth"
                        loading={false}
                      />
                    </div>

                    {/* GRAPH VISUALIZATION */}

                    <div className="panel min-w-0">
  <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/[0.07] pb-4">
    <div>
      <h3 className="panel-title">Intelligence activity</h3>
      <p className="panel-description">
        ENTITY CONSTELLATION · STORED RELATIONSHIPS
      </p>
    </div>

    <div className="flex items-center gap-3 text-[10px] text-[var(--text-muted)]">
      <span>{data?.entities.length ?? 0} entities</span>
      <span className="h-1 w-1 rounded-full bg-[var(--accent-primary)]" />
      <span>{constellationEdges.length} relationships</span>
    </div>
  </div>

  {loading ? (
    <div className="flex h-[300px] items-center justify-center text-xs text-[var(--text-muted)]">
      Loading intelligence constellation…
    </div>
  ) : error ? (
    <div className="flex h-[300px] items-center justify-center text-xs text-rose-300">
      Constellation data could not be loaded.
    </div>
  ) : !constellationPoints.length ? (
    <div className="flex h-[300px] flex-col items-center justify-center gap-2 text-center">
      <span className="text-2xl text-[var(--accent-primary)]">✳</span>
      <p className="text-sm text-[var(--text-secondary)]">
        No entities available
      </p>
      <p className="text-[10px] text-[var(--text-muted)]">
        Registered entities will appear here when available.
      </p>
    </div>
  ) : (
    <div className="pt-4">
      <div className="overflow-hidden rounded-lg bg-[#0b0b18]/70">
        <svg
          viewBox="0 0 900 450"
          className="h-[300px] w-full sm:h-[340px]"
          role="img"
          aria-label="Entity constellation showing stored relationships"
        >
          <defs>
            <radialGradient id="constellationGlow">
              <stop offset="0%" stopColor="#a78bfa" stopOpacity="0.2" />
              <stop offset="100%" stopColor="#a78bfa" stopOpacity="0" />
            </radialGradient>
          </defs>

          <circle
            cx="450"
            cy="225"
            r="190"
            fill="url(#constellationGlow)"
          />

          {constellationEdges.map((relationship) => {
            const source = constellationPointMap.get(
              relationship.source_entity_id,
            )
            const target = constellationPointMap.get(
              relationship.target_entity_id,
            )

            if (!source || !target) return null

            return (
              <line
                key={relationship.relationship_id}
                x1={source.x}
                y1={source.y}
                x2={target.x}
                y2={target.y}
                stroke="#8b7cf6"
                strokeOpacity="0.65"
                strokeWidth="1.5"
              >
                <title>
                  {formatEntityType(relationship.relationship_type)}
                  {relationship.description
                    ? ` — ${relationship.description}`
                    : ''}
                </title>
              </line>
            )
          })}

          {constellationPoints.map((point) => {
            const entity = point.entity
            const isConnected = constellationEdges.some(
              (relationship) =>
                relationship.source_entity_id === entity.entity_id ||
                relationship.target_entity_id === entity.entity_id,
            )

            return (
              <g
                key={entity.entity_id}
                transform={`translate(${point.x}, ${point.y})`}
                className="cursor-pointer"
                role="button"
                tabIndex={0}
                aria-label={`Open ${displayEntity(entity)} in Intelligence`}
                onClick={() => openEntity(entity)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    openEntity(entity)
                  }
                }}
              >
                <circle
                  r={isConnected ? 17 : 12}
                  fill="#8b7cf6"
                  fillOpacity={isConnected ? 0.18 : 0.1}
                  stroke="#a78bfa"
                  strokeOpacity={isConnected ? 0.9 : 0.5}
                  strokeWidth="1"
                />

                <circle
                  r={isConnected ? 5 : 4}
                  fill={isConnected ? '#c4b5fd' : '#77718e'}
                />

                <text
                  y="29"
                  textAnchor="middle"
                  fill="#d8d4e8"
                  fontSize="10"
                >
                  {displayEntity(entity).length > 18
                    ? `${displayEntity(entity).slice(0, 16)}…`
                    : displayEntity(entity)}
                </text>

                <title>
                  {displayEntity(entity)} · {formatEntityType(entity.entity_type)}
                  {' · Click to investigate'}
                </title>
              </g>
            )
          })}
        </svg>
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.06] pt-3">
        <div className="flex flex-wrap gap-4 text-[10px] text-[var(--text-muted)]">
          <span className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-[#c4b5fd]" />
            Connected entity
          </span>
          <span className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-[#77718e]" />
            Unconnected entity
          </span>
        </div>

        <span className="text-[10px] text-[var(--text-muted)]">
          Select a node to investigate
        </span>
      </div>

      <p className="mt-3 text-[10px] leading-5 text-[var(--text-muted)]">
        Showing up to 100 retrieved entities and 100 stored relationships.
        Lines represent recorded relationships only; they do not establish
        identity or attribution.
      </p>
    </div>
  )}
</div>

                    {/* RELATIONSHIP LIST */}

                    <div className="panel">
                      <div className="border-b border-white/[0.07] pb-4">
                        <h3 className="panel-title">
                          Relationship records
                        </h3>

                        <p className="panel-description">
                          SELECT A RELATIONSHIP TO VIEW ITS EVIDENCE AND
                          ANALYTICAL ASSESSMENT
                        </p>
                      </div>

                      {graph.edges.length === 0 ? (
                        <EmptyState message="No relationships were returned for this entity." />
                      ) : (
                        <div className="mt-4 space-y-3">
                          {graph.edges.map((edge) => {
                            const relationship = edge.relationship
                            const isSelected =
                              selectedRelationshipId ===
                              relationship.relationship_id

                            const source = graph.nodes.find(
                              (node) =>
                                node.entity_id ===
                                relationship.source_entity_id,
                            )

                            const target = graph.nodes.find(
                              (node) =>
                                node.entity_id ===
                                relationship.target_entity_id,
                            )

                            return (
                              <button
                                key={relationship.relationship_id}
                                type="button"
                                onClick={() =>
                                  setSelectedRelationshipId(
                                    relationship.relationship_id,
                                  )
                                }
                                className={`w-full rounded-lg border p-4 text-left transition ${
                                  isSelected
                                    ? 'border-[var(--accent-primary)] bg-[var(--bg-card-hover)]'
                                    : 'border-[var(--border-subtle)] bg-[var(--bg-secondary)] hover:border-[var(--border-primary)]'
                                }`}
                              >
                                <div className="flex flex-wrap items-center justify-between gap-3">
                                  <span className="text-xs font-semibold text-[var(--text-primary)]">
                                    {formatEntityType(
                                      relationship.relationship_type,
                                    )}
                                  </span>

                                  <span className="text-[10px] text-[var(--text-muted)]">
                                    {edge.evidence.length} authorized
                                    evidence records
                                  </span>
                                </div>

                                <div className="mt-3 grid grid-cols-[1fr_auto_1fr] items-center gap-3">
                                  <span className="truncate font-mono text-[10px] text-[var(--text-secondary)]">
                                    {source
                                      ? displayEntity(source)
                                      : shortId(
                                          relationship.source_entity_id,
                                        )}
                                  </span>

                                  <span className="text-[var(--accent-primary)]">
                                    ↔
                                  </span>

                                  <span className="truncate text-right font-mono text-[10px] text-[var(--text-secondary)]">
                                    {target
                                      ? displayEntity(target)
                                      : shortId(
                                          relationship.target_entity_id,
                                        )}
                                  </span>
                                </div>

                                <div className="mt-3 flex flex-wrap gap-4 text-[10px] text-[var(--text-muted)]">
                                  <span>
                                    Score:{' '}
                                    {formatScore(edge.analysis.score)}
                                  </span>

                                  <span>
                                    Band:{' '}
                                    {edge.analysis.confidence_band}
                                  </span>

                                  <span>
                                    Supporting:{' '}
                                    {edge.analysis.supporting_count}
                                  </span>

                                  <span>
                                    Contradicting:{' '}
                                    {edge.analysis.contradicting_count}
                                  </span>
                                </div>
                              </button>
                            )
                          })}
                        </div>
                      )}
                    </div>

                    {/* SELECTED RELATIONSHIP DETAILS */}

                    {selectedEdge && (
                      <div className="panel">
                        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/[0.07] pb-4">
                          <div>
                            <p className="text-[10px] tracking-[0.15em] text-[var(--accent-secondary)]">
                              RELATIONSHIP ASSESSMENT
                            </p>

                            <h3 className="mt-2 text-sm font-semibold text-[var(--text-primary)]">
                              {formatEntityType(
                                selectedEdge.relationship.relationship_type,
                              )}
                            </h3>

                            <p className="mt-1 font-mono text-[9px] text-[var(--text-muted)]">
                              {selectedEdge.relationship.relationship_id}
                            </p>
                          </div>

                          <button
                            type="button"
                            onClick={() =>
                              setSelectedRelationshipId(null)
                            }
                            className="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                          >
                            Close ×
                          </button>
                        </div>

                        {selectedEdge.relationship.description && (
                          <p className="mt-4 text-xs leading-6 text-[var(--text-secondary)]">
                            {selectedEdge.relationship.description}
                          </p>
                        )}

                        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
                          <AssessmentValue
                            label="LINKAGE SCORE"
                            value={formatScore(
                              selectedEdge.analysis.score,
                            )}
                          />

                          <AssessmentValue
                            label="CONFIDENCE BAND"
                            value={
                              selectedEdge.analysis.confidence_band
                            }
                          />

                          <AssessmentValue
                            label="SUPPORTING"
                            value={String(
                              selectedEdge.analysis.supporting_count,
                            )}
                          />

                          <AssessmentValue
                            label="CONTRADICTING"
                            value={String(
                              selectedEdge.analysis.contradicting_count,
                            )}
                          />
                        </div>

                        <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
                          <AssessmentValue
                            label="NEUTRAL EVIDENCE"
                            value={String(
                              selectedEdge.analysis.neutral_count,
                            )}
                          />

                          <AssessmentValue
                            label="DISTINCT SOURCES"
                            value={String(
                              selectedEdge.analysis.distinct_source_count,
                            )}
                          />

                          <AssessmentValue
                            label="DISTINCT OBSERVATIONS"
                            value={String(
                              selectedEdge.analysis.distinct_observation_count,
                            )}
                          />
                        </div>

                        <div className="mt-6">
                          <h4 className="text-xs font-semibold text-[var(--text-primary)]">
                            Authorized evidence
                          </h4>

                          <p className="mt-1 text-[10px] text-[var(--text-muted)]">
                            Evidence records returned by the backend for
                            authorized sources.
                          </p>

                          {selectedEdge.evidence.length === 0 ? (
                            <EmptyState message="No authorized evidence records were returned for this relationship." />
                          ) : (
                            <div className="mt-4 space-y-3">
                              {selectedEdge.evidence.map((evidence) => (
                                <article
                                  key={evidence.evidence_id}
                                  className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-4"
                                >
                                  <div className="flex flex-wrap items-center justify-between gap-3">
                                    <span
                                      className={`rounded border px-2 py-1 text-[9px] uppercase tracking-wider ${
                                        evidence.polarity === 'supports'
                                          ? 'border-emerald-400/20 text-emerald-300'
                                          : evidence.polarity ===
                                              'contradicts'
                                            ? 'border-rose-400/20 text-rose-300'
                                            : 'border-[var(--border-primary)] text-[var(--text-secondary)]'
                                      }`}
                                    >
                                      {evidence.polarity}
                                    </span>

                                    <span className="text-[10px] text-[var(--text-muted)]">
                                      {formatDate(evidence.observed_at)}
                                    </span>
                                  </div>

                                  <p className="mt-3 text-xs leading-6 text-[var(--text-primary)]">
                                    {evidence.evidence_description}
                                  </p>

                                  {evidence.limitations && (
                                    <p className="mt-3 text-[10px] leading-5 text-[var(--text-secondary)]">
                                      <strong>Limitations:</strong>{' '}
                                      {evidence.limitations}
                                    </p>
                                  )}

                                  <div className="mt-3 border-t border-white/[0.06] pt-3">
                                    <p className="font-mono text-[9px] text-[var(--text-muted)]">
                                      Evidence: {evidence.evidence_id}
                                    </p>

                                    <p className="mt-1 font-mono text-[9px] text-[var(--text-muted)]">
                                      Observation:{' '}
                                      {evidence.observation_id}
                                    </p>
                                  </div>
                                </article>
                              ))}
                            </div>
                          )}
                        </div>

                        <div className="mt-5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-4">
                          <h4 className="text-xs font-semibold text-[var(--text-primary)]">
                            Methodology
                          </h4>

                          <p className="mt-2 text-xs leading-6 text-[var(--text-secondary)]">
                            {selectedEdge.analysis.methodology}
                          </p>

                          <p className="mt-4 text-[10px] leading-5 text-[var(--text-muted)]">
                            {selectedEdge.analysis.source_quality_note}
                          </p>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </>
            )}            {/* ENTITY PROVENANCE */}

            <section className="mt-6 panel">
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/[0.07] pb-4">
                <div>
                  <p className="text-[10px] tracking-[0.15em] text-[var(--accent-secondary)]">
                    DATA LINEAGE
                  </p>
                  <h3 className="mt-2 text-sm font-semibold text-[var(--text-primary)]">
                    Entity provenance
                  </h3>
                  <p className="mt-1 text-[10px] text-[var(--text-muted)]">
                    EXTRACTION HISTORY, SOURCE AUTHORIZATION AND INTEGRITY
                  </p>
                </div>

                <span className="rounded border border-[var(--border-primary)] px-3 py-1 text-[10px] text-[var(--text-secondary)]">
                  {provenance
                    ? `${provenance.record_count} records`
                    : 'Provenance'}
                </span>
              </div>

              {provenanceLoading ? (
                <p className="mt-5 text-xs text-[var(--text-muted)]">
                  Retrieving provenance records...
                </p>
              ) : provenanceError ? (
                <p role="alert" className="mt-5 text-xs text-rose-300">
                  {provenanceError}
                </p>
              ) : !provenance || provenance.records.length === 0 ? (
                <div className="mt-5">
                  <EmptyState message="No provenance records are available for this entity." />
                </div>
              ) : (
                <div className="mt-4 space-y-3">
                  {provenance.records.map((record) => (
                    <article
                      key={record.association_id}
                      className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-4"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="text-xs font-semibold text-[var(--text-primary)]">
                            {record.field_name}
                          </p>
                          <p className="mt-1 text-[10px] text-[var(--text-muted)]">
                            {record.association_type} ·{' '}
                            {record.normalization_method}
                          </p>
                        </div>

                        <span
                          className={`rounded border px-2 py-1 text-[9px] ${
                            record.authorized_for_use
                              ? 'border-emerald-400/20 text-emerald-300'
                              : 'border-rose-400/20 text-rose-300'
                          }`}
                        >
                          {record.authorized_for_use
                            ? 'AUTHORIZED SOURCE'
                            : 'NOT AUTHORIZED'}
                        </span>
                      </div>

                      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                        <div>
                          <p className="text-[9px] text-[var(--text-muted)]">
                            SOURCE
                          </p>
                          <p className="mt-1 text-xs text-[var(--text-secondary)]">
                            {record.source_name}
                          </p>
                          <p className="mt-1 text-[10px] text-[var(--text-muted)]">
                            {record.source_type}
                          </p>
                        </div>

                        <div>
                          <p className="text-[9px] text-[var(--text-muted)]">
                            PROCESSING VERSION
                          </p>
                          <p className="mt-1 text-xs text-[var(--text-secondary)]">
                            {record.processing_version}
                          </p>
                        </div>

                        <div>
                          <p className="text-[9px] text-[var(--text-muted)]">
                            COLLECTED AT
                          </p>
                          <p className="mt-1 text-xs text-[var(--text-secondary)]">
                            {formatDate(record.collected_at)}
                          </p>
                        </div>

                        <div>
                          <p className="text-[9px] text-[var(--text-muted)]">
                            OBSERVED AT
                          </p>
                          <p className="mt-1 text-xs text-[var(--text-secondary)]">
                            {formatDate(record.observed_at)}
                          </p>
                        </div>
                      </div>

                      <div className="mt-4 border-t border-white/[0.06] pt-3">
                        <p className="text-[9px] text-[var(--text-muted)]">
                          CONTENT SHA-256
                        </p>
                        <p className="mt-1 break-all font-mono text-[9px] leading-5 text-[var(--text-secondary)]">
                          {record.content_sha256}
                        </p>
                        <p className="mt-2 break-all font-mono text-[9px] text-[var(--text-muted)]">
                          Observation: {record.observation_id}
                        </p>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>

            {/* ENTITY TIMELINE */}

            <section className="mt-6 panel">
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/[0.07] pb-4">
                <div>
                  <p className="text-[10px] tracking-[0.15em] text-[var(--accent-secondary)]">
                    CHRONOLOGICAL INTELLIGENCE
                  </p>
                  <h3 className="mt-2 text-sm font-semibold text-[var(--text-primary)]">
                    Entity timeline
                  </h3>
                  <p className="mt-1 text-[10px] text-[var(--text-muted)]">
                    EVIDENCE-BACKED EVENTS AND CONNECTED ENTITIES
                  </p>
                </div>

                <span className="rounded border border-[var(--border-primary)] px-3 py-1 text-[10px] text-[var(--text-secondary)]">
                  {timeline
                    ? `${timeline.event_count} events`
                    : 'Timeline'}
                </span>
              </div>

              {timelineLoading ? (
                <p className="mt-5 text-xs text-[var(--text-muted)]">
                  Retrieving timeline events...
                </p>
              ) : timelineError ? (
                <p role="alert" className="mt-5 text-xs text-rose-300">
                  {timelineError}
                </p>
              ) : !timeline || timeline.events.length === 0 ? (
                <div className="mt-5">
                  <EmptyState message="No timeline events are available for this entity." />
                </div>
              ) : (
                <div className="mt-5 space-y-4">
                  {timeline.events.map((event) => (
                    <article
                      key={event.event_id}
                      className="relative border-l border-[var(--border-primary)] pl-5"
                    >
                      <span className="absolute -left-[5px] top-1 h-2 w-2 rounded-full bg-[var(--accent-primary)]" />

                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-[10px] text-[var(--accent-primary)]">
                          {formatDate(event.event_timestamp)}
                        </span>

                        <span
                          className={`rounded border px-2 py-1 text-[9px] uppercase ${
                            event.evidence_polarity === 'supports'
                              ? 'border-emerald-400/20 text-emerald-300'
                              : event.evidence_polarity === 'contradicts'
                                ? 'border-rose-400/20 text-rose-300'
                                : 'border-[var(--border-primary)] text-[var(--text-secondary)]'
                          }`}
                        >
                          {event.evidence_polarity}
                        </span>
                      </div>

                      <h4 className="mt-2 text-xs font-semibold text-[var(--text-primary)]">
                        {formatEntityType(event.relationship_type)}
                      </h4>

                      <p className="mt-2 text-xs leading-6 text-[var(--text-secondary)]">
                        {event.evidence_description}
                      </p>

                      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                        <div>
                          <p className="text-[9px] text-[var(--text-muted)]">
                            CONNECTED ENTITY
                          </p>
                          <p className="mt-1 break-all font-mono text-[10px] text-[var(--text-secondary)]">
                            {displayEntity(event.connected_entity)}
                          </p>
                        </div>

                        <div>
                          <p className="text-[9px] text-[var(--text-muted)]">
                            SOURCE
                          </p>
                          <p className="mt-1 text-[10px] text-[var(--text-secondary)]">
                            {event.source.name} · {event.source.reliability}
                          </p>
                        </div>
                      </div>

                      {event.evidence_limitations && (
                        <p className="mt-3 text-[10px] leading-5 text-[var(--text-muted)]">
                          <strong>Limitations:</strong>{' '}
                          {event.evidence_limitations}
                        </p>
                      )}

                      <div className="mt-3 space-y-1">
                        <p className="font-mono text-[9px] text-[var(--text-muted)]">
                          Timestamp basis: {event.timestamp_basis}
                        </p>
                        <p className="break-all font-mono text-[9px] text-[var(--text-muted)]">
                          Evidence: {event.evidence_id}
                        </p>
                        <p className="break-all font-mono text-[9px] text-[var(--text-muted)]">
                          Observation: {event.observation_id}
                        </p>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>

            {/* INTELLIGENCE REPORT */}

            <section className="mt-6 panel">
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/[0.07] pb-4">
                <div>
                  <p className="text-[10px] tracking-[0.15em] text-[var(--accent-secondary)]">
                    ASSESSMENT OUTPUT
                  </p>
                  <h3 className="mt-2 text-sm font-semibold text-[var(--text-primary)]">
                    Intelligence report
                  </h3>
                  <p className="mt-1 text-[10px] text-[var(--text-muted)]">
                    GENERATED ENTITY INVESTIGATION SUMMARY
                  </p>
                </div>

                <span className="rounded border border-[var(--border-primary)] px-3 py-1 text-[10px] text-[var(--text-secondary)]">
                  {report?.metadata.report_version ?? 'REPORT'}
                </span>
              </div>

              {reportLoading ? (
                <p className="mt-5 text-xs text-[var(--text-muted)]">
                  Generating intelligence report...
                </p>
              ) : reportError ? (
                <p role="alert" className="mt-5 text-xs text-rose-300">
                  {reportError}
                </p>
              ) : !report ? (
                <div className="mt-5">
                  <EmptyState message="No intelligence report is available." />
                </div>
              ) : (
                <>
                  <div className="mt-4">
                    <p className="text-[9px] tracking-wider text-[var(--text-muted)]">
                      REPORT SUBJECT
                    </p>
                    <p className="mt-2 break-all font-mono text-sm text-[var(--text-primary)]">
                      {displayEntity(report.subject)}
                    </p>
                    <p className="mt-1 break-all font-mono text-[9px] text-[var(--text-muted)]">
                      {report.subject.entity_id}
                    </p>
                  </div>

                  <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
                    <AssessmentValue
                      label="RELATIONSHIPS"
                      value={String(report.summary.relationship_count)}
                    />
                    <AssessmentValue
                      label="EVIDENCE RECORDS"
                      value={String(report.summary.evidence_record_count)}
                    />
                    <AssessmentValue
                      label="TIMELINE EVENTS"
                      value={String(report.summary.timeline_event_count)}
                    />
                    <AssessmentValue
                      label="DISTINCT SOURCES"
                      value={String(report.summary.distinct_source_count)}
                    />
                    <AssessmentValue
                      label="SUPPORTING"
                      value={String(report.summary.supporting_evidence_count)}
                    />
                    <AssessmentValue
                      label="CONTRADICTING"
                      value={String(report.summary.contradicting_evidence_count)}
                    />
                  </div>

                  <div className="mt-5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-4">
                    <h4 className="text-xs font-semibold text-[var(--text-primary)]">
                      Report metadata
                    </h4>

                    <div className="mt-3 space-y-2 text-[10px] text-[var(--text-secondary)]">
                      <p>
                        Report ID:{' '}
                        <span className="break-all font-mono">
                          {report.metadata.report_id}
                        </span>
                      </p>
                      <p>
                        Generated: {formatDate(report.metadata.generated_at)}
                      </p>
                      <p>Type: {report.metadata.report_type}</p>
                    </div>
                  </div>

                  <div className="mt-5">
                    <h4 className="text-xs font-semibold text-[var(--text-primary)]">
                      Methodology
                    </h4>

                    <ul className="mt-3 space-y-2">
                      {report.methodology.map((item, index) => (
                        <li
                          key={`${index}-${item}`}
                          className="flex gap-2 text-xs leading-5 text-[var(--text-secondary)]"
                        >
                          <span className="text-[var(--accent-primary)]">
                            •
                          </span>
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <p className="mt-5 border-t border-white/[0.07] pt-4 text-[10px] leading-5 text-[var(--text-muted)]">
                    This report presents evidence-backed analytical
                    relationships. Linkage assessments do not establish
                    real-world identity or prove attribution.
                  </p>
                </>
              )}
            </section>
          </section>
        ) : selectedEntity ? (
          /* SELECTED ENTITY FALLBACK */

          <section className="mt-7 panel">
            <button
              type="button"
              onClick={returnToOverview}
              className="mb-5 text-xs text-[var(--accent-primary)] hover:text-[var(--text-primary)]"
            >
              ← Back to overview
            </button>

            <p className="text-[10px] tracking-[0.16em] text-[var(--text-muted)]">
              REGISTERED ENTITY
            </p>

            <p className="mt-3 break-all font-mono text-sm text-[var(--text-primary)]">
              {selectedEntity.canonical_value}
            </p>

            <p className="mt-3 text-xs text-[var(--text-secondary)]">
              Entity ID: {selectedEntity.entity_id}
            </p>
          </section>
        ) : activePage === 'Monitoring' ? (
          <MonitoringWorkspace />
        ) : activePage === 'Assets' ? (
          <AssetsWorkspace onOpenEntity={openEntity} />
          ) : activePage === 'Investigations' ? (
          <InvestigationsWorkspace />
          ) : activePage === 'Alerts' ? (
            <AlertsWorkspace />
        ) : activePage !== 'Overview' ? (
          /* OTHER WORKSPACES */

          <section className="mt-7 rounded-lg border border-dashed border-[var(--border-primary)] bg-[var(--bg-secondary)] px-5 py-16 text-center">
            <p className="text-sm text-[var(--text-primary)]">
              {activePage} workspace
            </p>

            <p className="mx-auto mt-2 max-w-md text-xs leading-6 text-[var(--text-muted)]">
              This workspace has not been implemented yet. It will be
              connected to its corresponding backend functionality in a
              later development milestone.
            </p>

            <button
              type="button"
              onClick={() => setActivePage('Overview')}
              className="mt-5 rounded border border-[var(--border-primary)] px-4 py-2 text-xs text-[var(--accent-primary)] hover:bg-white/[0.04]"
            >
              Return to overview
            </button>
          </section>
        ) : (
          /* OVERVIEW DASHBOARD */

          <>
            {error && (
              <div
                role="alert"
                className="mt-7 rounded border border-rose-400/20 bg-rose-400/[0.06] p-4 text-xs text-rose-300"
              >
                <p>Could not load dashboard data: {error}</p>

                <button
                  type="button"
                  onClick={() => void loadDashboard()}
                  className="mt-3 underline underline-offset-4"
                >
                  Retry
                </button>
              </div>
            )}

            {/* KPI CARDS */}

            <section className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard
                label="REGISTERED SOURCES"
                value={data ? String(data.sources.length) : '—'}
                detail="Sources retrieved · maximum 100"
                loading={loading}
                accent
              />

              <MetricCard
                label="OBSERVATIONS"
                value={data ? String(data.observations.length) : '—'}
                detail="Observations retrieved · maximum 100"
                loading={loading}
              />

              <MetricCard
                label="RELATIONSHIPS"
                value={data ? String(data.relationships.length) : '—'}
                detail="Relationships retrieved · maximum 100"
                loading={loading}
              />

              <MetricCard
                label="AUTHORIZED SOURCES"
                value={data ? String(authorizedSources) : '—'}
                detail="Among retrieved source records"
                loading={loading}
              />
            </section>

            {/* ACTIVITY AND RELATIONSHIPS */}

            <section className="mt-5 grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.55fr)_minmax(320px,0.9fr)]">
              <div className="panel min-w-0">
  <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/[0.07] pb-4">
    <div>
      <h3 className="panel-title">
        Intelligence activity
      </h3>

      <p className="panel-description">
        ENTITY CONSTELLATION · STORED RELATIONSHIPS
      </p>
    </div>

    <div className="flex gap-5 text-right">
      <div>
        <p className="text-[9px] text-[var(--text-muted)]">
          ENTITIES
        </p>
        <p className="mt-1 text-lg font-semibold text-[var(--text-primary)]">
          {data?.entities.length ?? 0}
        </p>
      </div>

      <div>
        <p className="text-[9px] text-[var(--text-muted)]">
          CONNECTIONS
        </p>
        <p className="mt-1 text-lg font-semibold text-[var(--accent-primary)]">
          {overviewConstellationEdges.length}
        </p>
      </div>
    </div>
  </div>

  <div className="mt-4 min-h-[390px]">
    {loading ? (
      <div className="flex h-[390px] items-center justify-center text-xs text-[var(--text-muted)]">
        Loading intelligence constellation...
      </div>
    ) : error ? (
      <div
        role="alert"
        className="flex h-[390px] items-center justify-center text-xs text-rose-300"
      >
        Unable to load constellation data: {error}
      </div>
    ) : overviewConstellationPoints.length === 0 ? (
      <div className="flex h-[390px] items-center justify-center text-xs text-[var(--text-muted)]">
        No entities available to visualize.
      </div>
    ) : (
      <div className="w-full overflow-hidden">
        <svg
  viewBox="0 0 900 450"
  role="img"
  aria-label="Intelligence constellation of registered entities and stored relationships"
  className="overview-constellation-svg h-auto max-h-[450px] w-full"
>
  <defs>
    <radialGradient id="overview-nebula-main">
      <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.22" />
      <stop offset="55%" stopColor="#6d28d9" stopOpacity="0.09" />
      <stop offset="100%" stopColor="#6d28d9" stopOpacity="0" />
    </radialGradient>

    <radialGradient id="overview-nebula-cyan">
      <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.12" />
      <stop offset="100%" stopColor="#22d3ee" stopOpacity="0" />
    </radialGradient>

    <linearGradient id="overview-link-gradient">
      <stop offset="0%" stopColor="#a78bfa" stopOpacity="0.12" />
      <stop offset="50%" stopColor="#c4b5fd" stopOpacity="0.72" />
      <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.16" />
    </linearGradient>

    <filter id="overview-node-glow" x="-150%" y="-150%" width="400%" height="400%">
      <feGaussianBlur stdDeviation="5" result="blur" />
      <feMerge>
        <feMergeNode in="blur" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>

    <filter id="overview-link-glow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="2.5" />
    </filter>
  </defs>

  {/* Deep-space background */}
  <rect width="900" height="450" fill="#0b0815" />

  <circle
    cx="430"
    cy="215"
    r="280"
    fill="url(#overview-nebula-main)"
  />

  <circle
    cx="690"
    cy="130"
    r="190"
    fill="url(#overview-nebula-cyan)"
  />

  <circle
    cx="180"
    cy="340"
    r="170"
    fill="url(#overview-nebula-main)"
    opacity="0.55"
  />

  {/* Subtle orbital rings */}
  <g
    fill="none"
    stroke="#a78bfa"
    strokeOpacity="0.10"
    strokeWidth="0.8"
  >
    <ellipse cx="450" cy="225" rx="390" ry="175" />
    <ellipse
      cx="450"
      cy="225"
      rx="290"
      ry="125"
      transform="rotate(-18 450 225)"
    />
    <ellipse
      cx="450"
      cy="225"
      rx="190"
      ry="80"
      transform="rotate(24 450 225)"
    />
  </g>

  {/* Background starfield */}
  {Array.from({ length: 90 }, (_, index) => {
    const x = (index * 137.5 + 31) % 900
    const y = (index * 83.7 + 19) % 450
    const radius = index % 9 === 0 ? 1.5 : index % 3 === 0 ? 0.9 : 0.55

    return (
      <circle
        key={`star-${index}`}
        cx={x}
        cy={y}
        r={radius}
        fill="#e9ddff"
        opacity={index % 4 === 0 ? 0.65 : 0.3}
      />
    )
  })}

  {/* Fine constellation guide points */}
  {overviewConstellationPoints.map((point, index) => (
    <circle
      key={`guide-${point.entity.entity_id}`}
      cx={point.x}
      cy={point.y}
      r="2"
      fill="#c4b5fd"
      opacity={index % 2 === 0 ? 0.45 : 0.2}
    />
  ))}

  {/* Stored relationship connections */}
  {overviewConstellationEdges.map((relationship, index) => {
    const source = overviewConstellationPointMap.get(
      relationship.source_entity_id,
    )
    const target = overviewConstellationPointMap.get(
      relationship.target_entity_id,
    )

    if (!source || !target) return null

    const dx = target.x - source.x
    const dy = target.y - source.y

    const curve = index % 2 === 0 ? 24 : -24
    const controlX = (source.x + target.x) / 2 - (dy / 2) * (curve / 100)
    const controlY = (source.y + target.y) / 2 + (dx / 2) * (curve / 100)

    const path = `M ${source.x} ${source.y} Q ${controlX} ${controlY} ${target.x} ${target.y}`

    return (
      <g key={relationship.relationship_id}>
        <path
          d={path}
          fill="none"
          stroke="#a78bfa"
          strokeWidth="5"
          strokeOpacity="0.12"
          filter="url(#overview-link-glow)"
        />

        <path
          d={path}
          fill="none"
          stroke="url(#overview-link-gradient)"
          strokeWidth="1.35"
          strokeOpacity="0.8"
          strokeDasharray="4 5"
        >
          <title>
            {formatEntityType(relationship.relationship_type)}
            {relationship.description
              ? ` — ${relationship.description}`
              : ''}
          </title>
        </path>

        <circle
          cx={controlX}
          cy={controlY}
          r="1.8"
          fill="#c4b5fd"
          opacity="0.7"
        />
      </g>
    )
  })}

  {/* Entity constellation nodes */}
  {overviewConstellationPoints.map(({ entity, x, y }) => {
    const connected = overviewConstellationEdges.some(
      (relationship) =>
        relationship.source_entity_id === entity.entity_id ||
        relationship.target_entity_id === entity.entity_id,
    )

    const type = entity.entity_type.toLowerCase()

    const nodeColor =
      type.includes('handle') ? '#c084fc'
      : type.includes('pgp') ? '#67e8f9'
      : type.includes('wallet') ? '#fbbf24'
      : type.includes('domain') ? '#5eead4'
      : type.includes('ip') ? '#fb7185'
      : type.includes('email') ? '#60a5fa'
      : type.includes('onion') ? '#a3e635'
      : '#a78bfa'

    const label = displayEntity(entity)
    const shortLabel =
      label.length > 17 ? `${label.slice(0, 15)}…` : label

    return (
      <g
        key={entity.entity_id}
        className="overview-constellation-node cursor-pointer outline-none"
        role="button"
        tabIndex={0}
        aria-label={`Investigate ${label}`}
        onClick={() => openEntity(entity)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            openEntity(entity)
          }
        }}
      >
        {/* Outer atmospheric glow */}
        <circle
          cx={x}
          cy={y}
          r={connected ? 29 : 21}
          fill={nodeColor}
          opacity="0.07"
          className="overview-node-halo"
        />

        {/* Orbital ring */}
        <circle
          cx={x}
          cy={y}
          r={connected ? 19 : 14}
          fill="none"
          stroke={nodeColor}
          strokeWidth="0.8"
          strokeOpacity={connected ? 0.5 : 0.25}
          strokeDasharray={connected ? '2 4' : '1 5'}
        />

        {/* Node glow */}
        <circle
          cx={x}
          cy={y}
          r={connected ? 11 : 8}
          fill={nodeColor}
          opacity="0.22"
          filter="url(#overview-node-glow)"
        />

        {/* Main node */}
        <circle
          cx={x}
          cy={y}
          r={connected ? 7 : 5}
          fill={nodeColor}
          stroke="#f5eaff"
          strokeWidth="1"
          strokeOpacity="0.75"
        />

        {/* Center highlight */}
        <circle
          cx={x - 1.5}
          cy={y - 1.5}
          r="1.8"
          fill="#ffffff"
          opacity="0.8"
        />

        {/* Entity label */}
        <text
          x={x}
          y={y + 34}
          textAnchor="middle"
          fill="#e9ddff"
          fontSize="10"
          fontWeight="600"
          paintOrder="stroke"
          stroke="#0b0815"
          strokeWidth="3"
          strokeLinejoin="round"
        >
          {shortLabel}
        </text>

        {/* Entity type */}
        <text
          x={x}
          y={y + 46}
          textAnchor="middle"
          fill={nodeColor}
          fontSize="7"
          letterSpacing="1"
          opacity="0.85"
        >
          {formatEntityType(entity.entity_type).toUpperCase()}
        </text>

        <title>
          {label}
          {' · '}
          {formatEntityType(entity.entity_type)}
          {connected
            ? ' · Stored relationship exists'
            : ' · Isolated entity'}
          {' · Click to investigate'}
        </title>
      </g>
    )
  })}
</svg>
      </div>
    )}
  </div>

  <div className="mt-3 flex flex-wrap items-center gap-5 border-t border-white/[0.07] pt-3">
    <div className="flex items-center gap-2">
      <span className="h-2.5 w-2.5 rounded-full bg-violet-400" />
      <span className="text-[10px] text-[var(--text-muted)]">
        Connected entity
      </span>
    </div>

    <div className="flex items-center gap-2">
      <span className="h-2.5 w-2.5 rounded-full bg-slate-500" />
      <span className="text-[10px] text-[var(--text-muted)]">
        Isolated entity
      </span>
    </div>

    <span className="text-[10px] text-[var(--text-muted)]">
      Select a node to investigate
    </span>
  </div>

  <p className="mt-3 text-[10px] leading-5 text-[var(--text-muted)]">
    Showing up to 100 retrieved entities and 100 stored
    relationships. Lines represent recorded relationships only;
    they do not establish identity or attribution.
  </p>
</div>
              <div className="panel">
                <div className="flex items-start justify-between border-b border-white/[0.07] pb-4">
                  <div>
                    <h3 className="panel-title">
                      Relationship overview
                    </h3>

                    <p className="panel-description">
                      STORED ENTITY CONNECTIONS
                    </p>
                  </div>

                  <span className="text-lg text-[var(--accent-primary)]">
                    ⌘
                  </span>
                </div>

                <div className="pt-5">
                  {loading ? (
                    <p className="text-xs text-[var(--text-muted)]">
                      Loading relationships…
                    </p>
                  ) : !data?.relationships.length ? (
                    <EmptyState message="No relationships were returned by the API." />
                  ) : (
                    <div className="space-y-3">
                      {data.relationships.slice(0, 5).map((relationship) => (
                        <div
                          key={relationship.relationship_id}
                          className="relationship-item"
                        >
                          <div className="flex items-center gap-2">
                            <span className="relationship-dot" />

                            <span className="text-[11px] font-medium text-[var(--text-primary)]">
                              {formatEntityType(
                                relationship.relationship_type,
                              )}
                            </span>
                          </div>

                          <div className="mt-3 grid grid-cols-[1fr_auto_1fr] items-center gap-2">
                            <span className="truncate font-mono text-[10px] text-[var(--text-secondary)]">
                              {shortId(relationship.source_entity_id)}
                            </span>

                            <span className="text-xs text-[var(--accent-primary)]">
                              ↔
                            </span>

                            <span className="truncate text-right font-mono text-[10px] text-[var(--text-secondary)]">
                              {shortId(relationship.target_entity_id)}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  <p className="mt-4 text-[10px] leading-5 text-[var(--text-muted)]">
                    Stored relationships are not proof of attribution.
                    Open the Intelligence workspace to explore their
                    evidence and analytical assessments.
                  </p>
                </div>
              </div>
            </section>

            {/* RECENT INTELLIGENCE */}

            <section className="panel mt-5">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.07] pb-4">
                <div>
                  <h3 className="panel-title">
                    Recent intelligence
                  </h3>

                  <p className="panel-description">
                    LATEST RETRIEVED OBSERVATIONS
                  </p>
                </div>

                <span className="text-[10px] text-[var(--text-muted)]">
                  {recentObservations.length} records shown
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="data-table min-w-[720px]">
                  <thead>
                    <tr>
                      <th>Observation</th>
                      <th>Source</th>
                      <th>Status</th>
                      <th>Processing version</th>
                      <th>Collected</th>
                    </tr>
                  </thead>

                  <tbody>
                    {recentObservations.map((observation) => (
                      <tr key={observation.observation_id}>
                        <td>
                          <p className="font-mono text-[11px] text-[var(--text-primary)]">
                            {shortId(observation.observation_id)}
                          </p>

                          <p className="mt-1 font-mono text-[9px] text-[var(--text-muted)]">
                            SHA-256 {shortId(observation.content_sha256)}
                          </p>
                        </td>

                        <td>
                          {sourceNames.get(observation.source_id) ??
                            shortId(observation.source_id)}
                        </td>

                        <td>
                          <span className="rounded border border-white/10 px-2 py-1 text-[10px] text-[var(--text-secondary)]">
                            {observation.status}
                          </span>
                        </td>

                        <td>{observation.processing_version}</td>

                        <td>{formatDate(observation.collected_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {!loading && recentObservations.length === 0 && (
                <EmptyState message="No observations were returned. Register an authorized source and ingest observations to populate this view." />
              )}
            </section>

            <footer className="dashboard-footer">
              <span>ECLIPSE NEXUS / DEFENSIVE RESEARCH</span>

              <span>
                {loading
                  ? 'SYNCING'
                  : error
                    ? 'API ERROR'
                    : `DATA RETRIEVED · ${totalRetrieved} RECORDS`}
              </span>
            </footer>
          </>
        )}
      </main>
    </div>
  )
}

/* REUSABLE COMPONENTS */

function MetricCard({
  label,
  value,
  detail,
  loading,
  accent = false,
}: {
  label: string
  value: string
  detail: string
  loading: boolean
  accent?: boolean
}) {
  return (
    <article className="metric-card">
      <p className="metric-label">{label}</p>

      <p className={`metric-value ${accent ? 'metric-accent' : ''}`}>
        {loading ? '—' : value}
      </p>

      <p className="metric-caption">
        {loading ? 'Retrieving API data…' : detail}
      </p>
    </article>
  )
}

function AssessmentValue({
  label,
  value,
}: {
  label: string
  value: string
}) {
  return (
    <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-3">
      <p className="text-[9px] font-semibold tracking-wider text-[var(--text-muted)]">
        {label}
      </p>

      <p className="mt-2 break-words text-sm font-semibold text-[var(--text-primary)]">
        {value}
      </p>
    </div>
  )
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="py-8 text-center">
      <p className="text-xs leading-6 text-[var(--text-muted)]">
        {message}
      </p>
    </div>
  )
}