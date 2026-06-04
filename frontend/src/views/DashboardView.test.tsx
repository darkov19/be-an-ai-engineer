import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react';
import { DashboardView } from './DashboardView';

// Mock fetch globally
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

describe('DashboardView - Quality Gate Warning and Lock UI', () => {
  beforeEach(() => {
    mockFetch.mockReset();
    // Realistic conditional mock responses
    mockFetch.mockImplementation((url) => {
      if (url === '/api/v1/profiles/current') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: 1,
            skills: ['Python', 'FastAPI'],
            updated_at: new Date().toISOString(), // fresh profile
          }),
        });
      }
      if (url === '/api/v1/jobs/analytics') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: {
              geo_segments: {
                us_eu_remote: {
                  skill_gap: [
                    { skill: 'RAG', market_frequency: 0.8 },
                    { skill: 'pgvector', market_frequency: 0.7 }
                  ]
                },
                india_ai_product: {
                  skill_gap: []
                }
              }
            }
          }),
        });
      }
      // Default fallback
      return Promise.resolve({
        ok: true,
        json: async () => ({ ok: true }),
      });
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('renders no banners and operates normally under nominal system state', async () => {
    const healthData = {
      data: {
        status: 'healthy',
        database: 'connected',
        timestamp: '2026-06-04T12:00:00Z',
        corpus_size: 150,
        eval_accuracy: 0.85,
        system_state: 'nominal',
        warning_mode: false,
      },
    };

    render(<DashboardView health={healthData} loading={false} />);

    // Wait for the async profile fetch update to finish, avoiding act warnings
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith('/api/v1/profiles/current');
    });

    // Banners should not be present
    expect(screen.queryByText(/KILL CRITERION TRIGGERED/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Danger Zone/i)).not.toBeInTheDocument();

    // Standard panels should be present
    expect(screen.getByText(/SYSTEM DIAGNOSTICS/i)).toBeInTheDocument();
    expect(screen.getByText(/COGNITIVE CORE STATUS:/i)).toBeInTheDocument();
    expect(screen.getByText(/SYSTEM TERMINAL LOGS/i)).toBeInTheDocument();
  });

  it('renders yellow top warning banner and operates normally under warning system state', async () => {
    const healthData = {
      data: {
        status: 'healthy',
        database: 'connected',
        timestamp: '2026-06-04T12:00:00Z',
        corpus_size: 50,
        eval_accuracy: 0.85,
        system_state: 'warning',
        warning_mode: true,
      },
    };

    render(<DashboardView health={healthData} loading={false} />);

    // Wait for the async profile fetch update to finish, avoiding act warnings
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith('/api/v1/profiles/current');
    });

    // Yellow warning banner should be rendered
    const warningBanner = screen.getByText(/Danger Zone: Ingestion quality thresholds near limit/i);
    expect(warningBanner).toBeInTheDocument();
    expect(screen.queryByText(/KILL CRITERION TRIGGERED/i)).not.toBeInTheDocument();

    // Standard panels should be present
    expect(screen.getByText(/SYSTEM DIAGNOSTICS/i)).toBeInTheDocument();
    expect(screen.getByText(/SYSTEM TERMINAL LOGS/i)).toBeInTheDocument();
  });

  it('renders full-page magenta lock banner and blocks standard console panels under locked system state', async () => {
    const healthData = {
      data: {
        status: 'healthy',
        database: 'connected',
        timestamp: '2026-06-04T12:00:00Z',
        corpus_size: 50,
        eval_accuracy: 0.65,
        system_state: 'locked',
        warning_mode: false,
      },
    };

    render(<DashboardView health={healthData} loading={false} />);

    // Wait for the async profile fetch update to finish, avoiding act warnings
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith('/api/v1/profiles/current');
    });

    // Magenta lock banner should be rendered
    const lockedBanner = screen.getByText(/Ingestion corpus or accuracy below minimum quality thresholds/i);
    expect(lockedBanner).toBeInTheDocument();
    expect(screen.queryByText(/Danger Zone/i)).not.toBeInTheDocument();

    // Standard panels should be blocked / absent
    expect(screen.queryByText(/SYSTEM DIAGNOSTICS/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/SYSTEM TERMINAL LOGS/i)).not.toBeInTheDocument();
  });

  it('renders BrainVisualizer and TelemetryChart widgets and supports resolving anomalies', async () => {
    const healthData = {
      data: {
        status: 'healthy',
        database: 'connected',
        timestamp: '2026-06-04T12:00:00Z',
        corpus_size: 150,
        eval_accuracy: 0.85,
        system_state: 'nominal',
        warning_mode: false,
      },
    };

    render(<DashboardView health={healthData} loading={false} />);

    // Wait for mock fetch triggers
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith('/api/v1/profiles/current');
      expect(mockFetch).toHaveBeenCalledWith('/api/v1/jobs/analytics');
    });

    // Verify BrainVisualizer is rendered by checking its title/legend
    expect(screen.getByText(/COGNITIVE SKILL NODE DIAGNOSTICS/i)).toBeInTheDocument();
    expect(screen.getAllByText("PROVEN")[0]).toBeInTheDocument();
    expect(screen.getAllByText("NOMINAL")[0]).toBeInTheDocument();
    expect(screen.getAllByText("ANOMALY")[0]).toBeInTheDocument();

    // Verify TelemetryChart is rendered
    expect(screen.getByText(/HEMODYNAMIC LEARNING WAVE/i)).toBeInTheDocument();

    // Verify Active Directives panel is rendered
    expect(screen.getByText(/ACTIVE PATHWAY DIRECTIVES/i)).toBeInTheDocument();
    expect(screen.getByText(/NO ACTIVE DIRECTIVES LOADED/i)).toBeInTheDocument();

    const ragNode = screen.getByRole('button', { name: /Skill: RAG\. Status: anomaly/i });
    fireEvent.mouseEnter(ragNode);
    fireEvent.click(await screen.findByRole('button', { name: /\[RESOLVE ANOMALY\]/i }));

    expect(screen.getAllByText(/RAG/i).length).toBeGreaterThan(0);
    expect(screen.getByLabelText(/ENTER GIT COMMIT HASH/i)).toBeInTheDocument();
    expect(screen.getByText(/Directive status: PENDING COMMIT LINK/i)).toBeInTheDocument();
  });

  it('allows keyboard users to resolve anomaly nodes', async () => {
    const healthData = {
      data: {
        status: 'healthy',
        database: 'connected',
        timestamp: '2026-06-04T12:00:00Z',
        corpus_size: 150,
        eval_accuracy: 0.85,
        system_state: 'nominal',
        warning_mode: false,
      },
    };

    render(<DashboardView health={healthData} loading={false} />);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith('/api/v1/jobs/analytics');
    });

    const pgvectorNode = screen.getByRole('button', { name: /Skill: pgvector\. Status: anomaly/i });
    fireEvent.keyDown(pgvectorNode, { key: 'Enter' });

    expect(screen.getAllByText(/PGVECTOR/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Accepted active directive to resolve anomaly: pgvector/i)).toBeInTheDocument();
  });
});
