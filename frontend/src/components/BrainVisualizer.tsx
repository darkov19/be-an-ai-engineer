import React, { useState, useEffect, useRef, useMemo } from 'react';
import styles from './BrainVisualizer.module.css';

interface Node3D {
  name: string;
  x: number;
  y: number;
  z: number;
}

const BASE_NODES: Node3D[] = [
  { name: 'pgvector', x: -35, y: 55, z: -25 },
  { name: 'RAG', x: -65, y: 15, z: 45 },
  { name: 'Agents', x: 65, y: 15, z: -45 },
  { name: 'Evals', x: 0, y: -45, z: 65 },
  { name: 'Python', x: -45, y: -25, z: -65 },
  { name: 'FastAPI', x: 45, y: -25, z: 45 },
  { name: 'LLMs', x: 0, y: -85, z: -15 },
  { name: 'MLOps', x: 35, y: 55, z: 25 },
];

const CONNECTIONS = [
  ['Python', 'FastAPI'],
  ['Python', 'LLMs'],
  ['Python', 'RAG'],
  ['FastAPI', 'Agents'],
  ['FastAPI', 'MLOps'],
  ['LLMs', 'RAG'],
  ['LLMs', 'Agents'],
  ['LLMs', 'Evals'],
  ['RAG', 'pgvector'],
  ['RAG', 'Evals'],
  ['Agents', 'MLOps'],
  ['Agents', 'pgvector'],
  ['Evals', 'MLOps'],
  ['pgvector', 'MLOps'],
];

interface BrainVisualizerProps {
  profileSkills: string[];
  skillGaps: string[];
  onResolveAnomaly?: (skill: string) => void;
  activeOrders?: string[];
}

