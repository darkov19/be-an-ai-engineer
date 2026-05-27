import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react';
import { IngestionView } from './IngestionView';

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
    // Auto-open after instantiation to simulate connection
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

// Mock URL.createObjectURL and URL.revokeObjectURL
globalThis.URL.createObjectURL = vi.fn(() => 'blob:mock-url');
globalThis.URL.revokeObjectURL = vi.fn();

// Mock fetch globally
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;
globalThis.EventSource = MockEventSource as unknown as typeof EventSource;

describe('Ingestion Cockpit View & TerminalConsole', () => {
  beforeEach(() => {
    mockFetch.mockReset();
    MockEventSource.activeInstance = null;
  });

  afterEach(() => {
    cleanup();
  });

  it('renders initial idle view correctly', () => {
    render(<IngestionView />);
    
    expect(screen.getByText(/STATUS: IDLE/i)).toBeInTheDocument();
    expect(screen.getByText(/INITIATE REMOTE SCAN/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Drag and drop CSV fallback area/i)).toBeInTheDocument();
    expect(screen.getByText(/CONSOLE SUBSYSTEM/i)).toBeInTheDocument();
    expect(screen.getByText(/Terminal standing by/i)).toBeInTheDocument();
  });

  it('initiates remote scan and streams logs successfully', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ task_id: 'test-task-uuid-123' }),
    });

    render(<IngestionView />);

    // Click initiate scan
    const scanBtn = screen.getByText(/INITIATE REMOTE SCAN/i);
    fireEvent.click(scanBtn);

    expect(mockFetch).toHaveBeenCalledWith('/api/v1/ingest', expect.any(Object));

    // Wait for task_id resolution and EventSource instantiation
    await waitFor(() => {
      expect(MockEventSource.activeInstance).not.toBeNull();
    });

    // Verify state updates to scanning
    expect(screen.getByText(/STATUS: SCANNING/i)).toBeInTheDocument();

    // Trigger log event
    MockEventSource.activeInstance!.emit('task.log', {
      event: 'Scanner loaded Ashy parser module',
      level: 'INFO',
      timestamp: '2026-05-27T12:00:00Z',
    });

    // Check log is rendered in Terminal
    await screen.findByText(/Scanner loaded Ashy parser module/i);

    // Complete the task
    MockEventSource.activeInstance!.emit('task.completed', {
      status: 'success',
      imported_jobs: 5,
    });

    // Check status becomes completed
    await waitFor(() => {
      expect(screen.getByText(/STATUS: COMPLETED/i)).toBeInTheDocument();
    });
  });

  it('handles 3.0s connection timeout and displays timeout banner', async () => {
    vi.useFakeTimers();
    
    const originalEventSource = globalThis.EventSource;
    class LaggingEventSource {
      url: string;
      listeners: Record<string, ((event: { data: string }) => void)[]> = {};
      onopen: (() => void) | null = null;
      onerror: (() => void) | null = null;
      constructor(url: string) {
        this.url = url;
      }
      addEventListener(_event: string, _callback: (event: { data: string }) => void) {}
      removeEventListener(_event: string, _callback: (event: { data: string }) => void) {}
      close() {}
    }
    globalThis.EventSource = LaggingEventSource as unknown as typeof EventSource;

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ task_id: 'test-task-uuid-456' }),
    });

    render(<IngestionView />);

    // Click scan
    fireEvent.click(screen.getByText(/INITIATE REMOTE SCAN/i));

    // Resolve the initial fetch promise to trigger EventSource connection
    await vi.advanceTimersByTimeAsync(0);
    // Then advance another 3 seconds for the connection timeout
    await vi.advanceTimersByTimeAsync(3000);

    // Timeout banner should appear
    expect(screen.getByText(/\[TIMEOUT DETECTED - PARSER OFFLINE\]/i)).toBeInTheDocument();
    expect(screen.getByText(/STATUS: FAILED/i)).toBeInTheDocument();

    // Reset EventSource mock and timers
    globalThis.EventSource = originalEventSource;
    vi.useRealTimers();
  });

  it('triggers dragover styling and handles CSV upload file drops', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'success', imported_jobs: 3, skipped_jobs: 0 }),
    });

    render(<IngestionView />);

    const dropzone = screen.getByLabelText(/Drag and drop CSV fallback area/i);

    // Dragover triggers active state classes
    fireEvent.dragOver(dropzone);
    expect(dropzone.className).toContain('dropzoneActive');

    // DragLeave removes active state classes
    fireEvent.dragLeave(dropzone);
    expect(dropzone.className).not.toContain('dropzoneActive');

    // Create a mock file
    const file = new File(['url,title,company,raw_text\nhttps://url.com,dev,corp,text'], 'jobs.csv', { type: 'text/csv' });

    // Drop file
    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [file],
      },
    });

    // Check COMPILING HUD feedback state
    expect(screen.getByText(/\[COMPILING\.\.\.\]/i)).toBeInTheDocument();

    // Check SAVED HUD feedback state
    await waitFor(() => {
      expect(screen.getByText(/\[SAVED: Imported 3 jobs, Skipped 0\]/i)).toBeInTheDocument();
    });

    // Verify POST was made
    expect(mockFetch).toHaveBeenCalledWith('/api/v1/ingest/csv', expect.any(Object));
  });

  it('handles invalid file drop extensions with HUD error feedback', async () => {
    render(<IngestionView />);

    const dropzone = screen.getByLabelText(/Drag and drop CSV fallback area/i);
    const file = new File(['text content'], 'jobs.txt', { type: 'text/plain' });

    // Drop text file
    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [file],
      },
    });

    expect(screen.getByText(/\[SAVE_ERR: File must have \.csv extension\]/i)).toBeInTheDocument();
  });

  it('supports pause/resume buffering inside TerminalConsole', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ task_id: 'test-task-1' }),
    });

    render(<IngestionView />);

    fireEvent.click(screen.getByText(/INITIATE REMOTE SCAN/i));

    await waitFor(() => {
      expect(MockEventSource.activeInstance).not.toBeNull();
    });

    // Click PAUSE
    const pauseBtn = screen.getByRole('button', { name: /PAUSE/i });
    fireEvent.click(pauseBtn);

    // Send log while paused
    MockEventSource.activeInstance!.emit('task.log', {
      event: 'Log line 1 while paused',
      level: 'INFO',
      timestamp: '2026-05-27T12:00:00Z',
    });

    // Wait for the buffer count to update in the UI
    await waitFor(() => {
      expect(screen.getByText(/PAUSED - 1 IN BUFFER/i)).toBeInTheDocument();
    });

    // Verify log is NOT displayed on screen
    expect(screen.queryByText(/Log line 1 while paused/i)).not.toBeInTheDocument();

    // Click RESUME
    fireEvent.click(screen.getByRole('button', { name: /RESUME/i }));

    // Verify log is flushed and displayed
    await screen.findByText(/Log line 1 while paused/i);
  });

  it('allows downloading logs as a txt file', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ task_id: 'test-task-2' }),
    });

    render(<IngestionView />);

    fireEvent.click(screen.getByText(/INITIATE REMOTE SCAN/i));

    await waitFor(() => {
      expect(MockEventSource.activeInstance).not.toBeNull();
    });

    // Emit a log to make the download button enabled
    MockEventSource.activeInstance!.emit('task.log', {
      event: 'Logging message for download',
      level: 'INFO',
      timestamp: '2026-05-27T12:00:00Z',
    });

    // Wait for the log to be rendered, making the button enabled
    await screen.findByText(/Logging message for download/i);

    // Trigger download
    const downloadBtn = screen.getByRole('button', { name: /DOWNLOAD LOGS/i });
    
    // We mock click trigger
    const linkSpy = vi.spyOn(document.body, 'appendChild');
    fireEvent.click(downloadBtn);

    expect(linkSpy).toHaveBeenCalled();
    expect(globalThis.URL.createObjectURL).toHaveBeenCalled();
  });

  it('verifies accessibility features (aria-live, role)', () => {
    render(<IngestionView />);

    const logArea = screen.getByRole('log');
    expect(logArea).toBeInTheDocument();
    expect(logArea).toHaveAttribute('aria-live', 'polite');
  });
});
