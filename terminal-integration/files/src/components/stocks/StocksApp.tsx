'use client';

import dynamic from 'next/dynamic';

// Key und Watchlist liegen im localStorage; ohne Server-Rendering gibt es keinen Hydration-Unterschied.
const StocksTerminal = dynamic(() => import('./StocksTerminal'), {
  ssr: false,
  loading: () => null,
});

export default function StocksApp() {
  return <StocksTerminal />;
}
