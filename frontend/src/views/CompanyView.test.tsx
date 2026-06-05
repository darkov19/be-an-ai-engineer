import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CompanyView } from './CompanyView';

// Mock routing hooks
const mockNavigate = vi.fn();
let mockParams = { companySlug: 'stripe' };
let mockSearchParams = new URLSearchParams('');

vi.mock('react-router-dom', () => ({
  useParams: () => mockParams,
  useNavigate: () => mockNavigate,
  useSearchParams: () => [mockSearchParams, vi.fn()],
}));

// Mock fetch globally
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function renderCompanyView() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <CompanyView />
    </QueryClientProvider>
  );
}

describe('CompanyView Stack Fingerprint & Interview Screen-Share View', () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockNavigate.mockReset();
    mockParams = { companySlug: 'stripe' };
    mockSearchParams = new URLSearchParams('');
  });

  afterEach(() => {
    cleanup();
  });

  it('renders loading state on mount', async () => {
    // Return a promise that doesn't resolve immediately to assert loading state
    mockFetch.mockReturnValue(new Promise(() => {}));

    renderCompanyView();

    expect(screen.getByText(/SCANNING COGNITIVE CORES/i)).toBeInTheDocument();
  });

  it('fetches and renders company fingerprint data successfully', async () => {
    const mockFingerprint = {
      company_slug: 'stripe',
      company_name: 'Stripe',
      role_archetypes: [
        'Builds scale-out systems',
        'Implements secure payments',
        'Works with cloud API integration',
        'Develops core platform features',
        'Collaborates on design'
      ],
      top_technologies: [
        { name: 'Python', count: 10 },
        { name: 'React', count: 8 },
      ],
      llm_observation: 'Stripe uses advanced tech integration.',
      updated_at: '2026-06-05T12:00:00Z',
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockFingerprint,
    });

    renderCompanyView();

    // Wait for the data to load
    await waitFor(() => {
      expect(screen.getByText(/STRIPE \/\/ STACK FINGERPRINT/i)).toBeInTheDocument();
    });

    expect(screen.getByText('Python')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
    expect(screen.getByText('React')).toBeInTheDocument();
    expect(screen.getByText('8')).toBeInTheDocument();

    expect(screen.getByText(/Builds scale-out systems/i)).toBeInTheDocument();
    expect(screen.getByText(/Stripe uses advanced tech integration/i)).toBeInTheDocument();
    expect(screen.getByText(/SYS_STATUS: nominal \/\/ public_view/i)).toBeInTheDocument();

    // Verify fetch was called with correct company slug
    expect(mockFetch).toHaveBeenCalledWith('/api/v1/company/stripe');
  });

  it('renders error panel on fetch failure (e.g. 404 Not Found)', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
    });

    renderCompanyView();

    await waitFor(() => {
      expect(screen.getByText(/DIAGNOSTIC FAULT \/\/ DATA RETRIEVAL FAILURE/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Company 'stripe' fingerprint not found./i)).toBeInTheDocument();

    // Test clicking back button
    const backBtn = screen.getByRole('button', { name: /RETURN TO COCKPIT DASHBOARD/i });
    fireEvent.click(backBtn);
    expect(mockNavigate).toHaveBeenCalledWith('/');
  });

  it('renders error panel on general network/server error', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error or server down'));

    renderCompanyView();

    await waitFor(() => {
      expect(screen.getByText(/DIAGNOSTIC FAULT \/\/ DATA RETRIEVAL FAILURE/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Network error or server down/i)).toBeInTheDocument();
  });

  it('conditionally renders [CLOSE DEMO] button when demo=true is present', async () => {
    // Set demo=true search param
    mockSearchParams = new URLSearchParams('demo=true');

    const mockFingerprint = {
      company_slug: 'stripe',
      company_name: 'Stripe',
      role_archetypes: ['A', 'B', 'C', 'D', 'E'],
      top_technologies: [{ name: 'Python', count: 1 }],
      llm_observation: 'Observation text',
      updated_at: '2026-06-05T12:00:00Z',
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockFingerprint,
    });

    renderCompanyView();

    await waitFor(() => {
      expect(screen.getByText(/STRIPE \/\/ STACK FINGERPRINT/i)).toBeInTheDocument();
    });

    // Check [CLOSE DEMO] is in the document
    const closeBtn = screen.getByRole('button', { name: /Close demo and return to dashboard/i });
    expect(closeBtn).toBeInTheDocument();

    // Click [CLOSE DEMO]
    fireEvent.click(closeBtn);
    expect(mockNavigate).toHaveBeenCalledWith('/');
  });

  it('does NOT render [CLOSE DEMO] button when demo parameter is absent', async () => {
    mockSearchParams = new URLSearchParams('');

    const mockFingerprint = {
      company_slug: 'stripe',
      company_name: 'Stripe',
      role_archetypes: ['A', 'B', 'C', 'D', 'E'],
      top_technologies: [{ name: 'Python', count: 1 }],
      llm_observation: 'Observation text',
      updated_at: '2026-06-05T12:00:00Z',
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockFingerprint,
    });

    renderCompanyView();

    await waitFor(() => {
      expect(screen.getByText(/STRIPE \/\/ STACK FINGERPRINT/i)).toBeInTheDocument();
    });

    // [CLOSE DEMO] should not be present
    expect(screen.queryByRole('button', { name: /Close demo and return to dashboard/i })).not.toBeInTheDocument();
  });

  it('encodes company slug before fetching the API route', async () => {
    mockParams = { companySlug: 'stripe?x=1' };
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
    });

    renderCompanyView();

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith('/api/v1/company/stripe%3Fx%3D1');
    });
  });

  it('renders exactly five role archetype rows when API returns fewer items', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        company_slug: 'stripe',
        company_name: 'Stripe',
        role_archetypes: ['A', 'B'],
        top_technologies: [{ name: 'Python', count: 1 }],
        llm_observation: 'Observation text',
      }),
    });

    renderCompanyView();

    await waitFor(() => {
      expect(screen.getByText(/STRIPE \/\/ STACK FINGERPRINT/i)).toBeInTheDocument();
    });

    expect(screen.getByText('01 //')).toBeInTheDocument();
    expect(screen.getByText('05 //')).toBeInTheDocument();
    expect(screen.getAllByText(/Hiring pattern unavailable/i)).toHaveLength(3);
  });
});
