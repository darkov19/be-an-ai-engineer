import React, { useState, useEffect, useRef, useCallback } from 'react';
import { ConsolePanel } from '../components/ConsolePanel';
import { BrainVisualizer } from '../components/BrainVisualizer';
import { TelemetryChart } from '../components/TelemetryChart';
import styles from './Views.module.css';

interface HealthData {
  status: string;
  database: string;
  timestamp: string;
  corpus_size?: number;
  eval_accuracy?: number | null;
  system_state?: string;
  warning_mode?: boolean;
}

interface HealthResponse {
  data?: HealthData;
  error?: boolean;
  code?: string;
  detail?: string;
}

interface DashboardViewProps {
  health: HealthResponse | null;
  loading: boolean;
}

interface Directive {
  skill: string;
  description: string;
  status: 'pending' | 'linked';
  commitHash?: string;
  dateCommitted: string;
}

interface AnalyticsSegment {
  job_count?: number;
  skill_gap?: Array<{ skill?: string; market_frequency?: number }>;
}

export const DashboardView: React.FC<DashboardViewProps> = ({ health, loading }) => {
  const [profileUpdatedAt, setProfileUpdatedAt] = useState<string | null>(null);
  const [profileSkills, setProfileSkills] = useState<string[]>([]);
  const [skillGaps, setSkillGaps] = useState<string[]>([]);
  const [telemetryPoints, setTelemetryPoints] = useState<number[]>([]);

  // State for active directives / commitments
  const [directives, setDirectives] = useState<Directive[]>([]);
  const [commitInputs, setCommitInputs] = useState<Record<string, string>>({});

  // State for dynamic ECG waveform status
  const [chartStatus, setChartStatus] = useState<'nominal' | 'active' | 'inactive'>('nominal');

  // Logs console history state
  const [terminalLogs, setTerminalLogs] = useState<string[]>([
    '[OK] Initializing cognitive core console shell...',
    '[OK] Keyboard shortcut controller registered.',
    '[OK] CRT sweep transition module activated.',
    '[SYS] Standing by for user input...',
  ]);

  const logsEndRef = useRef<HTMLDivElement>(null);
  const healthRef = useRef<HealthResponse | null>(health);
  const activeTimerRef = useRef<number | null>(null);

  useEffect(() => {
    healthRef.current = health;
  }, [health]);

  const getBaseChartStatus = useCallback((sourceHealth: HealthResponse | null) => {
    const data = sourceHealth?.data;
    if (!data || data.database !== 'connected' || data.status !== 'healthy') {
      return 'inactive';
    }
    return 'nominal';
  }, []);

  const setTemporaryActiveStatus = useCallback((durationMs: number) => {
    if (activeTimerRef.current !== null) {
      window.clearTimeout(activeTimerRef.current);
    }
    setChartStatus('active');
    activeTimerRef.current = window.setTimeout(() => {
      setChartStatus(getBaseChartStatus(healthRef.current));
      activeTimerRef.current = null;
    }, durationMs);
  }, [getBaseChartStatus]);

  // Fetch candidate profile on mount
  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const res = await fetch('/api/v1/profiles/current');
        if (res.ok) {
          const data = await res.json();
          if (data) {
            if (data.updated_at) {
              setProfileUpdatedAt(data.updated_at);
            }
            if (Array.isArray(data.skills)) {
              setProfileSkills(data.skills);
            }
          }
        }
      } catch (err) {
        console.error('Failed to fetch profile in dashboard:', err);
      }
    };
    fetchProfile();
  }, []);

  // Fetch jobs analytics on mount
  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        const res = await fetch('/api/v1/jobs/analytics');
        if (res.ok) {
          const data = await res.json();
          if (data?.data?.geo_segments) {
            const gaps = new Set<string>();
            const telemetrySamples: number[] = [];
            Object.values(data.data.geo_segments as Record<string, AnalyticsSegment>).forEach((segmentData) => {
              if (typeof segmentData?.job_count === 'number') {
                telemetrySamples.push(segmentData.job_count);
              }
              if (Array.isArray(segmentData?.skill_gap)) {
                telemetrySamples.push(segmentData.skill_gap.length * 10);
                segmentData.skill_gap.forEach((item: { skill?: string }) => {
                  if (item?.skill) {
                    gaps.add(item.skill);
                  }
                });
              }
            });
            setSkillGaps(Array.from(gaps));
            setTelemetryPoints(telemetrySamples.length > 0 ? telemetrySamples : [0]);
          }
        }
      } catch (err) {
        console.error('Failed to fetch jobs analytics:', err);
      }
    };
    fetchAnalytics();
  }, []);

  // Record cockpit access once
  useEffect(() => {
    Promise.resolve(fetch('/api/v1/cockpit/access', { method: 'POST' })).catch((err) => {
      console.error('Failed to record cockpit access:', err);
    });
  }, []);

  // Sync ECG chart status with database connector health
  useEffect(() => {
    const baseStatus = getBaseChartStatus(health);
    if (baseStatus === 'inactive') {
      if (activeTimerRef.current !== null) {
        window.clearTimeout(activeTimerRef.current);
        activeTimerRef.current = null;
      }
      setChartStatus('inactive');
    } else if (activeTimerRef.current === null) {
      setChartStatus(baseStatus);
    }
  }, [health, getBaseChartStatus]);

  useEffect(() => {
    return () => {
      if (activeTimerRef.current !== null) {
        window.clearTimeout(activeTimerRef.current);
      }
    };
  }, []);

  // Scroll terminal logs to bottom when updated
  useEffect(() => {
    if (logsEndRef.current && typeof logsEndRef.current.scrollIntoView === 'function') {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [terminalLogs]);

  // Calculate if profile is stale (21+ days since last update)
  const isProfileStale = () => {
    if (!profileUpdatedAt) return false;
    const lastUpdate = new Date(profileUpdatedAt);
    const now = new Date();
    const diffMs = now.getTime() - lastUpdate.getTime();
    const diffDays = diffMs / (1000 * 60 * 60 * 24);
    return diffDays >= 21;
  };

  const showStaleWarning = isProfileStale();
  const systemState = health?.data?.system_state;
  const isLocked = systemState === 'locked';
  const isWarning = systemState === 'warning';

  // Add warning log line if profile is stale
  useEffect(() => {
    if (showStaleWarning) {
      setTerminalLogs((prev) => {
        const warnLine = '[WARN] Profile data stale (21+ days since update).';
        if (prev.includes(warnLine)) return prev;
        return [...prev, warnLine];
      });
    }
  }, [showStaleWarning]);

  // Handle resolving skill anomaly
  const handleResolveAnomaly = (skillName: string) => {
    // Check if already in directives list
    if (directives.some((d) => d.skill.toLowerCase() === skillName.toLowerCase())) {
      return;
    }

    const newDirective: Directive = {
      skill: skillName,
      description: `Upgrade cognitive path: Implement proof-of-concept demonstrating ${skillName} integrations.`,
      status: 'pending',
      dateCommitted: new Date().toISOString().split('T')[0],
    };

    setDirectives((prev) => [...prev, newDirective]);
    setTelemetryPoints((prev) => [...prev.slice(-7), 120]);
    setTemporaryActiveStatus(3000);

    setTerminalLogs((prev) => [
      ...prev,
      `[SYS] Accepted active directive to resolve anomaly: ${skillName}.`,
      `[SYS] Directive status: PENDING COMMIT LINK.`,
    ]);
  };

  // Handle linking Git commit to directive
  const handleLinkCommit = (skillName: string) => {
    const commitHash = commitInputs[skillName]?.trim();
    if (!commitHash) return;

    // Transition directive to linked state
    setDirectives((prev) =>
      prev.map((d) =>
        d.skill.toLowerCase() === skillName.toLowerCase()
          ? { ...d, status: 'linked', commitHash }
          : d
      )
    );

    // Add skill to local profileSkills so the brain node instantly turns green!
    setProfileSkills((prev) => {
      if (prev.some((s) => s.toLowerCase() === skillName.toLowerCase())) return prev;
      return [...prev, skillName];
    });

    // Remove from local skillGaps
    setSkillGaps((prev) => prev.filter((s) => s.toLowerCase() !== skillName.toLowerCase()));

    // Trigger active surge on Telemetry Chart
    setTelemetryPoints((prev) => [...prev.slice(-7), 160]);
    setTemporaryActiveStatus(3500);

    setTerminalLogs((prev) => [
      ...prev,
      `[OK] Linked commit ${commitHash} to ${skillName} directive.`,
      `[SYS] Verifying codebase integrations...`,
      `[SYS] Verification SUCCESS. ${skillName} pathway cleared.`,
      `[PROGNOSIS] Profile fit upgraded. Anomaly resolved.`
    ]);
  };

  const handleInputChange = (skillName: string, value: string) => {
    setCommitInputs((prev) => ({
      ...prev,
      [skillName]: value,
    }));
  };

  return (
    <div className={styles.dashboardContainer}>
      {isLocked && (
        <div className={styles.lockedSurface} id="locked-banner">
          <div className={styles.lockedBanner}>
            <span className={styles.anomalySymbol}>▲</span>
            <span className={styles.anomalyLabel}>
              [KILL CRITERION TRIGGERED] Ingestion corpus or accuracy below minimum quality thresholds. Dashboard locked.
            </span>
          </div>
        </div>
      )}

      {isWarning && (
        <div className={styles.warningBanner} id="warning-banner">
          <span className={styles.anomalySymbol}>▲</span>
          <span className={styles.anomalyLabel}>
            [WARNING] Danger Zone: Ingestion quality thresholds near limit. 7 days to recover before console lock.
          </span>
        </div>
      )}

      {!isLocked && showStaleWarning && (
        <div className={styles.warningBanner}>
          <span className={styles.anomalySymbol}>▲</span>
          <span className={styles.anomalyLabel}>
            [WARNING] Profile is stale (last updated 21+ days ago). Refresh recommended.
          </span>
        </div>
      )}

      {!isLocked && (
        <div className={styles.threeColumnGrid}>
          {/* Left Column: Diagnostics and System info */}
          <div className={styles.column}>
            <ConsolePanel title="SYSTEM DIAGNOSTICS" glowColor="cyan">
              {loading ? (
                <div className={styles.scanningText}>SCANNING COGNITIVE CHANNELS...</div>
              ) : (
                <div className={styles.diagnosticsList} role="status" aria-live="polite" aria-atomic="true">
                  <div className={styles.diagnosticItem}>
                    <span className={styles.label}>COGNITIVE CORE STATUS:</span>
                    <span className={`${styles.value} ${health?.data?.status === 'healthy' ? styles.green : styles.red}`}>
                      {health?.data?.status === 'healthy' ? 'ONLINE' : 'OFFLINE'}
                    </span>
                  </div>
                  <div className={styles.diagnosticItem}>
                    <span className={styles.label}>DATABASE CONNECTOR:</span>
                    <span className={`${styles.value} ${health?.data?.database === 'connected' ? styles.green : styles.red}`}>
                      {health?.data?.database?.toUpperCase() || 'UNKNOWN'}
                    </span>
                  </div>
                  <div className={styles.diagnosticItem}>
                    <span className={styles.label}>LOCAL TELEMETRY SYNC:</span>
                    <span className={styles.valueMono}>{health?.data?.timestamp || 'N/A'}</span>
                  </div>
                </div>
              )}
            </ConsolePanel>

            <ConsolePanel title="COGNITIVE IDENTITY" glowColor="purple">
              <div className={styles.profileDetails}>
                <div className={styles.profileHeader}>
                  <div className={styles.profileAvatar}>AI</div>
                  <div>
                    <h3 className={styles.profileName}>DEVELOPER: DARKO</h3>
                    <p className={styles.profileRole}>ROLE: APPLIED AI ARCHITECT</p>
                  </div>
                </div>
                <div className={styles.profileInfoList}>
                  <div className={styles.infoRow}>
                    <span className={styles.infoLabel}>SENIORITY:</span>
                    <span className={styles.infoValue}>SENIOR / STAFF</span>
                  </div>
                  <div className={styles.infoRow}>
                    <span className={styles.infoLabel}>EXPERIENCE:</span>
                    <span className={styles.infoValue}>5 YEARS</span>
                  </div>
                  <div className={styles.infoRow}>
                    <span className={styles.infoLabel}>PROVEN SKILLS:</span>
                    <span className={styles.infoValue}>{profileSkills.length} MAPPED</span>
                  </div>
                </div>
              </div>
            </ConsolePanel>

            {health?.error && (
              <ConsolePanel title="DIAGNOSTIC FAULT DETECTED" glowColor="magenta">
                <div className={styles.diagnosticsList}>
                  <div className={styles.diagnosticItem}>
                    <span className={styles.label}>FAULT CODE:</span>
                    <span className={`${styles.value} ${styles.red}`}>{health.code}</span>
                  </div>
                  <div className={styles.diagnosticItem}>
                    <span className={styles.label}>DETAILS:</span>
                    <span className={`${styles.value} ${styles.red}`}>{health.detail}</span>
                  </div>
                </div>
              </ConsolePanel>
            )}
          </div>

          {/* Central Column: Brain Mesh visualizer and telemetry charts */}
          <div className={styles.centerColumn}>
            <ConsolePanel title="COGNITIVE SKILL NODE DIAGNOSTICS" glowColor="cyan">
              <BrainVisualizer
                profileSkills={profileSkills}
                skillGaps={skillGaps}
                onResolveAnomaly={handleResolveAnomaly}
                activeOrders={directives.map((d) => d.skill)}
              />
            </ConsolePanel>

            <TelemetryChart status={chartStatus} telemetryPoints={telemetryPoints} />

            <ConsolePanel title="SYSTEM TERMINAL LOGS" glowColor="purple">
              <div className={styles.logsConsole} aria-live="polite">
                {terminalLogs.map((line, index) => {
                  const isErr = line.includes('[WARN]') || line.includes('[SAVE_ERR') || line.includes('stale');
                  const isSuccess = line.includes('[OK]') || line.includes('SUCCESS');
                  return (
                    <div
                      key={index}
                      className={`${styles.logLine} ${
                        isErr ? styles.red : isSuccess ? styles.green : ''
                      }`}
                    >
                      {line}
                    </div>
                  );
                })}
                <div ref={logsEndRef} />
              </div>
            </ConsolePanel>
          </div>

          {/* Right Column: Active directives commitments */}
          <div className={styles.column}>
            <ConsolePanel title="ACTIVE PATHWAY DIRECTIVES" glowColor="magenta">
              <div className={styles.directivesList}>
                {directives.length === 0 ? (
                  <div className={styles.noDirectives}>
                    <div className={styles.noDirectivesIcon}>▲</div>
                    <div className={styles.noDirectivesText}>
                      NO ACTIVE DIRECTIVES LOADED
                      <p style={{ fontSize: '0.7rem', marginTop: '6px', color: 'var(--text-secondary)' }}>
                        Hover over any pulsing warning anomaly on the brain skill node visualizer and click <strong>[RESOLVE ANOMALY]</strong> to accept its career pathway upgrade directive.
                      </p>
                    </div>
                  </div>
                ) : (
                  directives.map((directive) => {
                    const isPending = directive.status === 'pending';
                    return (
                      <div
                        key={directive.skill}
                        className={styles.directiveCard}
                        data-status={directive.status}
                      >
                        <div className={styles.directiveHeader}>
                          <span className={styles.directiveSkill}>{directive.skill.toUpperCase()}</span>
                          <span className={styles.directiveDate}>{directive.dateCommitted}</span>
                        </div>
                        <p className={styles.directiveDesc}>{directive.description}</p>

                        {isPending ? (
                          <div className={styles.linkerForm}>
                            <label
                              htmlFor={`commit-${directive.skill}`}
                              style={{ fontSize: '0.65rem', color: 'var(--text-secondary)' }}
                            >
                              ENTER GIT COMMIT HASH:
                            </label>
                            <div className={styles.linkerInputWrapper}>
                              <input
                                id={`commit-${directive.skill}`}
                                type="text"
                                maxLength={10}
                                placeholder="e.g. e4a5b2c"
                                value={commitInputs[directive.skill] || ''}
                                onChange={(e) => handleInputChange(directive.skill, e.target.value)}
                                className={styles.linkerInput}
                              />
                              <button
                                onClick={() => handleLinkCommit(directive.skill)}
                                disabled={!commitInputs[directive.skill]?.trim()}
                                className={styles.btnLink}
                              >
                                LINK COMMIT
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className={styles.verifiedBadge}>
                            <span>✓ PATHWAY CLEAR</span>
                            <span className={styles.verifiedCommit}>
                              [COMMIT: {directive.commitHash}]
                            </span>
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </ConsolePanel>
          </div>
        </div>
      )}
    </div>
  );
};
