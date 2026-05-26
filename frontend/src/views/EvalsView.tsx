import React from 'react';
import { ConsolePanel } from '../components/ConsolePanel';
import styles from './Views.module.css';

export const EvalsView: React.FC = () => {
  return (
    <div className={styles.viewGrid}>
      <ConsolePanel title="EVALUATION SUITES" glowColor="cyan">
        <div className={styles.centeredMetrics}>
          <div className={styles.telemetryStat}>
            <span className={styles.telemetryNumber}>N/A</span>
            <span className={styles.telemetryLabel}>ACCURACY RATE</span>
          </div>
          <p className={styles.statusDescription}>
            Evals framework loaded. Structured accuracy audits, regression metrics, and warning flags will be presented here.
          </p>
        </div>
      </ConsolePanel>
      <ConsolePanel title="SYSTEM SAFETY LIMIT" glowColor="magenta">
        <div className={styles.anomalyBanner}>
          <span className={styles.anomalySymbol}>▲</span>
          <span className={styles.anomalyLabel}>KILL CRITERION STATUS: SAFE</span>
        </div>
      </ConsolePanel>
    </div>
  );
};
