import React from 'react';
import styles from './ConsolePanel.module.css';

interface ConsolePanelProps {
  title?: string;
  glowColor?: 'cyan' | 'purple' | 'magenta' | 'green';
  children: React.ReactNode;
  className?: string;
}

export const ConsolePanel: React.FC<ConsolePanelProps> = ({
  title,
  glowColor = 'cyan',
  children,
  className = '',
}) => {
  const glowClass = styles[glowColor] || styles.cyan;

  return (
    <section className={`${styles.hudPanel} ${glowClass} ${className}`}>
      {title && <h2 className={styles.panelTitle}>{title}</h2>}
      <div className={styles.panelContent}>
        {children}
      </div>
    </section>
  );
};
