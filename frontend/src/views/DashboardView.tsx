import React, { useState, useEffect } from 'react';
import { ConsolePanel } from '../components/ConsolePanel';
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

export const DashboardView: React.FC<DashboardViewProps> = ({ health, loading }) => {
  const [profileUpdatedAt, setProfileUpdatedAt] = useState<string | null>(null);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const res = await fetch('/api/v1/profiles/current');
        if (res.ok) {
          const data = await res.json();
          if (data && data.updated_at) {
            setProfileUpdatedAt(data.updated_at);
          }
        }
      } catch (err) {
        console.error('Failed to fetch profile in dashboard:', err);
      }
    };
    fetchProfile();
  }, []);

  useEffect(() => {
    Promise.resolve(fetch('/api/v1/cockpit/access', { method: 'POST' })).catch((err) => {
      console.error('Failed to record cockpit access:', err);
    });
  }, []);

  // Calculate if profile is stale (21+ days since last update)
  const isProfileStale = () => {
    if (!profileUpdatedAt) return false;
    const lastUpdate = new Date(profileUpdatedAt);
    const now = new Date();
    
    // Difference in milliseconds
    const diffMs = now.getTime() - lastUpdate.getTime();
    // Convert to days
    const diffDays = diffMs / (1000 * 60 * 60 * 24);
    
    return diffDays >= 21;
  };

  const showStaleWarning = isProfileStale();
  const systemState = health?.data?.system_state;
  const isLocked = systemState === 'locked';
  const isWarning = systemState === 'warning';

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
        <div className={styles.viewGrid}>
          <ConsolePanel title="SYSTEM DIAGNOSTICS" glowColor="cyan">
            {loading ? (
              <div className={styles.scanningText}>SCANNING COGNITIVE CHANNELS...</div>
            ) : (
              <div className={styles.diagnosticsList}>
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

          <ConsolePanel title="SYSTEM TERMINAL LOGS" glowColor="purple">
            <div className={styles.logsConsole}>
              <div className={styles.logLine}>[OK] Initializing cognitive core console shell...</div>
              <div className={styles.logLine}>[OK] Keyboard shortcut controller registered.</div>
              <div className={styles.logLine}>[OK] CRT sweep transition module activated.</div>
              {showStaleWarning && (
                <div className={`${styles.logLine} ${styles.red}`}>
                  [WARN] Profile data stale (21+ days since update).
                </div>
              )}
              <div className={styles.logLine}>[SYS] Standing by for user input...</div>
            </div>
          </ConsolePanel>
        </div>
      )}
    </div>
  );
};
