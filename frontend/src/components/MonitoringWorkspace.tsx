import { useEffect, useState } from 'react'

const API = '/api'

type ReportingPeriod = 7 | 30 | 90 | 365

type MonitoringSummary = {
  reporting_period_days: number
  generated_at: string

  total_runs: number
  successful_runs: number
  runs_with_rejections: number
  failed_runs: number
  active_runs: number

  total_lines: number
  parsed_records: number
  imported_records: number
  rejected_records: number
  duplicate_records: number

  observations_examined: number
  entities_created: number
  existing_entities_matched: number
  associations_created: number

  average_processing_time_seconds: number | null
}

type ProcessingStatus =
  | 'started'
  | 'importing'
  | 'extracting'
  | 'completed'
  | 'completed_with_rejections'
  | 'failed'

type ProcessingRun = {
  run_id: string
  source_name: string
  source_type: string
  status: ProcessingStatus
  started_at: string
  completed_at: string | null
  total_lines: number
  imported_count: number
  rejected_count: number
  entities_created: number
  error_message: string | null
}

type ProcessingRunResponse = {
  results: ProcessingRun[]
  result_count: number
  limit: number
  offset: number
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat('en-US').format(value)
}

function formatDate(value: string | null): string {
  if (!value) return 'In progress'

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) return 'Invalid date'

  return date.toLocaleString()
}

function formatStatus(status: ProcessingStatus): string {
  return status.replaceAll('_', ' ')
}

function statusStyle(status: ProcessingStatus): string {
  switch (status) {
    case 'completed':
      return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'

    case 'completed_with_rejections':
      return 'border-amber-500/30 bg-amber-500/10 text-amber-300'

    case 'failed':
      return 'border-rose-500/30 bg-rose-500/10 text-rose-300'

    default:
      return 'border-sky-500/30 bg-sky-500/10 text-sky-300'
  }
}

function MetricCard({
  label,
  value,
  description,
}: {
  label: string
  value: string | number
  description?: string
}) {
  return (
    <article className="rounded-lg border border-[rgba(205,165,255,0.18)] bg-[rgba(25,14,38,0.46)] p-4 backdrop-blur-[18px] shadow-[inset_0_1px_0_rgba(255,255,255,0.045),0_8px_28px_rgba(0,0,0,0.12)] transition-all duration-200 hover:border-[rgba(205,165,255,0.32)] hover:bg-[rgba(34,19,50,0.58)]">
      <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
        {label}
      </p>

      <p className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">
        {value}
      </p>

      {description && (
        <p className="mt-1 text-[10px] text-[var(--text-muted)]">
          {description}
        </p>
      )}
    </article>
  )
}

function SectionHeading({
  title,
  description,
}: {
  title: string
  description: string
}) {
  return (
    <div className="mb-4">
      <h3 className="text-sm font-semibold text-[var(--text-primary)]">
        {title}
      </h3>

      <p className="mt-1 text-[10px] text-[var(--text-muted)]">
        {description}
      </p>
    </div>
  )
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-dashed border-[var(--border-primary)] px-5 py-10 text-center">
      <p className="text-xs text-[var(--text-secondary)]">
        {message}
      </p>
    </div>
  )
}

