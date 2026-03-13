import { useState, useEffect } from 'react';
import TerminalPairScreen from './TerminalPairScreen';
import TerminalShell from './TerminalShell';
import { Toaster } from '../../components/ui/sonner';

const STORAGE_KEY = 'agrismart_terminal';

/**
 * Main Terminal page — manages pairing state.
 * Persists session in localStorage so the terminal survives browser restarts.
 * This page renders OUTSIDE the normal app layout (no sidebar, no auth context).
 */
export default function TerminalPage() {
  const [session, setSession] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });

  const handlePaired = (data) => {
    setSession(data);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  };

  const handleLogout = () => {
    setSession(null);
    localStorage.removeItem(STORAGE_KEY);
  };

  // Set viewport meta for mobile
  useEffect(() => {
    const existing = document.querySelector('meta[name="viewport"]');
    if (existing) {
      existing.setAttribute('content', 'width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover');
    }
    // Add safe area class
    document.documentElement.classList.add('terminal-mode');
    return () => {
      document.documentElement.classList.remove('terminal-mode');
      if (existing) {
        existing.setAttribute('content', 'width=device-width, initial-scale=1');
      }
    };
  }, []);

  if (!session) {
    return (
      <>
        <TerminalPairScreen onPaired={handlePaired} />
        <Toaster position="top-center" richColors />
      </>
    );
  }

  return (
    <>
      <TerminalShell session={session} onLogout={handleLogout} />
      <Toaster position="top-center" richColors />
    </>
  );
}
