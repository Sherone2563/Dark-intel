import { useEffect, useState } from 'react'

const API = '/api'
const PAGE_SIZE = 10

type ProcessingStatus =
  | 'started'
  | 'importing'
  | 'extracting'
  | 'completed'
  | 'completed_with_rejections'
  | 'failed'

type ProcessingRun = {
  run_id: string
  source_id: string
  source_name: string
  source_type: string
  source_reliability: string
  source_authorized_for_use: boolean
  status: ProcessingStatus
  started_at: string
  completed_at: string | null
  total_lines: number
  parsed_count: number
  imported_count: number
  skipped_duplicate_count: number
  rejected_count: number
  observations_examined: number
  entities_created: number
  existing_entities_matched: number
  associations_created: number
  handles_processed: number
  pgp_keys_processed: number
  processing_version: string
  error_message: string | null
}

type ProcessingRunResponse = {
  results: ProcessingRun[]
  result_count: number
  limit: number
  offset: number
}

type AlertCategory = 'error' | 'warning' | 'active'

type AlertFilter = 'all' | AlertCategory

function formatDate(value: string | null): string {
  if (!value) return 'Not recorded'

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return 'Invalid date'
  }

  return date.toLocaleString()
}

function shortId(value: string): string {
  return value.length > 14
    ? `${value.slice(0, 10)}…`
    : value
}

function formatLabel(value: string): string {
  return value.replaceAll('_', ' ')
}

function getAlertCategory(
  status: ProcessingStatus,
): AlertCategory | null {
  switch (status) {
    case 'failed':
      return 'error'

    case 'completed_with_rejections':
      return 'warning'

    case 'started':
    case 'importing':
    case 'extracting':
      return 'active'

    default:
      return null
  }
}

function categoryLabel(category: AlertCategory): string {
  switch (category) {
    case 'error':
      return 'Failed run'

    case 'warning':
      return 'Rejected records'

    case 'active':
      return 'In progress'
  }
}

function categoryStyle(category: AlertCategory): string {
  switch (category) {
    case 'error':
      return 'border-rose-500/30 bg-rose-500/10 text-rose-300'

    case 'warning':
      return 'border-amber-500/30 bg-amber-500/10 text-amber-300'

    case 'active':
      return 'border-sky-500/30 bg-sky-500/10 text-sky-300'
  }
}

function Metric({
  label,
  value,
}: {
  label: string
  value: number
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
    <div className="rounded-lg border border-dashed border-[var(--border-primary)] px-5 py-12 text-center">
      <p className="text-sm text-[var(--text-secondary)]">
        {message}
      </p>

      <p className="mt-2 text-[10px] text-[var(--text-muted)]">
        Alerts are derived from persisted ingestion processing runs.
      </p>
    </div>
  )
}

