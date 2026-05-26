import React from 'react';
import { ConsolePanel } from '../components/ConsolePanel';
import styles from './Views.module.css';

export const IngestionView: React.FC = () => {
  return (
    <div className={styles.viewGrid}>
      <ConsolePanel title="INGESTION PROCESSOR" glowColor="cyan">
        <div className={styles.centeredMetrics}>
          <div className={styles.telemetryStat}>
            <span className={styles.telemetryNumber}>0.00</span>
            <span className={styles.telemetryLabel}>B/S INGEST RATE</span>
          </div>
          <p className={styles.statusDescription}>
            Ingestion channels inactive. Drag-and-drop CSV fallback or multi-source parse configurations will appear here.
          </p>
        </div>
      </ConsolePanel>
      <ConsolePanel title="ACTIVE PIPELINES" glowColor="purple">
        <div className={styles.logsConsole}>
          <div className={styles.logLine}>[SYS] Standing by for ingestion stream triggers...</div>
          <div className={styles.logLine}>[INFO] Available parsers: CSV, PDF, Markdown, JSON.</div>
        </div>
      </ConsolePanel>
    </div>
  );
};
