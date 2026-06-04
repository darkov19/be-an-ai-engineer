import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { DashboardView } from './DashboardView';

// Mock fetch globally
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

describe('DashboardView - Quality Gate Warning and Lock UI', () => {
  beforeEach(() => {
    mockFetch.mockReset();
    // Default mock response for profile fetch
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 1,
        updated_at: new Date().toISOString(), // fresh profile
      }),
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
});
