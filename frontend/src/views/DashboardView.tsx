import React from 'react';
import { ConsolePanel } from '../components/ConsolePanel';
import styles from './Views.module.css';

interface HealthData {
  status: string;
  database: string;
  timestamp: string;
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
  return (
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
          <div className={styles.logLine}>[SYS] Standing by for user input...</div>
        </div>
      </ConsolePanel>
    </div>
  );
};
