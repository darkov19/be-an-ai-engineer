import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor, fireEvent, within } from '@testing-library/react';
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
                  job_count: 120,
                  top_skills: [
                    { skill: 'Python', count: 80, frequency: 0.67 },
                    { skill: 'FastAPI', count: 60, frequency: 0.50 },
                    { skill: 'RAG', count: 40, frequency: 0.33 },
                    { skill: 'pgvector', count: 30, frequency: 0.25 }
                  ],
                  experience_distribution: {
                    no_minimum: 0.1,
                    three_plus: 0.4,
                    five_plus: 0.3,
                    senior_only: 0.2
                  },
                  profile_fit_score: 0.65,
                  profile_fit_delta: 0.12,
                  skill_gap: [
                    { skill: 'RAG', market_frequency: 0.33, in_profile: false },
                    { skill: 'pgvector', market_frequency: 0.25, in_profile: false }
                  ]
                },
                india_ai_product: {
                  job_count: 80,
                  top_skills: [
                    { skill: 'Python', count: 50, frequency: 0.625 },
                    { skill: 'LLMs', count: 40, frequency: 0.50 }
                  ],
                  experience_distribution: {
                    no_minimum: 0.15,
                    three_plus: 0.35,
                    five_plus: 0.30,
                    senior_only: 0.20
                  },
                  profile_fit_score: 0.55,
                  profile_fit_delta: -0.03,
                  skill_gap: [
                    { skill: 'LLMs', market_frequency: 0.50, in_profile: false }
                  ]
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
    const tooltip = await screen.findByRole('tooltip');
    fireEvent.click(within(tooltip).getByRole('button', { name: /\[RESOLVE ANOMALY\]/i }));

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

describe('DashboardView - Geo-Segmented Market Analysis & Skill-Gap Diff', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date('2026-06-05T12:00:00Z'));
    mockFetch.mockReset();
    mockFetch.mockImplementation((url) => {
      if (url === '/api/v1/profiles/current') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: 1,
            skills: ['Python', 'FastAPI'],
            updated_at: '2026-05-01T12:00:00Z', // stale profile
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
                  job_count: 120,
                  top_skills: [
                    { skill: 'Python', count: 80, frequency: 0.67 },
                    { skill: 'FastAPI', count: 60, frequency: 0.50 },
                    { skill: 'RAG', count: 40, frequency: 0.33 },
                    { skill: 'pgvector', count: 30, frequency: 0.25 }
                  ],
                  experience_distribution: {
                    no_minimum: 0.1,
                    three_plus: 0.4,
                    five_plus: 0.3,
                    senior_only: 0.2
                  },
                  profile_fit_score: 0.65,
                  profile_fit_delta: 0.12,
                  skill_gap: [
                    { skill: 'RAG', market_frequency: 0.33, in_profile: false },
                    { skill: 'pgvector', market_frequency: 0.25, in_profile: false }
                  ]
                },
                india_ai_product: {
                  job_count: 80,
                  top_skills: [
                    { skill: 'Python', count: 50, frequency: 0.625 },
                    { skill: 'LLMs', count: 40, frequency: 0.50 }
                  ],
                  experience_distribution: {
                    no_minimum: 0.15,
                    three_plus: 0.35,
                    five_plus: 0.30,
                    senior_only: 0.20
                  },
                  profile_fit_score: 0.55,
                  profile_fit_delta: -0.03,
                  skill_gap: [
                    { skill: 'LLMs', market_frequency: 0.50, in_profile: false }
                  ]
                }
              }
            }
          }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ ok: true }),
      });
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    cleanup();
  });

  it('renders experience distribution strip and fit score delta with correct formatting and colors', async () => {
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

    expect(screen.getByText(/MARKET EXPERIENCE & PROFILE FIT TELEMETRY/i)).toBeInTheDocument();
    expect(screen.getByText(/US\/EU REMOTE SEGMENT/i)).toBeInTheDocument();
    expect(screen.getByText(/INDIA AI PRODUCT SEGMENT/i)).toBeInTheDocument();

    expect(screen.getByText(/No Min: 10% \| 3\+ Yrs: 40% \| 5\+ Yrs: 30% \| Senior: 20%/i)).toBeInTheDocument();
    expect(screen.getByText(/No Min: 15% \| 3\+ Yrs: 35% \| 5\+ Yrs: 30% \| Senior: 20%/i)).toBeInTheDocument();

    expect(screen.getByText('65%')).toBeInTheDocument();
    const positiveDelta = screen.getByText('+12%');
    expect(positiveDelta).toBeInTheDocument();
    expect(positiveDelta.className).toContain('deltaPositive');
    expect(screen.getByText('55%')).toBeInTheDocument();
    const negativeDelta = screen.getByText('-3%');
    expect(negativeDelta).toBeInTheDocument();
    expect(negativeDelta.className).toContain('deltaNegative');
  });

  it('renders side-by-side columns with top-10 skills indicating mapped vs missing', async () => {
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

    expect(screen.getAllByText('FastAPI').length).toBeGreaterThan(0);
    expect(screen.getAllByText('67%').length).toBeGreaterThan(0);
    expect(screen.getAllByText('50%').length).toBeGreaterThan(0);

    const mappedBadges = await screen.findAllByText('[MAPPED]');
    expect(mappedBadges.length).toBeGreaterThan(0);

    const missingBadges = await screen.findAllByText('[MISSING]');
    expect(missingBadges.length).toBeGreaterThan(0);
  });

  it('renders skill-gap table and handles RESOLVE ANOMALY action click', async () => {
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

    expect(screen.getByText(/COGNITIVE SKILL GAP DIFFERENTIAL/i)).toBeInTheDocument();
    expect(screen.getAllByText('LLMs').length).toBeGreaterThan(0);

    let ragRow: HTMLTableRowElement | null | undefined;
    await waitFor(() => {
      const ragElement = screen.getAllByText('RAG').find(el => el.tagName === 'TD');
      ragRow = ragElement?.closest('tr');
      expect(ragRow).toBeInTheDocument();
    });

    const resolveBtn = within(ragRow!).getByRole('button', { name: /Resolve anomaly for RAG in US\/EU Remote/i });
    fireEvent.click(resolveBtn);

    expect(screen.getByText(/Accepted active directive to resolve anomaly: RAG/i)).toBeInTheDocument();
  });

  it('displays freshness warning banner when candidate profile is stale', async () => {
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
      expect(mockFetch).toHaveBeenCalledWith('/api/v1/profiles/current');
    });

    const warningBanner = screen.getByText(/Profile is stale \(last updated 21\+ days ago\)\. Refresh recommended before the diff can be trusted\./i);
    expect(warningBanner).toBeInTheDocument();
  });
});
