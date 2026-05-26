import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import App from './App';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('App HUD Component', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('renders scanning state initially', async () => {
    mockFetch.mockImplementation(() => new Promise(() => {})); // Never resolves to simulate loading
    render(<App />);
    expect(screen.getByText(/SCANNING SYSTEM CHANNELS/i)).toBeInTheDocument();
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

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/SYS_STATUS: HEALTHY/i)).toBeInTheDocument();
      expect(screen.getByText(/ONLINE/i)).toBeInTheDocument();
      expect(screen.getByText(/CONNECTED/i)).toBeInTheDocument();
    });
  });

  it('renders offline status when fetch fails', async () => {
    mockFetch.mockRejectedValue(new Error('Network error'));

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/DIAGNOSTIC FAULT DETECTED/i)).toBeInTheDocument();
      expect(screen.getByText(/FETCH_ERROR/i)).toBeInTheDocument();
    });
  });
});
