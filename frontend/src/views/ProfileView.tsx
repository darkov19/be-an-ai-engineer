import React from 'react';
import { ConsolePanel } from '../components/ConsolePanel';
import styles from './Views.module.css';

export const ProfileView: React.FC = () => {
  return (
    <div className={styles.viewGrid}>
      <ConsolePanel title="ENGINEER PROFILE" glowColor="cyan">
        <div className={styles.profileDetails}>
          <div className={styles.profileHeader}>
            <span className={styles.profileAvatar}>▲</span>
            <div>
              <h3 className={styles.profileName}>DARKO</h3>
              <span className={styles.profileRole}>COGNITIVE COCKPIT OPERATOR</span>
            </div>
          </div>
          <div className={styles.profileInfoList}>
            <div className={styles.infoRow}>
              <span className={styles.infoLabel}>SYSTEM AUTHORITY:</span>
              <span className={styles.infoValue}>LEVEL_A_DEV</span>
            </div>
            <div className={styles.infoRow}>
              <span className={styles.infoLabel}>OPERATING SYSTEM:</span>
              <span className={styles.infoValue}>LINUX</span>
            </div>
          </div>
        </div>
      </ConsolePanel>
      <ConsolePanel title="MEMORANDUM" glowColor="purple">
        <p className={styles.statusDescription}>
          Cockpit customization variables saved. Standby for candidate profile management sync.
        </p>
      </ConsolePanel>
    </div>
  );
};
