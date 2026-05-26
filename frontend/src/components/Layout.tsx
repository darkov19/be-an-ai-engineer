import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import styles from './Layout.module.css';

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

interface LayoutProps {
  children: React.ReactNode;
  health: HealthResponse | null;
  loading: boolean;
}

export const Layout: React.FC<LayoutProps> = ({ children, health, loading }) => {
  const location = useLocation();
  const [triggerSweep, setTriggerSweep] = React.useState(false);
  const isFirstMount = React.useRef(true);

  React.useEffect(() => {
    if (isFirstMount.current) {
      isFirstMount.current = false;
      return;
    }
    setTriggerSweep(true);
    const timer = setTimeout(() => setTriggerSweep(false), 250);
    return () => clearTimeout(timer);
  }, [location.pathname]);

  const tabs = [
    { path: '/', label: 'Dashboard' },
    { path: '/ingest', label: 'Ingestion' },
    { path: '/evals', label: 'Evals' },
    { path: '/ledger', label: 'Ledger' },
    { path: '/profile', label: 'Profile' },
  ];

  return (
    <div className={styles.hudContainer}>
      {/* CRT sweep line */}
      <div
        className={`${styles.crtSweepLine} ${triggerSweep ? styles.crtSweepActive : ''}`}
        aria-hidden="true"
      />

      <header className={styles.hudHeader}>
        <div className={styles.logoSection}>
          <span className={styles.logoSymbol}>▲</span>
          <h1 className={styles.logoText}>ANTIGRAVITY // COGNITIVE CORE</h1>
        </div>
        <div className={styles.statusIndicator} aria-live="polite">
          <span
            className={`${styles.pulseDot} ${
              health?.data?.status === 'healthy' ? styles.green : styles.red
            }`}
          />
          <span className={styles.statusLabel}>
            SYS_STATUS: {loading ? 'SCANNING...' : health?.data?.status?.toUpperCase() || 'ERROR'}
          </span>
        </div>
      </header>

      <div className={styles.mainLayout}>
        <nav className={styles.sidebar} role="tablist" aria-label="Cockpit Navigation">
          {tabs.map((tab) => (
            <NavLink
              key={tab.path}
              to={tab.path}
              role="tab"
              aria-selected={location.pathname === tab.path}
              aria-controls="console-content"
              className={({ isActive }: { isActive: boolean }) =>
                `${styles.navLink} ${isActive ? styles.activeNavLink : ''}`
              }
            >
              {({ isActive }: { isActive: boolean }) => (
                <span className={styles.navLabel}>
                  {isActive ? `[ ${tab.label} ]` : `\u00A0\u00A0${tab.label}\u00A0\u00A0`}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        <main id="console-content" role="tabpanel" aria-live="polite" className={styles.contentArea}>
          {children}
        </main>
      </div>

      <footer className={styles.hudFooter}>
        <span className={styles.footerMeta}>USER: DARKO // CLASSIFIED SPRINT 1.2</span>
        <span className={styles.footerVersion}>VER: 1.2.0-HUD</span>
      </footer>
    </div>
  );
};
