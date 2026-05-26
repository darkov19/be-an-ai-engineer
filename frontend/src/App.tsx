import { useState, useEffect } from 'react';
import { Routes, Route, useNavigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { DashboardView } from './views/DashboardView';
import { IngestionView } from './views/IngestionView';
import { EvalsView } from './views/EvalsView';
import { LedgerView } from './views/LedgerView';
import { ProfileView } from './views/ProfileView';
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
  const navigate = useNavigate();

  useEffect(() => {
    const fetchHealth = () => {
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
    };

    fetchHealth();
    // Maintain async polling every 5 seconds
    const interval = setInterval(fetchHealth, 5000);
    return () => clearInterval(interval);
  }, []);

  // Keyboard shortcut controller (Alt+1 to Alt+5)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const activeEl = document.activeElement;
      const isInput = activeEl && (
        activeEl.tagName === 'INPUT' || 
        activeEl.tagName === 'TEXTAREA' || 
        (activeEl as HTMLElement).isContentEditable
      );
      if (isInput) return;

      const digitMatch = e.code.match(/^Digit([1-5])$/);
      if (e.altKey && digitMatch) {
        e.preventDefault();
        const tabIndex = parseInt(digitMatch[1]) - 1;
        const routes = ['/', '/ingest', '/evals', '/ledger', '/profile'];
        navigate(routes[tabIndex]);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [navigate]);

  return (
    <Layout health={health} loading={loading}>
      <Routes>
        <Route path="/" element={<DashboardView health={health} loading={loading} />} />
        <Route path="/ingest" element={<IngestionView />} />
        <Route path="/evals" element={<EvalsView />} />
        <Route path="/ledger" element={<LedgerView />} />
        <Route path="/profile" element={<ProfileView />} />
      </Routes>
    </Layout>
  );
}

export default App;
