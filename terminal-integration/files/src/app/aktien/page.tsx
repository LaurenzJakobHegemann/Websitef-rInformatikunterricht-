import type { Metadata } from 'next';
import StocksApp from '@/components/stocks/StocksApp';

export const metadata: Metadata = {
  title: 'Aktien',
  description: 'Watchlist, Firmenprofile, Finanzkennzahlen und Quartalszahlen für Parity-Mitglieder.',
};

export default function AktienPage() {
  return <StocksApp />;
}
