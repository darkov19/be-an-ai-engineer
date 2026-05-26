import React, { useState, useEffect } from 'react';
import './index.css';

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

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/v1/health')
      .then((res) => res.json())
      .then((data: HealthResponse) => {
        setHealth(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Error fetching health status:', err);
        setHealth({
          error: true,
          code: 'FETCH_ERROR',
          detail: 'Failed to communicate with the backend service.'
        });
        setLoading(false);
      });
  }, []);

  return (
    <div className="hud-container">
      <header className="hud-header">
        <div className="logo-section">
          <span className="logo-symbol">▲</span>
          <h1 className="logo-text">ANTIGRAVITY // COGNITIVE CORE</h1>
        </div>
        <div className="status-indicator">
          <span className={`pulse-dot ${health?.data?.status === 'healthy' ? 'green' : 'red'}`}></span>
          <span className="status-label">SYS_STATUS: {loading ? 'SCANNING...' : health?.data?.status?.toUpperCase() || 'ERROR'}</span>
        </div>
      </header>

      <main className="hud-grid">
        {/* System Diagnostics Card */}
        <section className="hud-card">
          <h2 className="card-title">SYSTEM DIAGNOSTICS</h2>
          {loading ? (
            <div className="loading-spinner">SCANNING SYSTEM CHANNELS...</div>
          ) : (
            <div className="diagnostics-list">
              <div className="diagnostic-item">
                <span className="diagnostic-label">COGNITIVE SERVICE:</span>
                <span className={`diagnostic-value ${health?.data?.status === 'healthy' ? 'healthy' : 'unhealthy'}`}>
                  {health?.data?.status === 'healthy' ? 'ONLINE' : 'OFFLINE'}
                </span>
              </div>
              <div className="diagnostic-item">
                <span className="diagnostic-label">DATABASE CONNECTOR:</span>
                <span className={`diagnostic-value ${health?.data?.database === 'connected' ? 'healthy' : 'unhealthy'}`}>
                  {health?.data?.database?.toUpperCase() || 'UNKNOWN'}
                </span>
              </div>
              <div className="diagnostic-item">
                <span className="diagnostic-label">TIMESTAMP:</span>
                <span className="diagnostic-value timestamp">{health?.data?.timestamp || 'N/A'}</span>
              </div>
            </div>
          )}
        </section>

        {/* Error Details Card (Conditional) */}
        {health?.error && (
          <section className="hud-card error-card">
            <h2 className="card-title text-red">DIAGNOSTIC FAULT DETECTED</h2>
            <div className="diagnostics-list">
              <div className="diagnostic-item">
                <span className="diagnostic-label">ERROR CODE:</span>
                <span className="diagnostic-value text-red">{health.code}</span>
              </div>
              <div className="diagnostic-item">
                <span className="diagnostic-label">DETAILS:</span>
                <span className="diagnostic-value text-red">{health.detail}</span>
              </div>
            </div>
          </section>
        )}
      </main>

      <footer className="hud-footer">
        <span className="footer-meta">USER: DARKO // CLASSIFIED SPRINT 1.1</span>
        <span className="footer-version">VER: 1.1.0-DEV</span>
      </footer>
    </div>
  );
}

export default App;