export const BrainVisualizer: React.FC<BrainVisualizerProps> = ({
  profileSkills,
  skillGaps,
  onResolveAnomaly,
  activeOrders = [],
}) => {
  const [hoveredNode, setHoveredNode] = useState<{
    name: string;
    px: number;
    py: number;
    status: 'proven' | 'anomaly' | 'nominal';
    score: number;
  } | null>(null);
  const [isMobile, setIsMobile] = useState(false);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  
  const containerRef = useRef<HTMLDivElement>(null);

  // Check mobile width and prefers-reduced-motion
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);

    const hasMatchMedia = typeof window !== 'undefined' && typeof window.matchMedia === 'function';
    if (hasMatchMedia) {
      const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
      setPrefersReducedMotion(mediaQuery.matches);
      const handleMotionChange = (e: MediaQueryListEvent) => {
        setPrefersReducedMotion(e.matches);
      };
      mediaQuery.addEventListener('change', handleMotionChange);

      return () => {
        window.removeEventListener('resize', checkMobile);
        mediaQuery.removeEventListener('change', handleMotionChange);
      };
    }

    return () => {
      window.removeEventListener('resize', checkMobile);
    };
  }, []);

  // Map profile skills and anomalies to status
  const skillStatuses = useMemo(() => {
    const statuses: Record<string, 'proven' | 'anomaly' | 'nominal'> = {};
    const lowerProfile = profileSkills.map((s) => s.toLowerCase());
    const lowerGaps = skillGaps.map((s) => s.toLowerCase());

    BASE_NODES.forEach((node) => {
      const nameLower = node.name.toLowerCase();
      if (lowerProfile.includes(nameLower)) {
        statuses[node.name] = 'proven';
      } else if (lowerGaps.includes(nameLower)) {
        statuses[node.name] = 'anomaly';
      } else {
        statuses[node.name] = 'nominal';
      }
    });
    return statuses;
  }, [profileSkills, skillGaps]);

  // Mock similarity score or fit strength
  const getSkillDetails = (name: string) => {
    const status = skillStatuses[name];
    if (status === 'proven') return { score: 0.95, label: 'Proven Fit' };
    if (status === 'anomaly') return { score: 0.76, label: 'Market Gap' };
    return { score: 0.85, label: 'Nominal Strength' };
  };

  // 3D coordinate projection
  const projectedNodes = useMemo(() => {
    const width = 400;
    const height = 300;
    const cx = width / 2;
    const cy = height / 2;
    const D = 220; // Perspective distance

    // Keep the SVG projection stable; the visible rotation is handled by CSS rotateY().
    const currentAngle = 0.8;
    const cosA = Math.cos(currentAngle);
    const sinA = Math.sin(currentAngle);

    return BASE_NODES.map((node) => {
      // Y-axis rotation
      const rotX = node.x * cosA - node.z * sinA;
      const rotZ = node.x * sinA + node.z * cosA;
      const rotY = node.y;

      // Perspective projection
      const scale = D / (D + rotZ);
      const px = cx + rotX * scale * 1.3;
      const py = cy + rotY * scale * 1.3;

      return {
        ...node,
        px,
        py,
        scale,
        depth: rotZ, // Store depth for z-indexing
        status: skillStatuses[node.name] || 'nominal',
      };
    });
  }, [skillStatuses]);

  // Sort nodes by depth so that items in front overlap items in back
  const sortedNodes = useMemo(() => {
    return [...projectedNodes].sort((a, b) => b.depth - a.depth);
  }, [projectedNodes]);

  // Map nodes by name for fast lookup in connection rendering
  const nodeMap = useMemo(() => {
    const map: Record<string, typeof projectedNodes[0]> = {};
    projectedNodes.forEach((node) => {
      map[node.name] = node;
    });
    return map;
  }, [projectedNodes]);

  const handleNodeMouseEnter = (node: typeof projectedNodes[0]) => {
    const details = getSkillDetails(node.name);
    setHoveredNode({
      name: node.name,
      px: node.px,
      py: node.py,
      status: node.status,
      score: details.score,
    });
  };

  const resolveAnomaly = (skillName: string) => {
    if (!activeOrders.includes(skillName)) {
      onResolveAnomaly?.(skillName);
    }
  };

  return (
    <div className={styles.visualizerContainer} ref={containerRef}>
      {/* Visual background volumetric glow circle */}
      <div className={styles.volumetricGlow} />

      {/* Outer perspective wrapper */}
      <div className={`${styles.perspectiveWrapper} ${isMobile || prefersReducedMotion ? styles.staticMode : ''}`}>
        <div className={`${styles.preserve3dContainer} ${isMobile || prefersReducedMotion ? '' : styles.rotatingMesh}`}>
          <svg
            viewBox="0 0 400 300"
            className={styles.svgMesh}
            aria-label="Interactive 3D skill diagnostic mesh representing candidate skill profile status."
            role="img"
          >
            {/* Horizontal scan sweep bar */}
            {!isMobile && !prefersReducedMotion && (
              <rect x="0" y="0" width="400" height="300" className={styles.scanSweep} fill="url(#scanGrad)" />
            )}

            <defs>
              <linearGradient id="scanGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--glow-cyan)" stopOpacity="0" />
                <stop offset="50%" stopColor="var(--glow-cyan)" stopOpacity="0.08" />
                <stop offset="52%" stopColor="var(--glow-cyan)" stopOpacity="0.25" />
                <stop offset="54%" stopColor="var(--glow-cyan)" stopOpacity="0.08" />
                <stop offset="100%" stopColor="var(--glow-cyan)" stopOpacity="0" />
              </linearGradient>

              {/* Node glow filters */}
              <filter id="glowGreen" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
              <filter id="glowMagenta" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="4" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
              <filter id="glowCyan" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {/* Connection Lines */}
            {CONNECTIONS.map(([fromName, toName], idx) => {
              const fromNode = nodeMap[fromName];
              const toNode = nodeMap[toName];
              if (!fromNode || !toNode) return null;

              const isHighlighted = hoveredNode && (hoveredNode.name === fromName || hoveredNode.name === toName);
              const isConnectionAnomaly = fromNode.status === 'anomaly' || toNode.status === 'anomaly';

              let strokeColor = 'var(--border-hud)';
              let strokeOpacity = 0.15;
              let strokeWidth = 1.0;

              if (isHighlighted) {
                strokeColor = hoveredNode.status === 'anomaly' ? 'var(--glow-magenta)' : 'var(--glow-cyan)';
                strokeOpacity = 0.7;
                strokeWidth = 1.5;
              } else if (isConnectionAnomaly) {
                strokeColor = 'var(--glow-magenta)';
                strokeOpacity = 0.25;
              }

              return (
                <line
                  key={`line-${idx}`}
                  x1={fromNode.px}
                  y1={fromNode.py}
                  x2={toNode.px}
                  y2={toNode.py}
                  stroke={strokeColor}
                  strokeOpacity={strokeOpacity}
                  strokeWidth={strokeWidth}
                  className={styles.meshLine}
                />
              );
            })}

            {/* Skill Nodes */}
            {sortedNodes.map((node) => {
              const isHovered = hoveredNode && hoveredNode.name === node.name;
              const radius = (isHovered ? 8 : 5) * node.scale;

              let nodeClass = styles.nodeNominal;
              let filterUrl = '';
              let fillVal = 'hsl(240, 10%, 40%)';

              if (node.status === 'proven') {
                nodeClass = styles.nodeProven;
                filterUrl = 'url(#glowGreen)';
                fillVal = 'var(--glow-green)';
              } else if (node.status === 'anomaly') {
                nodeClass = styles.nodeAnomaly;
                filterUrl = 'url(#glowMagenta)';
                fillVal = 'var(--glow-magenta)';
              }

              return (
                <g
                  key={`node-${node.name}`}
                  className={`${styles.nodeGroup} ${nodeClass}`}
                  onMouseEnter={() => handleNodeMouseEnter(node)}
                  tabIndex={0}
                  role="button"
                  aria-label={`Skill: ${node.name}. Status: ${node.status}`}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      if (node.status === 'anomaly') {
                        resolveAnomaly(node.name);
                      } else {
                        handleNodeMouseEnter(node);
                      }
                    } else if (e.key === 'Escape') {
                      setHoveredNode(null);
                    }
                  }}
                >
                  {/* Outer pulse for anomalies */}
                  {node.status === 'anomaly' && (
                    <circle
                      cx={node.px}
                      cy={node.py}
                      r={radius * 2.2}
                      fill="none"
                      stroke="var(--glow-magenta)"
                      strokeWidth="1"
                      className={styles.pulseRing}
                    />
                  )}

                  {/* Primary Node Circle */}
                  <circle
                    cx={node.px}
                    cy={node.py}
                    r={radius}
                    fill={fillVal}
                    filter={filterUrl}
                    className={styles.nodeCircle}
                  />

                  {/* Node Label Text */}
                  <text
                    x={node.px}
                    y={node.py + radius + 14 * node.scale}
                    textAnchor="middle"
                    className={styles.nodeLabel}
                    style={{ fontSize: `${0.75 * node.scale}rem` }}
                  >
                    {node.name}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>

      {/* Floating Interactive Diagnostic Tooltip */}
      {hoveredNode && (
        <div
          className={styles.tooltip}
          style={{
            left: `${Math.min(300, Math.max(10, hoveredNode.px - 90))}px`,
            top: `${Math.min(200, Math.max(10, hoveredNode.py - 120))}px`,
          }}
          role="tooltip"
          aria-live="polite"
          onMouseLeave={() => setHoveredNode(null)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              setHoveredNode(null);
            }
          }}
        >
          <div className={styles.tooltipHeader}>
            <span className={styles.tooltipIndicator} data-status={hoveredNode.status} />
            <span className={styles.tooltipTitle}>{hoveredNode.name}</span>
          </div>
          <div className={styles.tooltipDetails}>
            <div className={styles.tooltipRow}>
              <span>PATHWAY STATUS:</span>
              <span className={styles.tooltipStatusText} data-status={hoveredNode.status}>
                {hoveredNode.status.toUpperCase()}
              </span>
            </div>
            <div className={styles.tooltipRow}>
              <span>MARKET MATCH FIT:</span>
              <span className={styles.tooltipValue}>
                {Math.round(hoveredNode.score * 100)}%
              </span>
            </div>
          </div>

          {hoveredNode.status === 'anomaly' && (
            <button
              onClick={() => {
                resolveAnomaly(hoveredNode.name);
              }}
              disabled={activeOrders.includes(hoveredNode.name)}
              className={styles.tooltipCta}
            >
              {activeOrders.includes(hoveredNode.name) ? '[ORDER ACTIVE]' : '[RESOLVE ANOMALY]'}
            </button>
          )}
        </div>
      )}

      {/* Visual Diagnostic Legend */}
      <div className={styles.legend}>
        <div className={styles.legendItem}>
          <span className={`${styles.legendDot} ${styles.dotProven}`} />
          <span>PROVEN</span>
        </div>
        <div className={styles.legendItem}>
          <span className={`${styles.legendDot} ${styles.dotNominal}`} />
          <span>NOMINAL</span>
        </div>
        <div className={styles.legendItem}>
          <span className={`${styles.legendDot} ${styles.dotAnomaly}`} />
          <span>ANOMALY</span>
        </div>
      </div>
    </div>
  );
};