function AlertCard({ run }: { run: ProcessingRun }) {
  const category = getAlertCategory(run.status)

  if (!category) return null

  return (
    <article className="rounded-lg border border-[var(--border-primary)] bg-[var(--bg-secondary)] p-4">

      <div className="flex flex-wrap items-start justify-between gap-3">

        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">

            <span
              className={`rounded border px-2 py-1 text-[9px] uppercase tracking-wider ${categoryStyle(category)}`}
            >
              {categoryLabel(category)}
            </span>

            <span className="text-[9px] uppercase tracking-wider text-[var(--text-muted)]">
              {formatLabel(run.status)}
            </span>

          </div>

          <h3 className="mt-3 break-words text-sm font-semibold text-[var(--text-primary)]">
            {run.source_name}
          </h3>

          <p className="mt-1 text-[10px] text-[var(--text-muted)]">
            {formatLabel(run.source_type)} source
          </p>
        </div>

        <div className="text-right">
          <p className="text-[9px] text-[var(--text-muted)]">
            STARTED
          </p>

          <p className="mt-1 text-[10px] text-[var(--text-secondary)]">
            {formatDate(run.started_at)}
          </p>
        </div>

      </div>

      {run.error_message && (
        <div className="mt-4 rounded border border-rose-500/20 bg-rose-500/[0.05] p-3">
          <p className="text-[9px] uppercase tracking-wider text-rose-300">
            Processing error
          </p>

          <p className="mt-2 break-words text-xs leading-5 text-[var(--text-secondary)]">
            {run.error_message}
          </p>
        </div>
      )}

      {category === 'warning' && (
        <div className="mt-4 rounded border border-amber-500/20 bg-amber-500/[0.05] p-3">
          <p className="text-[9px] uppercase tracking-wider text-amber-300">
            Rejection summary
          </p>

          <p className="mt-2 text-xs text-[var(--text-secondary)]">
            {run.rejected_count} record(s) rejected during processing.
          </p>
        </div>
      )}

      <div className="mt-4 grid grid-cols-2 gap-3 border-t border-white/[0.06] pt-4 sm:grid-cols-4">

        <div>
          <p className="text-[9px] text-[var(--text-muted)]">
            TOTAL LINES
          </p>
          <p className="mt-1 text-sm text-[var(--text-primary)]">
            {run.total_lines}
          </p>
        </div>

        <div>
          <p className="text-[9px] text-[var(--text-muted)]">
            IMPORTED
          </p>
          <p className="mt-1 text-sm text-[var(--text-primary)]">
            {run.imported_count}
          </p>
        </div>

        <div>
          <p className="text-[9px] text-[var(--text-muted)]">
            REJECTED
          </p>
          <p className="mt-1 text-sm text-[var(--text-primary)]">
            {run.rejected_count}
          </p>
        </div>

        <div>
          <p className="text-[9px] text-[var(--text-muted)]">
            ENTITIES CREATED
          </p>
          <p className="mt-1 text-sm text-[var(--text-primary)]">
            {run.entities_created}
          </p>
        </div>

      </div>

      <div className="mt-4 flex flex-wrap justify-between gap-3 border-t border-white/[0.06] pt-3">

        <div>
          <p className="text-[9px] text-[var(--text-muted)]">
            PROCESSING RUN ID
          </p>

          <p className="mt-1 font-mono text-[9px] text-[var(--text-secondary)]">
            {shortId(run.run_id)}
          </p>
        </div>

        <div className="text-right">
          <p className="text-[9px] text-[var(--text-muted)]">
            COMPLETED AT
          </p>

          <p className="mt-1 text-[10px] text-[var(--text-secondary)]">
            {formatDate(run.completed_at)}
          </p>
        </div>

      </div>

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-[9px] text-[var(--text-muted)]">
        <span>
          Authorization: {run.source_authorized_for_use ? 'Authorized' : 'Not authorized'}
        </span>

        <span>
          Reliability: {formatLabel(run.source_reliability)}
        </span>

        <span>
          Version: {run.processing_version}
        </span>
      </div>

    </article>
  )
}

