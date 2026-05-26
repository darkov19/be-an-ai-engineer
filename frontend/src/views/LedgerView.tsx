import React from 'react';
import { ConsolePanel } from '../components/ConsolePanel';
import styles from './Views.module.css';

export const LedgerView: React.FC = () => {
  return (
    <div className={styles.viewGrid}>
      <ConsolePanel title="ACCOUNTABILITY LEDGER" glowColor="cyan">
        <div className={styles.centeredMetrics}>
          <div className={styles.telemetryStat}>
            <span className={styles.telemetryNumber}>0</span>
            <span className={styles.telemetryLabel}>COMMITTED TASKS</span>
          </div>
          <p className={styles.statusDescription}>
            The ledger database is synced. Commit history, git linking, and backlog accountability records will show here.
          </p>
        </div>
      </ConsolePanel>
      <ConsolePanel title="LEDGER MONITOR" glowColor="green">
        <div className={styles.logsConsole}>
          <div className={styles.logLine}>[LEDGER] Connected to ledger schema...</div>
          <div className={styles.logLine}>[LEDGER] Standing by...</div>
        </div>
      </ConsolePanel>
    </div>
  );
};
