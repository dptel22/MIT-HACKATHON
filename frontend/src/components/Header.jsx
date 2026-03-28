import { useEffect, useState } from 'react';

export default function Header({ connected, warmupDone }) {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const time = now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

  return (
    <header className="header">
      <div className="header-logo">Resolv<span>.io</span></div>
      <div className="header-spacer" />
      {!warmupDone && (
        <span className="badge badge-warming">Warming up ...</span>
      )}
      <div className="connection-pill">
        <span className={`dot ${connected ? 'dot-green' : 'dot-red'}`} />
        <span style={{ color: connected ? 'var(--neon-green)' : 'var(--neon-red)', fontWeight: 800 }}>
          {connected ? 'LINK ESTABLISHED' : 'OFFLINE'}
        </span>
      </div>
      <span style={{ color: 'var(--text-dim)', fontSize: 10, fontFamily: 'var(--font-mono)', letterSpacing: '0.1em' }}>POLLING: 2S</span>
      <span className="header-clock">{time}</span>
    </header>
  );
}
