'use client';

import { useState } from 'react';
import { checkApiKey, type KeyCheckResult } from '@/lib/stocks/finnhub';
import styles from './stocks.module.css';

const CHECK_MESSAGES: Record<Exclude<KeyCheckResult, 'ok'>, string> = {
  invalid: 'Finnhub kennt diesen Key nicht. Prüfe, ob du ihn vollständig und ohne Leerzeichen kopiert hast.',
  limit: 'Dieser Key hat sein Limit gerade erreicht. Warte eine Minute oder nimm einen anderen Key.',
  unreachable: 'Finnhub ist gerade nicht erreichbar. Prüfe deine Internetverbindung und versuche es erneut.',
};

interface KeySetupProps {
  isChange: boolean;
  onSaved: (key: string) => void;
  onCancel?: () => void;
}

export default function KeySetup({ isChange, onSaved, onCancel }: KeySetupProps) {
  const [value, setValue] = useState('');
  const [message, setMessage] = useState('');
  const [checking, setChecking] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const key = value.trim();
    if (!key) {
      setMessage('Bitte füge zuerst deinen API-Key ein.');
      return;
    }
    setChecking(true);
    setMessage('Prüfe Key …');
    const result = await checkApiKey(key);
    setChecking(false);
    if (result === 'ok') {
      onSaved(key);
    } else {
      setMessage(CHECK_MESSAGES[result]);
    }
  }

  return (
    <section className={styles.section}>
      <div className={`${styles.inner} ${styles.setup}`}>
        <p className={styles.eyebrow}>{isChange ? 'Einstellungen' : 'Einrichtung · ca. 2 Minuten'}</p>
        <h1 className={styles.title}>{isChange ? 'API-Key ändern' : 'Aktien im Parity Terminal'}</h1>
        <p className={styles.lead}>
          Kurse, Kennzahlen und Firmendaten kommen von Finnhub, einem Anbieter für Finanzdaten. Dafür brauchst du
          einen eigenen, kostenlosen API-Key. Jeder Nutzer verwendet seinen eigenen Key.
        </p>

        <ol className={styles.steps}>
          <li className={styles.step}>
            <h3>Konto anlegen</h3>
            <p>Registriere dich kostenlos bei Finnhub, mit E-Mail und Passwort oder mit Google. Eine Kreditkarte brauchst du nicht.</p>
            <a className={styles.stepLink} href="https://finnhub.io/register" target="_blank" rel="noopener noreferrer">
              Finnhub-Registrierung öffnen ↗
            </a>
          </li>
          <li className={styles.step}>
            <h3>E-Mail bestätigen</h3>
            <p>Öffne die Bestätigungsmail von Finnhub und klicke auf den Link darin.</p>
          </li>
          <li className={styles.step}>
            <h3>Key kopieren</h3>
            <p>Melde dich an. Im Dashboard steht ganz oben unter „API Key“ eine lange Zeichenkette. Kopiere sie vollständig.</p>
            <a className={styles.stepLink} href="https://finnhub.io/dashboard" target="_blank" rel="noopener noreferrer">
              Finnhub-Dashboard öffnen ↗
            </a>
          </li>
          <li className={styles.step}>
            <h3>Key einfügen</h3>
            <p>Füge den Key unten ein und tippe auf „Key prüfen und speichern“.</p>
          </li>
        </ol>

        <form className={styles.setupForm} onSubmit={handleSubmit} noValidate>
          <label className={styles.label} htmlFor="finnhub-key">Dein Finnhub API-Key</label>
          <input
            id="finnhub-key"
            className={styles.input}
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="z. B. c1a2b3c4d5e6f7g8h9i0"
            autoComplete="off"
            spellCheck={false}
            autoFocus={isChange}
          />
          <div className={styles.setupActions}>
            <button type="submit" className={`${styles.btn} ${styles.btnSolid}`} disabled={checking}>
              Key prüfen und speichern
            </button>
            {onCancel && (
              <button type="button" className={styles.btn} onClick={onCancel}>
                Abbrechen
              </button>
            )}
          </div>
          <p className={styles.error} role="alert">{message}</p>
        </form>

        <p className={styles.note}>
          Dein Key bleibt nur in diesem Browser gespeichert und wird nur an Finnhub gesendet. Der kostenlose Plan erlaubt
          60 Anfragen pro Minute. Ist das Limit erreicht, zeigt die Seite einen Hinweis, und du kannst einen anderen Key eingeben.
        </p>
      </div>
    </section>
  );
}
