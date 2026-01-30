'use client';

import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';

type Theme = 'light' | 'dark';

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>('light');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const stored = localStorage.getItem('theme') as Theme | null;
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const initial = stored ?? (prefersDark ? 'dark' : 'light');
    setTheme(initial);
    document.documentElement.classList.toggle('dark', initial === 'dark');
  }, []);

  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    localStorage.setItem('theme', next);
    document.documentElement.classList.toggle('dark', next === 'dark');
  };

  // Prevent hydration mismatch
  if (!mounted) return null;

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className={cn(
        'fixed right-4 top-4 z-50 rounded-full px-3 py-2 text-xs font-medium shadow-md transition-all',
        'bg-white/80 text-gray-700 hover:bg-white focus:outline-none focus:ring-2 focus:ring-ayurveda-gold focus:ring-offset-2',
        'dark:bg-gray-800/80 dark:text-gray-200 dark:hover:bg-gray-800 dark:focus:ring-offset-gray-900'
      )}
      aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      aria-pressed={theme === 'dark'}
    >
      <span aria-hidden="true">{theme === 'dark' ? '☀️' : '🌙'}</span>
      <span className="ml-1">{theme === 'dark' ? 'Light' : 'Dark'}</span>
    </button>
  );
}