import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent, cleanup, act } from '@testing-library/react';
import { ProfileView } from './ProfileView';
import { DashboardView } from './DashboardView';

// Mock fetch globally
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

describe('Profile Management & Freshness Monitor', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders profile fields and loads current profile data on mount', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 1,
        skills: ['React', 'TypeScript'],
        seniority: 'Senior',
        tech_stack: ['FastAPI', 'PostgreSQL'],
        years_of_experience: 5,
        geo_preference: 'Remote',
        updated_at: '2026-05-26T20:00:00Z',
      }),
    });

    render(<ProfileView />);

    await waitFor(() => {
      expect(screen.getByLabelText(/skills/i)).toHaveValue('React, TypeScript');
      expect(screen.getByLabelText(/tech stack/i)).toHaveValue('FastAPI, PostgreSQL');
      expect(screen.getByLabelText(/seniority level/i)).toHaveValue('Senior');
      expect(screen.getByLabelText(/years of experience/i)).toHaveValue(5);
      expect(screen.getByLabelText(/geographical preference/i)).toHaveValue('Remote');
    });

    expect(mockFetch).toHaveBeenCalledWith('/api/v1/profiles/current');
  });

  it('triggers debounced auto-save after typing and shows compiling/saved states', async () => {
    // Initial GET call mock
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: 1,
        skills: ['React'],
        seniority: 'Senior',
        tech_stack: [],
        years_of_experience: 5,
        geo_preference: 'Remote',
        updated_at: '2026-05-26T20:00:00Z',
      }),
    });

    render(<ProfileView />);

    // Wait for the GET fetch to finish
    await waitFor(() => {
      expect(screen.getByLabelText(/skills/i)).toHaveValue('React');
    });

    // Mock PUT call returning successfully
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: 1,
        skills: ['React', 'TypeScript'],
        seniority: 'Senior',
        tech_stack: [],
        years_of_experience: 5,
        geo_preference: 'Remote',
        updated_at: '2026-05-26T21:00:00Z',
      }),
    });

    // Simulate typing
    fireEvent.change(screen.getByLabelText(/skills/i), { target: { value: 'React, TypeScript' } });

    // Instantly check for [COMPILING...]
    expect(screen.getByText(/\[COMPILING\.\.\.\]/i)).toBeInTheDocument();

    // Wait for the 250ms debounce time to run
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 300));
    });

    // Wait for saving indicators to show [SAVED]
    await waitFor(() => {
      expect(screen.getByText(/\[SAVED\]/i)).toBeInTheDocument();
    });

    // Check that fetch PUT was called with correct parameters
    expect(mockFetch).toHaveBeenLastCalledWith('/api/v1/profiles/current', expect.objectContaining({
      method: 'PUT',
      body: JSON.stringify({
        skills: ['React', 'TypeScript'],
        tech_stack: [],
        seniority: 'Senior',
        years_of_experience: 5,
        geo_preference: 'Remote',
      }),
    }));
  });

  it('applies error indicators and magenta borders on save failure', async () => {
    // Initial GET call mock
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: 1,
        skills: ['React'],
        seniority: 'Senior',
        tech_stack: [],
        years_of_experience: 5,
        geo_preference: 'Remote',
        updated_at: '2026-05-26T20:00:00Z',
      }),
    });

    render(<ProfileView />);

    await waitFor(() => {
      expect(screen.getByLabelText(/skills/i)).toHaveValue('React');
    });

    // Mock PUT call returning error
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({
        error: true,
        code: 'VALIDATION_ERROR',
        detail: 'Skills list contains forbidden characters',
      }),
    });

    // Trigger typing update
    fireEvent.change(screen.getByLabelText(/skills/i), { target: { value: 'React, @@@' } });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 300));
    });

    // Wait for the error indicator
    await waitFor(() => {
      expect(screen.getByText(/\[SAVE_ERR: Skills list contains forbidden characters\]/i)).toBeInTheDocument();
    });

    // Check if error border classes are applied
    expect(screen.getByLabelText(/skills/i).className).toContain('inputError');
  });

  it('renders yellow stale warning banner on Dashboard when profile is 21+ days old', async () => {
    const staleDate = new Date();
    staleDate.setDate(staleDate.getDate() - 22); // 22 days ago
    
    // Mock GET profile returning stale update timestamp
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: 1,
        updated_at: staleDate.toISOString(),
      }),
    });
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ ok: true }) });

    render(<DashboardView health={{ data: { status: 'healthy', database: 'connected', timestamp: 'now' } }} loading={false} />);

    await waitFor(() => {
      expect(screen.getByText(/Profile is stale/i)).toBeInTheDocument();
    });
  });

  it('does NOT render yellow warning banner on Dashboard when profile is updated recently', async () => {
    const freshDate = new Date();
    freshDate.setDate(freshDate.getDate() - 2); // 2 days ago
    
    // Mock GET profile returning fresh update timestamp
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: 1,
        updated_at: freshDate.toISOString(),
      }),
    });
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ ok: true }) });

    render(<DashboardView health={{ data: { status: 'healthy', database: 'connected', timestamp: 'now' } }} loading={false} />);

    // Wait for potential rendering, then confirm banner is absent
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });
    expect(screen.queryByText(/Profile is stale/i)).not.toBeInTheDocument();
  });
});
