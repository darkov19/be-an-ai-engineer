import React, { useState, useEffect, useRef } from 'react';
import { ConsolePanel } from '../components/ConsolePanel';
import styles from './ProfileView.module.css';
import viewStyles from './Views.module.css';

export const ProfileView: React.FC = () => {
  const [skillsInput, setSkillsInput] = useState('');
  const [techStackInput, setTechStackInput] = useState('');
  const [seniority, setSeniority] = useState('');
  const [yearsOfExperience, setYearsOfExperience] = useState<number>(0);
  const [geoPreference, setGeoPreference] = useState('');
  
  const [isLoaded, setIsLoaded] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeRequestRef = useRef<AbortController | null>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const latestValuesRef = useRef({
    skills: '',
    techStack: '',
    seniority: '',
    yearsOfExperience: 0,
    geoPreference: '',
  });

  // Load profile data on mount
  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const res = await fetch('/api/v1/profiles/current');
        if (res.ok) {
          const data = await res.json();
          const skillsStr = (data.skills || []).join(', ');
          const techStackStr = (data.tech_stack || []).join(', ');
          const yrs = data.years_of_experience || 0;
          const sen = data.seniority || '';
          const geo = data.geo_preference || '';

          setSkillsInput(skillsStr);
          setTechStackInput(techStackStr);
          setSeniority(sen);
          setYearsOfExperience(yrs);
          setGeoPreference(geo);
          setLastUpdated(data.updated_at);
          
          latestValuesRef.current = {
            skills: skillsStr,
            techStack: techStackStr,
            seniority: sen,
            yearsOfExperience: yrs,
            geoPreference: geo,
          };
          
          setIsLoaded(true);
        }
      } catch (err) {
        console.error('Failed to fetch profile:', err);
      }
    };

    fetchProfile();
  }, []);

  // Flush pending save on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
        
        // Immediate synchronous-like fetch flush (does not wait for state updates)
        const valuesToSave = latestValuesRef.current;
        const cleanList = (str: string): string[] => 
          str.split(',').map(s => s.trim()).filter(s => s.length > 0);

        const payload = {
          skills: cleanList(valuesToSave.skills),
          tech_stack: cleanList(valuesToSave.techStack),
          seniority: valuesToSave.seniority || null,
          years_of_experience: Number(valuesToSave.yearsOfExperience),
          geo_preference: valuesToSave.geoPreference || null,
        };

        fetch('/api/v1/profiles/current', {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
          keepalive: true,
        }).catch(err => {
          console.error('Failed to flush save on unmount:', err);
        });
      }
    };
  }, []);

  // Primary API Save Logic
  const saveProfile = async (valuesToSave = latestValuesRef.current) => {
    const cleanList = (str: string): string[] => 
      str.split(',').map(s => s.trim()).filter(s => s.length > 0);

    const payload = {
      skills: cleanList(valuesToSave.skills),
      tech_stack: cleanList(valuesToSave.techStack),
      seniority: valuesToSave.seniority || null,
      years_of_experience: Number(valuesToSave.yearsOfExperience),
      geo_preference: valuesToSave.geoPreference || null,
    };

    // Abort any existing in-flight save request
    if (activeRequestRef.current) {
      activeRequestRef.current.abort();
    }
    const controller = new AbortController();
    activeRequestRef.current = controller;

    try {
      const res = await fetch('/api/v1/profiles/current', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      const data = await res.json();
      if (!res.ok || data.error) {
        setSaveStatus('error');
        setErrorMessage(data.detail || 'Failed to save profile parameters.');
      } else {
        setSaveStatus('saved');
        setLastUpdated(data.updated_at);
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        // Silently ignore aborted requests
        return;
      }
      const msg = err instanceof Error ? err.message : 'Network/Server connection failure.';
      setSaveStatus('error');
      setErrorMessage(msg);
    } finally {
      if (activeRequestRef.current === controller) {
        activeRequestRef.current = null;
      }
    }
  };

  // Debounce Trigger Setup
  const triggerSave = (newValues: typeof latestValuesRef.current) => {
    if (!isLoaded) return;
    
    setSaveStatus('saving');
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      saveProfile(newValues);
    }, 250);
  };

  // Keyboard shortcut blocker for Alt+1 to Alt+5 when form fields are focused, registered in capture phase
  useEffect(() => {
    const form = formRef.current;
    if (!form) return;

    const handleKeyDownCapture = (e: KeyboardEvent) => {
      const digitMatch = e.code.match(/^Digit([1-5])$/);
      if (e.altKey && digitMatch) {
        // Stop propagation in the capture phase so that window-level listeners do not intercept it
        e.stopPropagation();
      }
    };

    form.addEventListener('keydown', handleKeyDownCapture, { capture: true });
    return () => {
      form.removeEventListener('keydown', handleKeyDownCapture, { capture: true });
    };
  }, []);

  // Individual Form Change Handlers
  const handleSkillsChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setSkillsInput(val);
    const nextValues = { ...latestValuesRef.current, skills: val };
    latestValuesRef.current = nextValues;
    triggerSave(nextValues);
  };

  const handleTechStackChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setTechStackInput(val);
    const nextValues = { ...latestValuesRef.current, techStack: val };
    latestValuesRef.current = nextValues;
    triggerSave(nextValues);
  };

  const handleSeniorityChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    setSeniority(val);
    const nextValues = { ...latestValuesRef.current, seniority: val };
    latestValuesRef.current = nextValues;
    triggerSave(nextValues);
  };

  const handleYearsChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = Math.max(0, parseInt(e.target.value) || 0);
    setYearsOfExperience(val);
    const nextValues = { ...latestValuesRef.current, yearsOfExperience: val };
    latestValuesRef.current = nextValues;
    triggerSave(nextValues);
  };

  const handleGeoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setGeoPreference(val);
    const nextValues = { ...latestValuesRef.current, geoPreference: val };
    latestValuesRef.current = nextValues;
    triggerSave(nextValues);
  };

  const isError = saveStatus === 'error';

  return (
    <div className={viewStyles.viewGrid}>
      <ConsolePanel title="EDIT ENGINEER PROFILE" glowColor={isError ? 'magenta' : 'cyan'}>
        <form ref={formRef} className={styles.profileForm} onSubmit={(e) => e.preventDefault()}>
          <div className={styles.formGrid}>
            <div className={`${styles.inputGroup} ${styles.fullWidth}`}>
              <label htmlFor="skills-input" className={styles.label}>Skills (Comma-separated)</label>
              <input
                id="skills-input"
                type="text"
                className={`${styles.input} ${isError ? styles.inputError : ''}`}
                value={skillsInput}
                onChange={handleSkillsChange}
                placeholder="e.g. React, TypeScript, Python, Docker"
              />
              <span className={styles.helpText}>Enter skills that describe your overall software capabilities.</span>
            </div>

            <div className={`${styles.inputGroup} ${styles.fullWidth}`}>
              <label htmlFor="tech-stack-input" className={styles.label}>Tech Stack (Comma-separated)</label>
              <input
                id="tech-stack-input"
                type="text"
                className={`${styles.input} ${isError ? styles.inputError : ''}`}
                value={techStackInput}
                onChange={handleTechStackChange}
                placeholder="e.g. FastAPI, PostgreSQL, TailwindCSS"
              />
              <span className={styles.helpText}>Enter specific technologies and frameworks in your active stack.</span>
            </div>

            <div className={styles.inputGroup}>
              <label htmlFor="seniority-select" className={styles.label}>Seniority Level</label>
              <select
                id="seniority-select"
                className={`${styles.select} ${isError ? styles.inputError : ''}`}
                value={seniority}
                onChange={handleSeniorityChange}
              >
                <option value="">Select Level</option>
                <option value="Junior">Junior Developer</option>
                <option value="Mid">Mid Level Developer</option>
                <option value="Senior">Senior Developer</option>
                <option value="Lead">Lead Engineer</option>
                <option value="Principal">Principal Architect</option>
              </select>
            </div>

            <div className={styles.inputGroup}>
              <label htmlFor="years-experience-input" className={styles.label}>Years of Experience</label>
              <input
                id="years-experience-input"
                type="number"
                min="0"
                className={`${styles.input} ${isError ? styles.inputError : ''}`}
                value={yearsOfExperience}
                onChange={handleYearsChange}
              />
            </div>

            <div className={`${styles.inputGroup} ${styles.fullWidth}`}>
              <label htmlFor="geo-pref-input" className={styles.label}>Geographical Preference</label>
              <input
                id="geo-pref-input"
                type="text"
                className={`${styles.input} ${isError ? styles.inputError : ''}`}
                value={geoPreference}
                onChange={handleGeoChange}
                placeholder="e.g. Remote, Berlin, New York"
              />
            </div>
          </div>

          <div className={styles.statusContainer}>
            {saveStatus === 'saving' && (
              <span className={styles.indicatorCompiling}>[COMPILING...]</span>
            )}
            {saveStatus === 'saved' && (
              <span className={styles.indicatorSaved}>[SAVED]</span>
            )}
            {saveStatus === 'error' && (
              <span className={styles.indicatorError}>[SAVE_ERR: {errorMessage}]</span>
            )}
          </div>
        </form>
      </ConsolePanel>

      <div className={styles.metaGrid}>
        <ConsolePanel title="SYSTEM STATUS & METADATA" glowColor="purple">
          <div className={styles.metaCard}>
            <div className={styles.metaRow}>
              <span className={styles.metaLabel}>SYSTEM AUTHORITY:</span>
              <span className={styles.metaValue}>LEVEL_A_DEV</span>
            </div>
            <div className={styles.metaRow}>
              <span className={styles.metaLabel}>OPERATING SYSTEM:</span>
              <span className={styles.metaValue}>LINUX</span>
            </div>
            <div className={styles.metaRow}>
              <span className={styles.metaLabel}>LAST UPDATED TIMEFRAME:</span>
              <span className={styles.metaValue}>
                {lastUpdated ? new Date(lastUpdated).toLocaleString() : 'NEVER'}
              </span>
            </div>
          </div>
        </ConsolePanel>
      </div>
    </div>
  );
};
