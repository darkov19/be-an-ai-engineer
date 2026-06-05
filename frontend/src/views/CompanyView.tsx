import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import styles from './CompanyView.module.css';

interface Technology {
  name: string;
  count: number;
}

interface Fingerprint {
  company_slug: string;
  company_name: string;
  role_archetypes: string[];
  top_technologies: Technology[];
  llm_observation: string;
  updated_at?: string;
}

export const CompanyView: React.FC = () => {
  const { companySlug } = useParams<{ companySlug: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const isDemo = searchParams.get('demo') === 'true';

  const fingerprintQuery = useQuery({
    queryKey: ['company-fingerprint', companySlug],
    enabled: Boolean(companySlug),
    queryFn: async (): Promise<Fingerprint> => {
      if (!companySlug) {
        throw new Error('Company slug is required.');
      }

      const res = await fetch(`/api/v1/company/${encodeURIComponent(companySlug)}`);
      if (!res.ok) {
        if (res.status === 404) {
          throw new Error(`Company '${companySlug}' fingerprint not found.`);
        }
        throw new Error('Failed to retrieve company stack fingerprint.');
      }

      const data = await res.json();
      if (!Array.isArray(data.role_archetypes) || !Array.isArray(data.top_technologies)) {
        throw new Error('Invalid company fingerprint payload.');
      }

      const roleArchetypes = data.role_archetypes
        .filter((item: unknown): item is string => typeof item === 'string' && item.trim().length > 0)
        .slice(0, 5);

      while (roleArchetypes.length < 5) {
        roleArchetypes.push('Hiring pattern unavailable in cached fingerprint.');
      }

      return {
        company_slug: String(data.company_slug || companySlug),
        company_name: String(data.company_name || companySlug),
        role_archetypes: roleArchetypes,
        top_technologies: data.top_technologies
          .filter((item: unknown): item is Technology => (
            typeof item === 'object' &&
            item !== null &&
            typeof (item as Technology).name === 'string' &&
            typeof (item as Technology).count === 'number'
          ))
          .slice(0, 10),
        llm_observation: String(data.llm_observation || 'No stack observation available.'),
        updated_at: typeof data.updated_at === 'string' ? data.updated_at : undefined,
      };
    },
  });

  const fingerprint = fingerprintQuery.data;
  const error = fingerprintQuery.error instanceof Error ? fingerprintQuery.error.message : null;

  const handleCloseDemo = () => {
    navigate('/');
  };

  if (fingerprintQuery.isLoading) {
    return (
      <div className={styles.loadingContainer}>
        <div className={styles.pulseScanner}>
          <span className={styles.logoSymbol}>▲</span>
          <span className={styles.scanningText}>SCANNING COGNITIVE CORES // RETRIEVING FINGERPRINT...</span>
        </div>
      </div>
    );
  }

  if (error || !fingerprint) {
    return (
      <div className={styles.errorContainer}>
        <div className={styles.faultPanel}>
          <span className={styles.errorSymbol}>▲</span>
          <h2 className={styles.errorTitle}>DIAGNOSTIC FAULT // DATA RETRIEVAL FAILURE</h2>
          <p className={styles.errorText}>{error || 'Unknown error occurred.'}</p>
          <button onClick={() => navigate('/')} className={styles.btnBack}>
            RETURN TO COCKPIT DASHBOARD
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.hudContainer}>
      <header className={styles.hudHeader}>
        <div className={styles.logoSection}>
          <span className={styles.logoSymbol}>▲</span>
          <h1 className={styles.logoText}>
            {fingerprint.company_name.toUpperCase()} // STACK FINGERPRINT
          </h1>
        </div>
        
        <div className={styles.headerControls}>
          {isDemo && (
            <button
              onClick={handleCloseDemo}
              className={styles.closeDemoBtn}
              aria-label="Close demo and return to dashboard"
            >
              [CLOSE DEMO]
            </button>
          )}
          <span className={styles.statusBadge} role="status">
            SYS_STATUS: nominal // public_view
          </span>
        </div>
      </header>

      <div className={styles.mainLayout}>
        <section className={`${styles.hudPanel} ${styles.cyan}`}>
          <h2 className={styles.panelTitle}>TOP 10 EXTRACTED TECHNOLOGIES</h2>
          <div className={styles.techList}>
            {fingerprint.top_technologies.length === 0 ? (
              <div className={styles.emptyText}>[NO EXTRACTED TECHNOLOGIES RECORDED]</div>
            ) : (
              fingerprint.top_technologies.map((tech) => (
                <div key={tech.name} className={styles.techRow}>
                  <span className={styles.techName}>{tech.name}</span>
                  <span className={styles.techCount}>{tech.count}</span>
                </div>
              ))
            )}
          </div>
        </section>

        <section className={`${styles.hudPanel} ${styles.purple}`}>
          <h2 className={styles.panelTitle}>ROLE ARCHETYPE SUMMARY</h2>
          <div className={styles.bulletsList}>
            {fingerprint.role_archetypes.map((bullet, idx) => (
              <div key={idx} className={styles.bulletItem}>
                <span className={styles.bulletMarker}>0{idx + 1} //</span>
                <span className={styles.bulletText}>{bullet}</span>
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className={styles.observationContainer}>
        <h3 className={styles.observationTitle}>AI Stack Observation</h3>
        <p className={styles.observationText}>{fingerprint.llm_observation}</p>
      </div>

      <footer className={styles.hudFooter}>
        <span className={styles.footerMeta}>
          LAST_UPDATED: {fingerprint.updated_at ? new Date(fingerprint.updated_at).toLocaleString() : 'N/A'}
        </span>
        <span className={styles.footerVersion}>VER: 1.2.0-HUD // SCREEN-SHARE_MODE</span>
      </footer>
    </div>
  );
};