export default function AlertsWorkspace() {
  const [runs, setRuns] = useState<ProcessingRun[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState<AlertFilter>('all')
  const [offset, setOffset] = useState(0)

  async function loadRuns(isRefresh = false) {
    if (isRefresh) {
      setRefreshing(true)
    }

    setError('')

    try {
      const response = await fetch(
        `${API}/processing-runs?limit=100&offset=0`,
      )

      if (!response.ok) {
        throw new Error(
          `Unable to retrieve processing runs (${response.status}).`,
        )
      }

      const data =
        (await response.json()) as ProcessingRunResponse

      setRuns(data.results)
      setOffset(0)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to retrieve processing runs.',
      )
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    const controller = new AbortController()

    async function fetchInitialRuns() {
      try {
        const response = await fetch(
          `${API}/processing-runs?limit=100&offset=0`,
          { signal: controller.signal },
        )

        if (!response.ok) {
          throw new Error(
            `Unable to retrieve processing runs (${response.status}).`,
          )
        }

        const data =
          (await response.json()) as ProcessingRunResponse

        setRuns(data.results)
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          return
        }

        setError(
          err instanceof Error
            ? err.message
            : 'Unable to retrieve processing runs.',
        )
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    }

    void fetchInitialRuns()

    return () => controller.abort()
  }, [])

  const alertRuns = runs.filter(
    (run) => getAlertCategory(run.status) !== null,
  )

  const errorCount = alertRuns.filter(
    (run) => getAlertCategory(run.status) === 'error',
  ).length

  const warningCount = alertRuns.filter(
    (run) => getAlertCategory(run.status) === 'warning',
  ).length

  const activeCount = alertRuns.filter(
    (run) => getAlertCategory(run.status) === 'active',
  ).length

  const filteredRuns = alertRuns.filter((run) => {
    if (filter === 'all') return true

    return getAlertCategory(run.status) === filter
  })

  const visibleRuns = filteredRuns.slice(
    offset,
    offset + PAGE_SIZE,
  )

  const filters: { label: string; value: AlertFilter }[] = [
    { label: 'All alerts', value: 'all' },
    { label: 'Errors', value: 'error' },
    { label: 'Warnings', value: 'warning' },
    { label: 'In progress', value: 'active' },
  ]

  return (
    <section className="mt-7 space-y-5">

      {/* HEADER */}

      <div className="flex flex-wrap items-start justify-between gap-4">

        <div>
          <p className="text-[10px] tracking-[0.16em] text-[var(--accent-secondary)]">
            OPERATIONAL MONITORING
          </p>

          <h2 className="mt-2 text-xl font-semibold text-[var(--text-primary)]">
            System alerts
          </h2>

          <p className="mt-2 max-w-2xl text-xs leading-6 text-[var(--text-muted)]">
            Monitor ingestion failures, rejected records, and
            processing runs currently in progress.
          </p>
        </div>

        <button
          type="button"
          onClick={() => void loadRuns(true)}
          disabled={loading || refreshing}
          className="rounded border border-[var(--accent-primary)] bg-[var(--accent-primary)]/10 px-4 py-2.5 text-xs text-[var(--accent-primary)] transition hover:bg-[var(--accent-primary)]/20 disabled:opacity-50"
        >
          {refreshing ? 'Refreshing…' : '↻ Refresh'}
        </button>

      </div>

      {/* METRICS */}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">

        <Metric label="Errors" value={errorCount} />

        <Metric label="Warnings" value={warningCount} />

        <Metric label="Active runs" value={activeCount} />

      </div>

      {/* FILTERS */}

      <div className="flex flex-wrap gap-2 border-b border-white/[0.07] pb-3">

        {filters.map((item) => (
          <button
            key={item.value}
            type="button"
            onClick={() => {
              setFilter(item.value)
              setOffset(0)
            }}
            aria-pressed={filter === item.value}
            className={`rounded border px-4 py-2 text-xs transition ${
              filter === item.value
                ? 'border-[var(--accent-primary)] bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]'
                : 'border-[var(--border-subtle)] text-[var(--text-secondary)] hover:bg-white/[0.04]'
            }`}
          >
            {item.label}
          </button>
        ))}

      </div>

      {/* ERROR */}

      {error && (
        <div
          role="alert"
          className="rounded border border-rose-500/30 bg-rose-500/[0.06] p-4 text-xs text-rose-300"
        >
          {error}
        </div>
      )}

      {/* ALERT LIST */}

      {loading ? (
        <div className="py-12 text-center text-xs text-[var(--text-muted)]">
          Loading operational alerts…
        </div>
      ) : error ? (
        <EmptyState message="Alert data could not be retrieved." />
      ) : visibleRuns.length === 0 ? (
        <EmptyState
          message={
            filter === 'all'
              ? 'No operational alerts. All recorded processing runs are healthy.'
              : `No ${filter === 'active' ? 'active' : filter} alerts found.`
          }
        />
      ) : (
        <div className="space-y-3">

          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-[10px] text-[var(--text-muted)]">
              {filteredRuns.length} matching alerts
            </p>

            <p className="text-[10px] text-[var(--text-muted)]">
              Showing {offset + 1}–
              {offset + visibleRuns.length}
            </p>
          </div>

          {visibleRuns.map((run) => (
            <AlertCard key={run.run_id} run={run} />
          ))}

          {/* PAGINATION */}

          {filteredRuns.length > PAGE_SIZE && (
            <div className="flex items-center justify-between border-t border-white/[0.07] pt-4">

              <button
                type="button"
                disabled={offset === 0}
                onClick={() =>
                  setOffset(Math.max(0, offset - PAGE_SIZE))
                }
                className="rounded border border-[var(--border-primary)] px-4 py-2 text-xs text-[var(--text-secondary)] disabled:opacity-30"
              >
                Previous
              </button>

              <span className="text-[10px] text-[var(--text-muted)]">
                Page {Math.floor(offset / PAGE_SIZE) + 1} of{' '}
                {Math.ceil(filteredRuns.length / PAGE_SIZE)}
              </span>

              <button
                type="button"
                disabled={offset + PAGE_SIZE >= filteredRuns.length}
                onClick={() => setOffset(offset + PAGE_SIZE)}
                className="rounded border border-[var(--border-primary)] px-4 py-2 text-xs text-[var(--text-secondary)] disabled:opacity-30"
              >
                Next
              </button>

            </div>
          )}

        </div>
      )}

      {/* SCOPE NOTE */}

      <p className="border-t border-white/[0.06] pt-4 text-[10px] leading-5 text-[var(--text-muted)]">
        These alerts describe ingestion and processing operations.
        They do not represent confirmed threat activity or threat-actor
        attribution. Successful processing runs are excluded from
        the alert list.
      </p>

    </section>
  )
}