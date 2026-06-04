import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import { ConsolePanel } from '../components/ConsolePanel';
import { TerminalConsole, LogEntry } from '../components/TerminalConsole';
import { fetchEvalsHistory, fetchLatestEvalSummary, runEvaluationApi } from '../api/evals';
import { useSSE } from '../hooks/useSSE';
import styles from './EvalsView.module.css';

export const EvalsView: React.FC = () => {
  const queryClient = useQueryClient();

  // Control parameters state
  const [split, setSplit] = useState<string>('held_out');
  const [promptVersion, setPromptVersion] = useState<string>('extraction_v1');
  const [dryRun, setDryRun] = useState<boolean>(false);

  // Filters state
  const [showMismatchesOnly, setShowMismatchesOnly] = useState<boolean>(false);

  // Background execution / SSE state
  const [runState, setRunState] = useState<'idle' | 'running' | 'completed' | 'failed'>('idle');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [taskId, setTaskId] = useState<string>('');

  // Load history and latest runs
  const historyQuery = useQuery({
    queryKey: ['evalsHistory'],
    queryFn: fetchEvalsHistory,
  });

  const latestQuery = useQuery({
    queryKey: ['latestEvalResults'],
    queryFn: fetchLatestEvalSummary,
    retry: false, // Don't retry since 404 is a valid state if no evaluations have run
  });

  useSSE(taskId ? `/api/v1/tasks/${taskId}/logs/stream` : null, runState === 'running' && Boolean(taskId), {
    timeoutMs: 3000,
    onOpen: () => {
      setRunState('running');
    },
    onStarted: () => {
      setRunState('running');
      setLogs((prev) => [
        ...prev,
        {
          event: '[SYS] Evaluation task initiated successfully.',
          level: 'sys',
          timestamp: new Date().toISOString(),
        },
      ]);
    },
    onLog: (payload) => {
      if (payload && typeof payload === 'object') {
        setLogs((prev) => [...prev, payload as LogEntry]);
      }
    },
    onCompleted: (payload) => {
      const summary = payload && typeof payload === 'object' ? payload as {
        overall_metrics?: { f1?: number };
        summary_path?: string;
      } : {};
      setLogs((prev) => [
        ...prev,
        {
          event: `Evaluation finished. Result: F1 Score = ${summary.overall_metrics?.f1 ?? 'N/A'}. Details saved to ${summary.summary_path || 'disk'}.`,
          level: 'success',
          timestamp: new Date().toISOString(),
        },
      ]);
      setRunState('completed');
      queryClient.invalidateQueries({ queryKey: ['evalsHistory'] });
      queryClient.invalidateQueries({ queryKey: ['latestEvalResults'] });
    },
    onFailed: (payload) => {
      const errObj = payload && typeof payload === 'object' ? payload as { error?: string } : {};
      setRunState('failed');
      setLogs((prev) => [
        ...prev,
        {
          event: `Evaluation run failed: ${errObj.error || 'Unknown task failure'}`,
          level: 'error',
          timestamp: new Date().toISOString(),
        },
      ]);
      queryClient.invalidateQueries({ queryKey: ['evalsHistory'] });
      queryClient.invalidateQueries({ queryKey: ['latestEvalResults'] });
    },
    onError: () => {
      setRunState('failed');
      setLogs((prev) => [
        ...prev,
        {
          event: '[STREAM DISCONNECTED] Log stream connection closed or failed.',
          level: 'error',
          timestamp: new Date().toISOString(),
        },
      ]);
    },
  });

  const handleRunEvaluation = async () => {
    setRunState('running');
    setLogs([]);
    setTaskId('');

    try {
      const data = await runEvaluationApi({
        split,
        prompt_version: promptVersion,
        dry_run: dryRun,
      });

      setTaskId(data.task_id);
    } catch (err) {
      setRunState('failed');
      setLogs((prev) => [
        ...prev,
        {
          event: `Failed to initiate evaluation: ${err instanceof Error ? err.message : String(err)}`,
          level: 'error',
          timestamp: new Date().toISOString(),
        },
      ]);
    }
  };

  // Format Helper for cells (lists, enums, objects)
  const formatValue = (val: unknown) => {
    if (val === null || val === undefined) return 'N/A';
    if (Array.isArray(val)) {
      return val.length > 0 ? val.join(', ') : 'None';
    }
    if (typeof val === 'object') {
      const obj = val as Record<string, unknown>;
      if (obj['kind'] === 'not_disclosed') return 'Not Disclosed';
      if (obj['kind'] === 'disclosed') {
        return `${String(obj['currency'] || 'USD')} ${String(obj['min_amount'] ?? 0)} - ${String(obj['max_amount'] ?? 0)} per ${String(obj['period'] || 'year')}`;
      }
      return JSON.stringify(val);
    }
    return String(val);
  };

  // Recharts Chronological Data
  const chartData = historyQuery.data ? [...historyQuery.data].reverse().map((run) => ({
    timestamp: run.run_timestamp,
    accuracy: Number(run.overall_accuracy),
    precision: Number(run.overall_precision),
    recall: Number(run.overall_recall),
    f1: Number(run.overall_f1),
  })) : [];

  // Mismatch logic for table
  const detailedDiffs = latestQuery.data?.detailed_diffs || [];
  const filteredDiffs = showMismatchesOnly
    ? detailedDiffs.filter(
        (diff) =>
          diff.mismatched_fields.length > 0 ||
          diff.actual === null ||
          diff.extraction_error !== null
      )
    : detailedDiffs;

  const latestStats = latestQuery.data;

  // Custom cell formatter with Orange mismatch styling
  const renderFieldCell = (
    field: string,
    expected: unknown,
    actual: unknown,
    matchingStatus: Record<string, boolean>
  ) => {
    const isMatch = matchingStatus[field] === true;
    const tdClass = isMatch ? styles.td : `${styles.td} ${styles.mismatchCell}`;

    return (
      <td className={tdClass} data-testid={isMatch ? undefined : `mismatch-${field}`}>
        <div className={styles.cellDiffBox}>
          <div>
            <span className={styles.expectedLabel}>EXP:</span> {formatValue(expected)}
          </div>
          <div>
            <span className={styles.actualLabel}>ACT:</span> {formatValue(actual)}
          </div>
        </div>
      </td>
    );
  };

  return (
    <div className={styles.dashboardContainer}>
      {/* 1. Regression Warning Banner */}
      {latestStats?.accuracy_regression && (
        <div className={styles.errorBanner} role="alert" data-testid="regression-banner">
          <span>▲ SYSTEM ALARM: Structured Extraction F1 Accuracy Regression Detected (Drop exceeded 3% threshold)</span>
        </div>
      )}

      {/* 2. Top Grid Layout */}
      <div className={styles.evalsGrid}>
        {/* Left Column: Diagnostics and Historical Charts */}
        <div>
          <ConsolePanel title="EVALUATION METRICS COCKPIT" glowColor="cyan">
            {/* Control Panel Parameters */}
            <div className={styles.controlSection}>
              <div className={styles.controlGroup}>
                <div className={styles.inputField}>
                  <label htmlFor="split-select" className={styles.inputLabel}>
                    EVALUATION SPLIT
                  </label>
                  <select
                    id="split-select"
                    value={split}
                    onChange={(e) => setSplit(e.target.value)}
                    className={styles.select}
                  >
                    <option value="held_out">held_out</option>
                    <option value="train">train</option>
                  </select>
                </div>

                <div className={styles.inputField}>
                  <label htmlFor="prompt-input" className={styles.inputLabel}>
                    PROMPT VERSION
                  </label>
                  <input
                    id="prompt-input"
                    type="text"
                    value={promptVersion}
                    onChange={(e) => setPromptVersion(e.target.value)}
                    className={styles.input}
                    placeholder="e.g. extraction_v1"
                  />
                </div>

                <div className={styles.inputField} style={{ flexDirection: 'row', alignItems: 'center', gap: '8px', alignSelf: 'center', paddingBottom: '4px' }}>
                  <input
                    id="dry-run-checkbox"
                    type="checkbox"
                    checked={dryRun}
                    onChange={(e) => setDryRun(e.target.checked)}
                    className={styles.checkbox}
                  />
                  <label htmlFor="dry-run-checkbox" className={styles.inputLabel} style={{ cursor: 'pointer' }}>
                    DRY RUN
                  </label>
                </div>

                <button
                  onClick={handleRunEvaluation}
                  disabled={runState === 'running'}
                  className={styles.btnRun}
                  data-testid="run-eval-btn"
                >
                  {runState === 'running' ? 'RUNNING...' : 'RUN EVALUATION'}
                </button>

                {runState === 'running' && (
                  <div className={styles.statusContainer} data-testid="eval-loading-spinner">
                    <div className={styles.doubleRingSpinner}>
                      <div />
                      <div />
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Latest Run Quick Metrics Overview */}
            {latestStats && (
              <div className={styles.summaryOverview} style={{ marginTop: '20px' }}>
                <div className={`${styles.metricBlock} ${latestStats.accuracy_regression ? styles.regressionTriggered : ''}`}>
                  <span className={`${styles.metricValue} ${latestStats.accuracy_regression ? styles.regressionValue : styles.metricValue}`} style={{ color: latestStats.accuracy_regression ? '' : 'var(--glow-green)' }}>
                    {(latestStats.overall_metrics.f1 * 100).toFixed(1)}%
                  </span>
                  <span className={styles.metricName}>OVERALL F1 / ACCURACY</span>
                </div>
                <div className={styles.metricBlock}>
                  <span className={styles.metricValue} style={{ color: 'var(--glow-cyan)' }}>
                    {(latestStats.overall_metrics.precision * 100).toFixed(1)}%
                  </span>
                  <span className={styles.metricName}>AVERAGE PRECISION</span>
                </div>
                <div className={styles.metricBlock}>
                  <span className={styles.metricValue} style={{ color: 'var(--glow-purple)' }}>
                    {(latestStats.overall_metrics.recall * 100).toFixed(1)}%
                  </span>
                  <span className={styles.metricName}>AVERAGE RECALL</span>
                </div>
                <div className={styles.metricBlock}>
                  <span className={styles.metricValue}>
                    {latestStats.split}
                  </span>
                  <span className={styles.metricName}>DATASET SPLIT</span>
                </div>
              </div>
            )}

            {/* Historical Charts (Recharts) */}
            <div className={styles.chartContainer} data-testid="recharts-wrapper">
              <span className={styles.inputLabel}>ACCURACY / REGRESSION OVER TIME</span>
              {chartData.length === 0 ? (
                <div className={styles.chartFallback}>No run history found. Run evaluation to see trends.</div>
              ) : (
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={chartData} margin={{ top: 15, right: 10, left: -25, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2a2a35" />
                    <XAxis
                      dataKey="timestamp"
                      stroke="#8a8a9a"
                      fontSize={10}
                      tickFormatter={(t) => t.slice(11, 16)} // Show HH:MM
                    />
                    <YAxis stroke="#8a8a9a" fontSize={10} domain={[0.0, 1.0]} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#020204', borderColor: '#2a2a35', color: '#fff' }}
                      itemStyle={{ fontSize: '11px' }}
                      labelStyle={{ fontSize: '10px', color: '#8a8a9a' }}
                    />
                    <Legend wrapperStyle={{ fontSize: '10px', marginTop: '5px' }} />
                    <Line
                      name="F1 / Accuracy"
                      type="monotone"
                      dataKey="f1"
                      stroke="hsl(145, 80%, 45%)"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                      activeDot={{ r: 5 }}
                    />
                    <Line
                      name="Precision"
                      type="monotone"
                      dataKey="precision"
                      stroke="hsl(180, 100%, 50%)"
                      strokeWidth={1.5}
                      dot={{ r: 2 }}
                    />
                    <Line
                      name="Recall"
                      type="monotone"
                      dataKey="recall"
                      stroke="hsl(270, 100%, 60%)"
                      strokeWidth={1.5}
                      dot={{ r: 2 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </ConsolePanel>
        </div>

        {/* Right Column: Live Logs Terminal */}
        <div data-testid="log-terminal-panel">
          <ConsolePanel title="EVALUATION TELEMETRY LOGS" glowColor="purple">
            <TerminalConsole logs={logs} taskId={taskId} />
          </ConsolePanel>
        </div>
      </div>

      {/* 3. Bottom Table: Side-by-Side Audit Comparison */}
      {latestStats && (
        <div className={styles.tableContainer}>
          <div className={styles.tableHeaderBar}>
            <span className={styles.inputLabel} style={{ fontSize: '0.85rem' }}>
              Detailed Extraction Auditing (Split: {latestStats.split}, Version: {latestStats.prompt_version})
            </span>
            <div className={styles.tableFilters}>
              <label htmlFor="mismatch-toggle" className={styles.filterLabel}>
                <input
                  id="mismatch-toggle"
                  type="checkbox"
                  checked={showMismatchesOnly}
                  onChange={(e) => setShowMismatchesOnly(e.target.checked)}
                  className={styles.checkbox}
                />
                SHOW MISMATCHES ONLY
              </label>
            </div>
          </div>

          <div className={styles.overflowWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th className={styles.th}>ID</th>
                  <th className={styles.th}>Overall F1</th>
                  <th className={styles.th}>Skills</th>
                  <th className={styles.th}>Tech Stack</th>
                  <th className={styles.th}>Seniority</th>
                  <th className={styles.th}>Remote Policy</th>
                  <th className={styles.th}>Role Archetype</th>
                  <th className={styles.th}>Salary Band</th>
                </tr>
              </thead>
              <tbody>
                {filteredDiffs.map((diff) => {
                  const actualObj = diff.actual || {};
                  return (
                    <tr key={diff.eval_id} className={styles.tr}>
                      <td className={`${styles.td} ${styles.tdMono}`}>{diff.eval_id}</td>
                      <td className={`${styles.td} ${styles.tdMono}`} style={{ color: diff.overall_f1 === 1 ? 'var(--glow-green)' : 'var(--glow-cyan)' }}>
                        {(diff.overall_f1 * 100).toFixed(0)}%
                      </td>
                      {renderFieldCell('skills', diff.expected.skills, actualObj.skills, diff.matching_status)}
                      {renderFieldCell('tech_stack', diff.expected.tech_stack, actualObj.tech_stack, diff.matching_status)}
                      {renderFieldCell('seniority', diff.expected.seniority, actualObj.seniority, diff.matching_status)}
                      {renderFieldCell('remote_policy', diff.expected.remote_policy, actualObj.remote_policy, diff.matching_status)}
                      {renderFieldCell('role_archetype', diff.expected.role_archetype, actualObj.role_archetype, diff.matching_status)}
                      {renderFieldCell('salary_band', diff.expected.salary_band, actualObj.salary_band, diff.matching_status)}
                    </tr>
                  );
                })}
                {filteredDiffs.length === 0 && (
                  <tr>
                    <td colSpan={8} className={styles.td} style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>
                      No evaluation items to display.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
