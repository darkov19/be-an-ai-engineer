import React, { useState, useRef, useEffect } from 'react';
import { ConsolePanel } from '../components/ConsolePanel';
import { TerminalConsole, LogEntry } from '../components/TerminalConsole';
import viewStyles from './IngestionView.module.css';

type ScanState = 'idle' | 'scanning' | 'completed' | 'failed';

export const IngestionView: React.FC = () => {
  const [scanState, setScanState] = useState<ScanState>('idle');
  const [showTimeoutBanner, setShowTimeoutBanner] = useState(false);
  const [companySlug, setCompanySlug] = useState<string>('stripe');
  const [hudFeedback, setHudFeedback] = useState<string>('');
  const [hudState, setHudState] = useState<'idle' | 'compiling' | 'saved' | 'error'>('idle');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [taskId, setTaskId] = useState<string>('');
  const [isDragActive, setIsDragActive] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const activeEsRef = useRef<EventSource | null>(null);

  // Cleanup EventSource on unmount
  useEffect(() => {
    return () => {
      if (activeEsRef.current) {
        activeEsRef.current.close();
      }
    };
  }, []);

  const connectSSE = (tid: string, timeoutTimerId: number | ReturnType<typeof setTimeout>) => {
    const es = new EventSource(`/api/v1/tasks/${tid}/logs/stream`);

    es.onopen = () => {
      // Clear timeout since connection is successfully established!
      clearTimeout(timeoutTimerId);
      setScanState('scanning');
      setShowTimeoutBanner(false);
    };

    es.addEventListener('task.started', (e) => {
      clearTimeout(timeoutTimerId);
      setScanState('scanning');
      setShowTimeoutBanner(false);
      try {
        JSON.parse(e.data);
        setLogs((prev) => [
          ...prev,
          {
            event: 'Remote scan initialization sequence started.',
            level: 'sys',
            timestamp: new Date().toISOString(),
          },
        ]);
      } catch (err) {
        // Fallback
      }
    });

    es.addEventListener('task.log', (e) => {
      try {
        const data = JSON.parse(e.data);
        setLogs((prev) => [...prev, data]);
      } catch (err) {
        console.error(err);
      }
    });

    es.addEventListener('task.completed', (e) => {
      try {
        const summary = JSON.parse(e.data);
        setLogs((prev) => [
          ...prev,
          {
            event: `Scan completed successfully. Result summary: ${JSON.stringify(summary)}`,
            level: 'success',
            timestamp: new Date().toISOString(),
          },
        ]);
        setScanState('completed');
        es.close();
        activeEsRef.current = null;
      } catch (err) {
        setScanState('failed');
        es.close();
        activeEsRef.current = null;
      }
    });

    es.addEventListener('task.failed', (e) => {
      try {
        const errObj = JSON.parse(e.data);
        setLogs((prev) => [
          ...prev,
          {
            event: `Parser execution failed: ${errObj.error}`,
            level: 'error',
            timestamp: new Date().toISOString(),
          },
        ]);
        setScanState('failed');
        es.close();
        activeEsRef.current = null;
      } catch (err) {
        setScanState('failed');
        es.close();
        activeEsRef.current = null;
      }
    });

    es.onerror = (err) => {
      console.warn('EventSource encountered an error:', err);
      // Fail state transition and display timeout/offline banner on stream disconnect
      setScanState('failed');
      setShowTimeoutBanner(true);
      es.close();
      activeEsRef.current = null;
      setLogs((prev) => [
        ...prev,
        {
          event: '[STREAM DISCONNECTED] Log stream connection lost or failed to connect.',
          level: 'error',
          timestamp: new Date().toISOString(),
        },
      ]);
    };

    return es;
  };

  const startRemoteScan = async () => {
    setScanState('scanning');
    setLogs([]);
    setTaskId('');
    setShowTimeoutBanner(false);

    const controller = new AbortController();
    let hasTimedOut = false;

    // Setup 3-second timeout timer
    const timerId = setTimeout(() => {
      hasTimedOut = true;
      controller.abort();
      setScanState('failed');
      setShowTimeoutBanner(true);
      if (activeEsRef.current) {
        activeEsRef.current.close();
        activeEsRef.current = null;
      }
      setLogs((prev) => [
        ...prev,
        {
          event: '[TIMEOUT DETECTED - PARSER OFFLINE] Log stream failed to establish in 3.0s.',
          level: 'error',
          timestamp: new Date().toISOString(),
        },
      ]);
    }, 3000);

    try {
      const res = await fetch('/api/v1/ingest', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ company_slug: companySlug.trim() || undefined }),
        signal: controller.signal,
      });

      if (!res.ok) {
        throw new Error(`HTTP error status: ${res.status}`);
      }

      const data = await res.json();
      const tid = data.task_id;

      if (hasTimedOut) {
        return;
      }

      setTaskId(tid);

      const es = connectSSE(tid, timerId);
      activeEsRef.current = es;
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return;
      }
      clearTimeout(timerId);
      setScanState('failed');
      setShowTimeoutBanner(true);
      setLogs((prev) => [
        ...prev,
        {
          event: `Scan initialization failed: ${err instanceof Error ? err.message : String(err)}`,
          level: 'error',
          timestamp: new Date().toISOString(),
        },
      ]);
    }
  };

  // Drag and Drop Handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragActive(true);
  };

  const handleDragLeave = () => {
    setIsDragActive(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragActive(false);

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      const file = files[0];
      await uploadCSVFile(file);
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      const file = files[0];
      await uploadCSVFile(file);
      e.target.value = '';
    }
  };

  const uploadCSVFile = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setHudState('error');
      setHudFeedback('[SAVE_ERR: File must have .csv extension]');
      return;
    }

    setHudState('compiling');
    setHudFeedback('[COMPILING...]');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/v1/ingest/csv', {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();

      if (res.ok && data.status === 'success') {
        setHudState('saved');
        setHudFeedback(`[SAVED: Imported ${data.imported_jobs} jobs, Skipped ${data.skipped_jobs}]`);
      } else {
        setHudState('error');
        setHudFeedback(`[SAVE_ERR: ${data.detail || data.code || 'Upload failed'}]`);
      }
    } catch (err) {
      setHudState('error');
      setHudFeedback(`[SAVE_ERR: ${err instanceof Error ? err.message : String(err)}]`);
    }
  };

  const triggerFileSelect = () => {
    fileInputRef.current?.click();
  };

  const dismissBanner = () => {
    setShowTimeoutBanner(false);
  };

  const loadOfflineFallback = async () => {
    const rawSlug = companySlug.trim().toLowerCase();
    const slug = /^[a-z0-9-]+$/.test(rawSlug) ? rawSlug : 'stripe';
    const cachedPath = `/cached-fingerprints/${encodeURIComponent(slug)}.html?demo=true`;

    try {
      const res = await fetch(`/cached-fingerprints/${encodeURIComponent(slug)}.html`, { method: 'HEAD' });
      window.location.href = res.ok ? cachedPath : `/company/${encodeURIComponent(slug)}?demo=true`;
    } catch {
      window.location.href = `/company/${encodeURIComponent(slug)}?demo=true`;
    }
  };

  const getLedClass = () => {
    switch (scanState) {
      case 'scanning':
        return viewStyles.ledScanning;
      case 'completed':
        return viewStyles.ledCompleted;
      case 'failed':
        return viewStyles.ledFailed;
      default:
        return viewStyles.ledIdle;
    }
  };

  const getHudClass = () => {
    switch (hudState) {
      case 'compiling':
        return viewStyles.feedbackCompiling;
      case 'saved':
        return viewStyles.feedbackSaved;
      case 'error':
        return viewStyles.feedbackError;
      default:
        return '';
    }
  };

  return (
    <div className={viewStyles.viewGrid}>
      <div>
        {showTimeoutBanner && (
          <div className={viewStyles.timeoutBanner} role="alert">
            <span>[TIMEOUT DETECTED - PARSER OFFLINE]</span>
            <div className={viewStyles.bannerControls}>
              <button
                onClick={loadOfflineFallback}
                className={viewStyles.btnBanner}
              >
                [LOAD OFFLINE FALLBACK CACHE]
              </button>
              <button onClick={startRemoteScan} className={viewStyles.btnBanner}>
                RETRY
              </button>
              <button
                onClick={dismissBanner}
                className={`${viewStyles.btnBanner} ${viewStyles.btnBannerSecondary}`}
              >
                DISMISS
              </button>
            </div>
          </div>
        )}

        <ConsolePanel title="INGESTION COCKPIT" glowColor="cyan">
          <div className={viewStyles.scanSection}>
            <div className={viewStyles.targetCompanySelector}>
              <label htmlFor="company-slug-input" className={viewStyles.companyLabel}>TARGET COMPANY SLUG:</label>
              <input
                id="company-slug-input"
                type="text"
                value={companySlug}
                onChange={(e) => setCompanySlug(e.target.value)}
                placeholder="e.g. stripe"
                className={viewStyles.companyInput}
                disabled={scanState === 'scanning'}
              />
            </div>

            <div className={viewStyles.cockpitHeader}>
              <div className={viewStyles.ledContainer}>
                <span className={`${viewStyles.led} ${getLedClass()}`} />
                <span>STATUS: {scanState.toUpperCase()}</span>
              </div>
              {scanState === 'scanning' && (
                <span className={viewStyles.scanningIndicator}>SCAN ACTIVE</span>
              )}
            </div>

            <div className={viewStyles.scanControls}>
              <button
                onClick={startRemoteScan}
                disabled={scanState === 'scanning'}
                className={viewStyles.btnScan}
              >
                INITIATE REMOTE SCAN
              </button>
              {scanState === 'scanning' && (
                <div className={viewStyles.progressContainer}>
                  <div className={`${viewStyles.progressBar} ${viewStyles.progressBarScanning}`} />
                  <span className={viewStyles.progressText}>POLLING SSE STREAM...</span>
                </div>
              )}
            </div>
          </div>
        </ConsolePanel>

        <div className={viewStyles.fallbackSection}>
          <h3 className={viewStyles.fallbackTitle}>FALLBACK INGESTION CHANNEL</h3>
          <div
            className={`${viewStyles.dropzone} ${isDragActive ? viewStyles.dropzoneActive : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={triggerFileSelect}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                triggerFileSelect();
              }
            }}
            aria-label="Drag and drop CSV fallback area"
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              className={viewStyles.fileInput}
              accept=".csv"
            />
            <span className={viewStyles.dropIcon}>📂</span>
            <span className={viewStyles.dropTextPrimary}>
              Drag and drop job listings `.csv` file here
            </span>
            <span className={viewStyles.dropTextSecondary}>
              or click to browse local filesystem (Max 5MB)
            </span>
          </div>

          {hudFeedback && (
            <div className={viewStyles.hudFeedbackContainer}>
              <span className={viewStyles.hudFeedbackLabel}>HUD_FEEDBACK:</span>
              <span className={`${viewStyles.hudFeedbackValue} ${getHudClass()}`} aria-live="polite">
                {hudFeedback}
              </span>
            </div>
          )}
        </div>
      </div>

      <ConsolePanel title="PARSING TELEMETRY STREAM" glowColor="purple">
        <TerminalConsole logs={logs} taskId={taskId} />
      </ConsolePanel>
    </div>
  );
};