function ProcessingActivity({
  runs,
}: {
  runs: ProcessingRun[]
}) {
  if (runs.length === 0) {
    return <EmptyState message="No processing activity recorded." />
  }

  return (
    <div className="space-y-3">
      {runs.map((run) => (
        <article
          key={run.run_id}
          className="rounded-lg border border-[rgba(205,165,255,0.18)] bg-[rgba(25,14,38,0.46)] p-4 backdrop-blur-[18px] shadow-[inset_0_1px_0_rgba(255,255,255,0.045),0_8px_28px_rgba(0,0,0,0.12)] transition-all duration-200 hover:border-[rgba(205,165,255,0.32)] hover:bg-[rgba(34,19,50,0.58)]"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <h4 className="break-words text-xs font-semibold text-[var(--text-primary)]">
                {run.source_name}
              </h4>

              <p className="mt-1 text-[10px] text-[var(--text-muted)]">
                {run.source_type.replaceAll('_', ' ')} source
              </p>
            </div>

            <span
              className={`rounded border px-2 py-1 text-[9px] uppercase tracking-wider ${statusStyle(run.status)}`}
            >
              {formatStatus(run.status)}
            </span>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3 border-t border-white/[0.06] pt-3 sm:grid-cols-4">
            <div>
              <p className="text-[9px] text-[var(--text-muted)]">
                TOTAL LINES
              </p>
              <p className="mt-1 text-xs text-[var(--text-primary)]">
                {formatNumber(run.total_lines)}
              </p>
            </div>

            <div>
              <p className="text-[9px] text-[var(--text-muted)]">
                IMPORTED
              </p>
              <p className="mt-1 text-xs text-[var(--text-primary)]">
                {formatNumber(run.imported_count)}
              </p>
            </div>

            <div>
              <p className="text-[9px] text-[var(--text-muted)]">
                REJECTED
              </p>
              <p className="mt-1 text-xs text-[var(--text-primary)]">
                {formatNumber(run.rejected_count)}
              </p>
            </div>

            <div>
              <p className="text-[9px] text-[var(--text-muted)]">
                ENTITIES CREATED
              </p>
              <p className="mt-1 text-xs text-[var(--text-primary)]">
                {formatNumber(run.entities_created)}
              </p>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap justify-between gap-2 border-t border-white/[0.06] pt-3">
            <p className="text-[10px] text-[var(--text-muted)]">
              Started: {formatDate(run.started_at)}
            </p>

            <p className="text-[10px] text-[var(--text-muted)]">
              Completed: {formatDate(run.completed_at)}
            </p>
          </div>

          {run.error_message && (
            <div className="mt-3 rounded border border-rose-500/20 bg-rose-500/[0.05] p-3">
              <p className="text-[9px] uppercase tracking-wider text-rose-300">
                Processing error
              </p>

              <p className="mt-2 break-words text-xs leading-5 text-[var(--text-secondary)]">
                {run.error_message}
              </p>
            </div>
          )}
        </article>
      ))}
    </div>
  )
}

