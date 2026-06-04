import React, { useState, useEffect, useRef } from 'react';
import styles from './TelemetryChart.module.css';

interface TelemetryChartProps {
  status?: 'active' | 'nominal' | 'inactive';
  telemetryPoints?: number[];
  height?: number;
  width?: number;
}

export const TelemetryChart: React.FC<TelemetryChartProps> = ({
  status = 'nominal',
  telemetryPoints = [],
  height = 120,
  width = 500,
}) => {
  const [timeShift, setTimeShift] = useState(0);
  const [currentVal, setCurrentVal] = useState(0);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  const requestRef = useRef<number | null>(null);
  const previousTimeRef = useRef<number | null>(null);

  useEffect(() => {
    const hasMatchMedia = typeof window !== 'undefined' && typeof window.matchMedia === 'function';
    let mediaQuery: MediaQueryList | null = null;
    let handleChange: ((e: MediaQueryListEvent) => void) | null = null;

    if (hasMatchMedia) {
      mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
      setPrefersReducedMotion(mediaQuery.matches);
      handleChange = (e: MediaQueryListEvent) => {
        setPrefersReducedMotion(e.matches);
      };
      mediaQuery.addEventListener('change', handleChange);
    }

    return () => {
      if (mediaQuery && handleChange) {
        mediaQuery.removeEventListener('change', handleChange);
      }
    };
  }, []);

  // Animation frame loop for panning the ECG waveform
  useEffect(() => {
    previousTimeRef.current = null;
    if (prefersReducedMotion) {
      if (requestRef.current) {
        cancelAnimationFrame(requestRef.current);
        requestRef.current = null;
      }
      return;
    }

    const animate = (time: number) => {
      if (previousTimeRef.current !== null) {
        const delta = time - previousTimeRef.current;
        // Shift speed depends on status
        const speed = status === 'active' ? 0.12 : status === 'nominal' ? 0.08 : 0.04;
        setTimeShift((prev) => (prev + delta * speed) % 10000);
      }
      previousTimeRef.current = time;
      requestRef.current = requestAnimationFrame(animate);
    };

    requestRef.current = requestAnimationFrame(animate);
    return () => {
      if (requestRef.current) {
        cancelAnimationFrame(requestRef.current);
      }
    };
  }, [status, prefersReducedMotion]);

  // Generate ECG waveform path
  const pathD = React.useMemo(() => {
    const points = [];
    const midY = height / 2;
    const pointsCount = 60;
    
    const normalizedTelemetry = telemetryPoints.length > 0
      ? telemetryPoints
      : Array.from({ length: pointsCount + 1 }, (_, index) => {
          const period = status === 'active' ? 120 : 160;
          const x = (index / pointsCount) * width;
          const pos = prefersReducedMotion ? x % period : (x + timeShift) % period;
          if (status === 'inactive') return 0;
          if (pos > 15 && pos < 30) return status === 'active' ? 18 : 9;
          if (pos >= 33 && pos < 39) return status === 'active' ? 100 : 62;
          if (pos >= 55 && pos < 75) return status === 'active' ? 31 : 18;
          return 2;
        });
    const maxTelemetry = Math.max(...normalizedTelemetry, 1);

    for (let i = 0; i <= pointsCount; i++) {
      const x = (i / pointsCount) * width;
      let y = midY;

      if (status === 'inactive') {
        y = midY;
      } else {
        const sampleIndex = Math.min(
          normalizedTelemetry.length - 1,
          Math.round((i / pointsCount) * (normalizedTelemetry.length - 1))
        );
        const normalizedValue = normalizedTelemetry[sampleIndex] / maxTelemetry;
        const amplitude = status === 'active' ? 48 : 30;
        const baselineNoise = prefersReducedMotion ? 0 : Math.sin(x * 0.8 + timeShift * 0.2) * 0.4;
        y = midY - normalizedValue * amplitude + baselineNoise;
      }

      points.push({ x, y });
    }

    // Generate Bezier path
    let d = `M ${points[0].x} ${points[0].y}`;
    for (let i = 0; i < points.length - 1; i++) {
      const p0 = points[i];
      const p1 = points[i + 1];
      const cpX = (p0.x + p1.x) / 2;
      d += ` Q ${cpX} ${p0.y}, ${p1.x} ${p1.y}`;
    }
    return d;
  }, [width, height, timeShift, status, telemetryPoints, prefersReducedMotion]);

  // Update current readout values dynamically to match wave amplitude
  useEffect(() => {
    const telemetryPeak = Math.max(...telemetryPoints, 0);
    const nextValue = status === 'inactive'
      ? 0
      : Math.round(telemetryPeak || (status === 'active' ? 118 : 68));
    if (prefersReducedMotion) {
      setCurrentVal(nextValue);
      return;
    }

    const timer = setInterval(() => {
      if (status === 'inactive') {
        setCurrentVal(0);
      } else if (status === 'nominal') {
        setCurrentVal(nextValue + Math.round(Math.sin(Date.now() / 400) * 4));
      } else {
        setCurrentVal(nextValue + Math.round(Math.sin(Date.now() / 280) * 8));
      }
    }, 400);
    return () => clearInterval(timer);
  }, [status, telemetryPoints, prefersReducedMotion]);

  let statusText = 'NOMINAL';
  let strokeColor = 'var(--glow-green)';
  let glowStyle = styles.glowGreen;

  if (status === 'active') {
    statusText = 'INGESTING / ACTIVE';
    strokeColor = 'var(--glow-cyan)';
    glowStyle = styles.glowCyan;
  } else if (status === 'inactive') {
    statusText = 'FLATLINE / INACTIVE';
    strokeColor = 'var(--glow-magenta)';
    glowStyle = styles.glowMagenta;
  }

  return (
    <div className={styles.chartContainer}>
      <div className={styles.header}>
        <div className={styles.titleGroup}>
          <span className={styles.tag}>TELEMETRY CHANNEL 01</span>
          <h3 className={styles.title}>HEMODYNAMIC LEARNING WAVE</h3>
        </div>
        <div className={styles.statusDisplay}>
          <span className={styles.statusLabel}>STATUS:</span>
          <span className={`${styles.statusVal} ${
            status === 'active' ? styles.cyanText : status === 'inactive' ? styles.magentaText : styles.greenText
          }`}>
            {statusText}
          </span>
        </div>
      </div>

      <div className={styles.svgWrapper}>
        {/* Panning grid background overlay */}
        <div className={styles.panningGrid} />

        <svg
          viewBox={`0 0 ${width} ${height}`}
          className={styles.svgElement}
          aria-label="ECG wave telemetry showing active ingestion runs and commit pushes."
          role="img"
        >
          <defs>
            <filter id="ecgGlowGreen" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="ecgGlowCyan" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="ecgGlowMagenta" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Core Waveform Path */}
          <path
            d={pathD}
            fill="none"
            stroke={strokeColor}
            strokeWidth="1.8"
            filter={
              status === 'active'
                ? 'url(#ecgGlowCyan)'
                : status === 'inactive'
                ? 'url(#ecgGlowMagenta)'
                : 'url(#ecgGlowGreen)'
            }
            className={`${styles.wavePath} ${glowStyle}`}
          />
        </svg>
      </div>

      <div className={styles.footer}>
        <div className={styles.metaItem}>
          <span className={styles.metaLabel}>RATE:</span>
          <span className={styles.metaValMono}>{currentVal} CPS</span>
        </div>
        <div className={styles.metaItem}>
          <span className={styles.metaLabel}>SYNC:</span>
          <span className={styles.metaValMono}>100% SECURE</span>
        </div>
        <div className={styles.metaItem}>
          <span className={styles.metaLabel}>BANDWIDTH:</span>
          <span className={styles.metaValMono}>
            {status === 'active' ? '8.4 KB/S' : status === 'nominal' ? '3.2 KB/S' : '0.0 KB/S'}
          </span>
        </div>
      </div>
    </div>
  );
};
