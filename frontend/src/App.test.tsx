import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from './App';

// Mock fetch globally
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

describe('App HUD Component', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders scanning state initially and layouts correctly', async () => {
    mockFetch.mockImplementation(() => new Promise(() => {})); // Never resolves to simulate loading
    render(
      <MemoryRouter initialEntries={['/']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByText(/SYS_STATUS: SCANNING/i)).toBeInTheDocument();
    expect(screen.getByRole('tablist')).toBeInTheDocument();
  });

  it('renders online/connected states when health check returns healthy', async () => {
    mockFetch.mockResolvedValue({
      json: async () => ({
        data: {
          status: 'healthy',
          database: 'connected',
          timestamp: '2026-05-26T20:28:44Z'
        }
      })
    });

    render(
      <MemoryRouter initialEntries={['/']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <App />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/SYS_STATUS: HEALTHY/i)).toBeInTheDocument();
      expect(screen.getByText(/ONLINE/i)).toBeInTheDocument();
      expect(screen.getByText(/CONNECTED/i)).toBeInTheDocument();
    });
  });

  it('renders navigation tabs and supports keyboard shortcuts', async () => {
    mockFetch.mockResolvedValue({
      json: async () => ({
        data: {
          status: 'healthy',
          database: 'connected',
          timestamp: '2026-05-26T20:28:44Z'
        }
      })
    });

    render(
      <MemoryRouter initialEntries={['/']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <App />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/SYS_STATUS: HEALTHY/i)).toBeInTheDocument();
    });

    // Check tabs are rendered
    const tabs = screen.getAllByRole('tab');
    expect(tabs.length).toBe(5);
    
    // Check that Dashboard is active (has brackets)
    expect(tabs[0].textContent).toContain('[ Dashboard ]');
    expect(tabs[1].textContent).toContain('Ingestion');

    // Trigger Alt+2 shortcut to go to Ingestion
    fireEvent.keyDown(window, { altKey: true, key: '2', code: 'Digit2' });
    
    // Now Ingestion should be active, Dashboard inactive
    await waitFor(() => {
      expect(tabs[1].textContent).toContain('[ Ingestion ]');
    });

    // Trigger Alt+3 shortcut to go to Evals
    fireEvent.keyDown(window, { altKey: true, key: '3', code: 'Digit3' });
    await waitFor(() => {
      expect(tabs[2].textContent).toContain('[ Evals ]');
    });

    // Trigger Alt+4 shortcut to go to Ledger
    fireEvent.keyDown(window, { altKey: true, key: '4', code: 'Digit4' });
    await waitFor(() => {
      expect(tabs[3].textContent).toContain('[ Ledger ]');
    });

    // Trigger Alt+5 shortcut to go to Profile
    fireEvent.keyDown(window, { altKey: true, key: '5', code: 'Digit5' });
    await waitFor(() => {
      expect(tabs[4].textContent).toContain('[ Profile ]');
    });

    // Trigger Alt+1 shortcut to return to Dashboard
    fireEvent.keyDown(window, { altKey: true, key: '1', code: 'Digit1' });
    await waitFor(() => {
      expect(tabs[0].textContent).toContain('[ Dashboard ]');
    });
  });

  it('ignores shortcuts when focused in inputs', async () => {
    mockFetch.mockResolvedValue({
      json: async () => ({
        data: {
          status: 'healthy',
          database: 'connected',
          timestamp: '2026-05-26T20:28:44Z'
        }
      })
    });

    render(
      <MemoryRouter initialEntries={['/']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <App />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/SYS_STATUS: HEALTHY/i)).toBeInTheDocument();
    });

    const tabs = screen.getAllByRole('tab');

    // Create and focus an input so document.activeElement is an input field
    const input = document.createElement('input');
    document.body.appendChild(input);
    input.focus();

    // Fire the shortcut on window (where the listener lives) — guard should
    // detect document.activeElement === input and suppress navigation
    fireEvent.keyDown(window, { altKey: true, key: '2', code: 'Digit2' });

    // Ingestion should not become active because focus is in an input
    expect(tabs[0].textContent).toContain('[ Dashboard ]');
    expect(tabs[1].textContent).not.toContain('[ Ingestion ]');

    document.body.removeChild(input);
  });
});