export default function MonitoringWorkspace() {
  const [days, setDays] = useState<ReportingPeriod>(30)
  const [summary, setSummary] = useState<MonitoringSummary | null>(null)
  const [runs, setRuns] = useState<ProcessingRun[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    let cancelled = false

    async function loadMonitoringData() {
      try {
        setError(null)

        const [summaryResponse, runsResponse] = await Promise.all([
          fetch(`${API}/monitoring/summary?days=${days}`),
          fetch(`${API}/processing-runs?limit=8&offset=0`),
        ])

        if (!summaryResponse.ok) {
          throw new Error(
            `Monitoring summary request failed (${summaryResponse.status}).`,
          )
        }

        if (!runsResponse.ok) {
          throw new Error(
            `Processing activity request failed (${runsResponse.status}).`,
          )
        }

        const summaryData: MonitoringSummary =
          await summaryResponse.json()

        const runsData: ProcessingRunResponse =
          await runsResponse.json()

        if (cancelled) return

        setSummary(summaryData)
        setRuns(runsData.results)
      } catch (err) {
        if (cancelled) return

        setError(
          err instanceof Error
            ? err.message
            : 'Unable to load monitoring data.',
        )
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void loadMonitoringData()

    return () => {
      cancelled = true
    }
  }, [days, refreshKey])

  if (loading && !summary) {
    return (
      <section className="mt-7 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-secondary)] p-10 text-center">
        <p className="text-xs text-[var(--text-secondary)]">
          Loading operational monitoring data...
        </p>
      </section>
    )
  }

  return (
    <section className="mt-7 space-y-8">
      {/* CONTROLS */}

      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
            Operational intelligence
          </p>

          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            Processing activity and ingestion performance.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label
            htmlFor="monitoring-period"
            className="text-[10px] text-[var(--text-muted)]"
          >
            PERIOD
          </label>

          <select
            id="monitoring-period"
            value={days}
            onChange={(event) => {
                setLoading(true)
              setDays(Number(event.target.value) as ReportingPeriod)
            }}
            className="rounded border border-[var(--border-primary)] bg-[var(--bg-card)] px-3 py-2 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--accent-primary)]"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
            <option value={365}>Last 365 days</option>
          </select>

          <button
            type="button"
            onClick={() =>{
                setLoading(true)
                setRefreshKey((value) => value + 1)}}
            disabled={loading}
            className="rounded border border-[var(--border-primary)] px-3 py-2 text-xs text-[var(--accent-primary)] transition hover:bg-white/[0.04] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? 'Refreshing...' : '↻ Refresh'}
          </button>
        </div>
      </div>

      {/* ERROR */}

      {error && (
        <div
          role="alert"
          className="rounded border border-rose-500/30 bg-rose-500/[0.06] p-4"
        >
          <p className="text-xs text-rose-300">
            {error}
          </p>

          <button
            type="button"
            onClick={() =>{
                setLoading(true)
                 setRefreshKey((value) => value + 1)}}
            className="mt-3 text-[10px] text-[var(--accent-primary)] hover:underline"
          >
            Retry request
          </button>
        </div>
      )}

      {summary && (
        <>
          {/* PROCESSING OVERVIEW */}

          <div>
            <SectionHeading
              title="Processing overview"
              description={`Processing runs recorded during the last ${days} days.`}
            />

            <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
              <MetricCard
                label="Total runs"
                value={formatNumber(summary.total_runs)}
              />

              <MetricCard
                label="Successful"
                value={formatNumber(summary.successful_runs)}
                description="Completed without rejections"
              />

              <MetricCard
                label="With rejections"
                value={formatNumber(summary.runs_with_rejections)}
              />

              <MetricCard
                label="Failed"
                value={formatNumber(summary.failed_runs)}
              />

              <MetricCard
                label="Active"
                value={formatNumber(summary.active_runs)}
                description="Currently processing"
              />
            </div>
          </div>

          {/* INGESTION METRICS */}

          <div>
            <SectionHeading
              title="Ingestion metrics"
              description="Record-level ingestion and validation totals."
            />

            <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
              <MetricCard
                label="Total lines"
                value={formatNumber(summary.total_lines)}
              />

              <MetricCard
                label="Parsed"
                value={formatNumber(summary.parsed_records)}
              />

              <MetricCard
                label="Imported"
                value={formatNumber(summary.imported_records)}
              />

              <MetricCard
                label="Rejected"
                value={formatNumber(summary.rejected_records)}
              />

              <MetricCard
                label="Duplicates"
                value={formatNumber(summary.duplicate_records)}
              />
            </div>
          </div>

          {/* ENTITY EXTRACTION */}

          <div>
            <SectionHeading
              title="Entity extraction"
              description="Entities and associations produced by ingestion processing."
            />

            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <MetricCard
                label="Observations examined"
                value={formatNumber(summary.observations_examined)}
              />

              <MetricCard
                label="Entities created"
                value={formatNumber(summary.entities_created)}
              />

              <MetricCard
                label="Existing entities matched"
                value={formatNumber(summary.existing_entities_matched)}
              />

              <MetricCard
                label="Associations created"
                value={formatNumber(summary.associations_created)}
              />
            </div>
          </div>

          {/* PERFORMANCE */}

          <div>
            <SectionHeading
              title="Processing performance"
              description="Average duration of completed and terminated processing runs."
            />

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <MetricCard
                label="Average processing time"
                value={
                  summary.average_processing_time_seconds === null
                    ? 'N/A'
                    : `${summary.average_processing_time_seconds.toFixed(2)} s`
                }
                description="Runs with a valid completion timestamp"
              />

              <MetricCard
                label="Reporting period"
                value={`${summary.reporting_period_days} days`}
                description={`Generated ${formatDate(summary.generated_at)}`}
              />
            </div>
          </div>
        </>
      )}

      {/* RECENT ACTIVITY */}

      <div>
        <SectionHeading
          title="Recent processing activity"
          description="Latest persisted ingestion runs, including successful and unsuccessful runs."
        />

        <ProcessingActivity runs={runs} />
      </div>

      <p className="border-t border-white/[0.06] pt-4 text-[10px] leading-5 text-[var(--text-muted)]">
        Monitoring metrics are aggregated from persisted processing runs.
        They describe recorded ingestion activity and should not be interpreted
        as system uptime or production reliability measurements.
      </p>
    </section>
  )
}