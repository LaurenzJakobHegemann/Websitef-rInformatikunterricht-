'use client';

import type { KeyProblem } from '@/lib/stocks/finnhub';
import styles from './stocks.module.css';

const MESSAGES: Record<KeyProblem, { title: string; text: string }> = {
  limit: {
    title: 'Limit erreicht.',
    text: 'Dein Finnhub-Key hat 60 Anfragen pro Minute verbraucht. Nach einer Minute geht es automatisch weiter, oder du gibst einen anderen Key ein.',
  },
  invalid: {
    title: 'Key ungültig.',
    text: 'Finnhub akzeptiert deinen API-Key nicht mehr. Gib einen gültigen Key ein.',
  },
};

interface KeyBannerProps {
  problem: KeyProblem;
  onChangeKey: () => void;
  onDismiss: () => void;
}

export default function KeyBanner({ problem, onChangeKey, onDismiss }: KeyBannerProps) {
  const { title, text } = MESSAGES[problem];
  return (
    <div className={styles.banner} role="status">
      <div className={styles.bannerInner}>
        <p className={styles.bannerText}>
          <strong>{title}</strong> {text}
        </p>
        <div className={styles.bannerActions}>
          <button type="button" className={`${styles.btn} ${styles.btnOnBlue} ${styles.btnSm}`} onClick={onChangeKey}>
            Neuen Key eingeben
          </button>
          <button type="button" className={styles.bannerClose} onClick={onDismiss} aria-label="Hinweis schließen">
            ×
          </button>
        </div>
      </div>
    </div>
  );
}
