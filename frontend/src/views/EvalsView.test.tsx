import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent, cleanup, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { EvalsView } from './EvalsView';
import * as evalsApi from '../api/evals';

// Mock Recharts ResponsiveContainer and standard components to avoid JSDOM dimensions issues
vi.mock('recharts', async (importOriginal) => {
  const original = await importOriginal<typeof import('recharts')>();
  return {
    ...original,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="recharts-responsive-container">{children}</div>,
  };
});

// Mock EventSource globally
class MockEventSource {
  url: string;
  listeners: Record<string, ((event: { data: string }) => void)[]> = {};
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;

  static activeInstance: MockEventSource | null = null;

  constructor(url: string) {
    this.url = url;
    MockEventSource.activeInstance = this;
    setTimeout(() => {
      if (this.onopen) this.onopen();
    }, 0);
  }

  addEventListener(event: string, callback: (event: { data: string }) => void) {
    if (!this.listeners[event]) {
      this.listeners[event] = [];
    }
    this.listeners[event].push(callback);
  }

  removeEventListener(event: string, callback: (event: { data: string }) => void) {
    if (this.listeners[event]) {
      this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
    }
  }

  emit(event: string, data: unknown) {
    if (this.listeners[event]) {
      this.listeners[event].forEach(cb => cb({ data: JSON.stringify(data) }));
    }
  }

  close() {
    if (MockEventSource.activeInstance === this) {
      MockEventSource.activeInstance = null;
    }
  }
}

globalThis.EventSource = MockEventSource as unknown as typeof EventSource;

describe('EvalsView Component', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    MockEventSource.activeInstance = null;
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  const renderView = () => {
    return render(
      <QueryClientProvider client={queryClient}>
        <EvalsView />
      </QueryClientProvider>
    );
  };

  it('renders initial dashboard structure correctly with loading states', async () => {
    const fetchHistorySpy = vi.spyOn(evalsApi, 'fetchEvalsHistory').mockResolvedValue([]);
    const fetchLatestSpy = vi.spyOn(evalsApi, 'fetchLatestEvalSummary').mockRejectedValue(new Error('SUMMARY_NOT_FOUND'));

    renderView();

    expect(screen.getByText(/EVALUATION METRICS COCKPIT/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/EVALUATION SPLIT/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/PROMPT VERSION/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /RUN EVALUATION/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(fetchHistorySpy).toHaveBeenCalled();
      expect(fetchLatestSpy).toHaveBeenCalled();
    });

    expect(screen.getByText(/No run history found/i)).toBeInTheDocument();
  });

  it('renders historical charts when history is populated', async () => {
    const historyMock = [
      {
        id: 1,
        run_timestamp: '2026-06-04T12:00:00Z',
        prompt_version: 'extraction_v1',
        extraction_schema_version: '1.0.0',
        overall_accuracy: 0.85,
        overall_precision: 0.86,
        overall_recall: 0.84,
        overall_f1: 0.85,
        accuracy_regression: false,
        metrics: {
          field_metrics: {},
          num_samples: 10,
          prior_f1: null,
          split: 'held_out'
        },
        created_at: '2026-06-04T12:00:00Z'
      }
    ];

    vi.spyOn(evalsApi, 'fetchEvalsHistory').mockResolvedValue(historyMock);
    vi.spyOn(evalsApi, 'fetchLatestEvalSummary').mockRejectedValue(new Error('SUMMARY_NOT_FOUND'));

    renderView();

    await waitFor(() => {
      expect(screen.getByTestId('recharts-responsive-container')).toBeInTheDocument();
    });
    expect(screen.queryByText(/No run history found/i)).not.toBeInTheDocument();
  });

  it('displays detailed comparison table and regression banner if regression triggered', async () => {
    vi.spyOn(evalsApi, 'fetchEvalsHistory').mockResolvedValue([]);
    const latestMock = {
      run_id: 10,
      run_timestamp: '2026-06-04T12:00:00Z',
      prompt_version: 'extraction_v1',
      schema_version: '1.0.0',
      split: 'held_out',
      overall_metrics: { precision: 0.80, recall: 0.75, f1: 0.77 },
      accuracy_regression: true,
      field_metrics: {},
      detailed_diffs: [
        {
          eval_id: 'eval-001',
          expected: { skills: ['FastAPI', 'React'], seniority: 'mid' },
          actual: { skills: ['FastAPI'], seniority: 'mid' },
          matching_status: { skills: false, seniority: true },
          mismatched_fields: ['skills'],
          metrics: {
            skills: { precision: 1.0, recall: 0.5, f1: 0.67 }
          },
          overall_f1: 0.83,
          extraction_error: null
        }
      ]
    };
    vi.spyOn(evalsApi, 'fetchLatestEvalSummary').mockResolvedValue(latestMock);

    renderView();

    await waitFor(() => {
      expect(screen.getByTestId('regression-banner')).toBeInTheDocument();
    });
    expect(screen.getByText(/Structured Extraction F1 Accuracy Regression Detected/i)).toBeInTheDocument();

    expect(screen.getByText('eval-001')).toBeInTheDocument();
    expect(screen.getAllByText('mid')).toHaveLength(2);
    expect(screen.getByTestId('mismatch-skills')).toBeInTheDocument();
  });

  it('runs evaluation, displays loading spinner, and streams logs via SSE', async () => {
    vi.spyOn(evalsApi, 'fetchEvalsHistory').mockResolvedValue([]);
    vi.spyOn(evalsApi, 'fetchLatestEvalSummary').mockRejectedValue(new Error('SUMMARY_NOT_FOUND'));
    const runEvalSpy = vi.spyOn(evalsApi, 'runEvaluationApi').mockResolvedValue({ task_id: 'test-eval-task' });

    renderView();

    const runBtn = screen.getByTestId('run-eval-btn');
    await act(async () => {
      fireEvent.click(runBtn);
    });

    expect(runEvalSpy).toHaveBeenCalledWith({ split: 'held_out', prompt_version: 'extraction_v1', dry_run: false });

    await waitFor(() => {
      expect(MockEventSource.activeInstance).not.toBeNull();
    });

    expect(screen.getByTestId('eval-loading-spinner')).toBeInTheDocument();

    await act(async () => {
      MockEventSource.activeInstance!.emit('task.log', {
        event: 'Evaluating posting eval-001',
        level: 'INFO',
        timestamp: '2026-06-04T12:00:00Z',
      });
    });

    await screen.findByText(/Evaluating posting eval-001/i);

    await act(async () => {
      MockEventSource.activeInstance!.emit('task.completed', {
        overall_metrics: { f1: 0.88 },
        summary_path: '_bmad-output/run-summary-2026-22.json',
      });
    });

    await waitFor(() => {
      expect(screen.queryByTestId('eval-loading-spinner')).not.toBeInTheDocument();
    });
  });
});
