import React, { useState, useEffect, useRef } from 'react';
import styles from './TerminalConsole.module.css';

export interface LogEntry {
  event?: string;
  message?: string;
  level?: string;
  timestamp?: string;
  [key: string]: unknown;
}

interface TerminalConsoleProps {
  logs: LogEntry[];
  taskId?: string;
}

export const TerminalConsole: React.FC<TerminalConsoleProps> = ({ logs, taskId }) => {
  const [displayedLogs, setDisplayedLogs] = useState<LogEntry[]>([]);
  const [buffer, setBuffer] = useState<LogEntry[]>([]);
  const [isPaused, setIsPaused] = useState(false);
  const [scrollLock, setScrollLock] = useState(true);

  const logAreaRef = useRef<HTMLDivElement>(null);

  // Sync logs when parent changes, respecting Pause state
  useEffect(() => {
    if (logs.length === 0) {
      setDisplayedLogs([]);
      setBuffer([]);
      return;
    }

    const processedCount = displayedLogs.length + buffer.length;
    if (logs.length > processedCount) {
      const newLogs = logs.slice(processedCount);
      if (isPaused) {
        setBuffer((prev) => [...prev, ...newLogs]);
      } else {
        setDisplayedLogs((prev) => [...prev, ...newLogs]);
      }
    }
  }, [logs, isPaused, displayedLogs.length, buffer.length]);

  // Scroll to bottom if scroll lock is active and logs change
  useEffect(() => {
    if (scrollLock && logAreaRef.current) {
      logAreaRef.current.scrollTop = logAreaRef.current.scrollHeight;
    }
  }, [displayedLogs, scrollLock]);

  const togglePause = () => {
    if (isPaused) {
      // Flushing buffer
      setDisplayedLogs((prev) => [...prev, ...buffer]);
      setBuffer([]);
    }
    setIsPaused(!isPaused);
  };

  const downloadLogs = () => {
    const textContent = displayedLogs
      .map((log) => {
        const time = log.timestamp || new Date().toISOString();
        const lvl = (log.level || 'INFO').toUpperCase();
        const msg = log.event || log.message || JSON.stringify(log);
        return `[${time}] [${lvl}] ${msg}`;
      })
      .join('\n');

    const blob = new Blob([textContent], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `task-logs-${taskId || 'export'}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const getRowClass = (log: LogEntry) => {
    const level = (log.level || '').toUpperCase();
    const text = (log.event || log.message || '').toUpperCase();

    if (
      level === 'INFO' ||
      level === 'SUCCESS' ||
      text.includes('[INFO]') ||
      text.includes('INFO:') ||
      text.includes('INFO ')
    ) {
      return styles.logInfo;
    }
    if (
      level === 'WARN' ||
      level === 'WARNING' ||
      text.includes('[WARN]') ||
      text.includes('[WARNING]') ||
      text.includes('WARN:') ||
      text.includes('WARNING:')
    ) {
      return styles.logWarn;
    }
    if (
      level === 'ERROR' ||
      level === 'FAIL' ||
      level === 'FATAL' ||
      text.includes('[ERROR]') ||
      text.includes('[FAIL]') ||
      text.includes('[FATAL]') ||
      text.includes('ERROR:') ||
      text.includes('FAIL:') ||
      text.includes('FATAL:')
    ) {
      return styles.logError;
    }
    if (level === 'SYS' || text.includes('[SYS]')) {
      return styles.logSys;
    }
    return styles.logDefault;
  };

  const formatLogText = (log: LogEntry) => {
    const time = log.timestamp ? `[${log.timestamp.split('T')[1]?.slice(0, 8) || log.timestamp}] ` : '';
    const lvl = log.level ? `[${log.level.toUpperCase()}] ` : '';
    const msg = log.event || log.message || JSON.stringify(log);
    return `${time}${lvl}${msg}`;
  };

  return (
    <div className={styles.terminalContainer}>
      <div className={styles.controlBar}>
        <div className={styles.statusInfo}>
          <span>CONSOLE SUBSYSTEM</span>
          {isPaused && (
            <span className={styles.bufferIndicator} aria-live="polite">
              &nbsp;[PAUSED - {buffer.length} IN BUFFER]
            </span>
          )}
        </div>
        <div className={styles.controls}>
          <label className={styles.lockLabel}>
            <input
              type="checkbox"
              checked={scrollLock}
              onChange={(e) => setScrollLock(e.target.checked)}
              className={styles.lockCheckbox}
            />
            AUTO-SCROLL
          </label>
          <button
            onClick={togglePause}
            className={`${styles.btn} ${isPaused ? styles.btnPauseActive : ''}`}
            title={isPaused ? 'Resume stream updates' : 'Pause stream updates'}
          >
            {isPaused ? 'RESUME' : 'PAUSE'}
          </button>
          <button
            onClick={downloadLogs}
            disabled={displayedLogs.length === 0}
            className={styles.btn}
            title="Download terminal logs"
          >
            DOWNLOAD LOGS
          </button>
        </div>
      </div>
      <div
        className={styles.logArea}
        ref={logAreaRef}
        aria-live="polite"
        role="log"
      >
        {displayedLogs.map((log, idx) => (
          <div key={idx} className={`${styles.logRow} ${getRowClass(log)}`}>
            {formatLogText(log)}
          </div>
        ))}
        {displayedLogs.length === 0 && (
          <div className={`${styles.logRow} ${styles.logSys}`}>
            [SYS] Terminal standing by. Awaiting log stream events...
          </div>
        )}
      </div>
    </div>
  );
};
