'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { DoshaBars } from '@/components/DoshaBars';
import { ChatInterface } from '@/components/ChatInterface';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { DoshaTrendChart } from '@/components/DoshaTrendChart';
import { AssessmentResponse } from '@/lib/api';

export default function DashboardPage() {
  const [assessment, setAssessment] = useState<AssessmentResponse | null>(null);
  const [mounted, setMounted] = useState(false);
  const [chatHeight, setChatHeight] = useState<number | null>(null);
  const [isLargeScreen, setIsLargeScreen] = useState(false);
  const leftColumnRef = useRef<HTMLElement>(null);

  // Load assessment from localStorage on mount
  useEffect(() => {
    setMounted(true);
    const stored = localStorage.getItem('doshaAssessment');
    if (stored) {
      try {
        setAssessment(JSON.parse(stored));
      } catch {
        // Invalid data - remove it
        localStorage.removeItem('doshaAssessment');
      }
    }
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mediaQuery = window.matchMedia('(min-width: 1024px)');
    const handleChange = (event: MediaQueryListEvent | MediaQueryList) => {
      setIsLargeScreen(event.matches);
    };
    handleChange(mediaQuery);
    mediaQuery.addEventListener?.('change', handleChange);
    return () => mediaQuery.removeEventListener?.('change', handleChange);
  }, []);

  useEffect(() => {
    if (!leftColumnRef.current || !isLargeScreen) {
      setChatHeight(null);
      return;
    }
    const updateHeight = () => {
      const height = leftColumnRef.current?.offsetHeight ?? null;
      setChatHeight(height);
    };
    updateHeight();
    const observer = new ResizeObserver(updateHeight);
    observer.observe(leftColumnRef.current);
    return () => observer.disconnect();
  }, [assessment, isLargeScreen]);

  // Prevent hydration mismatch
  if (!mounted) {
    return (
      <main id="main-content" className="min-h-screen p-4 sm:p-8 text-gray-900 dark:text-gray-100">
        <div className="max-w-6xl mx-auto">
          <div className="animate-pulse">
            <div className="h-8 bg-gray-200 dark:bg-gray-800 rounded w-48 mb-8"></div>
            <div className="grid lg:grid-cols-3 gap-6">
              <div className="lg:col-span-1 h-96 bg-gray-200 dark:bg-gray-800 rounded-2xl"></div>
              <div className="lg:col-span-2 h-96 bg-gray-200 dark:bg-gray-800 rounded-2xl"></div>
            </div>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main id="main-content" className="min-h-screen p-4 sm:p-8 text-gray-900 dark:text-gray-100">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6 sm:mb-8">
          <div>
            <nav aria-label="Breadcrumb">
              <Link 
                href="/" 
                className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 text-sm inline-flex items-center gap-1 focus:outline-none focus:underline"
              >
                <span aria-hidden="true">←</span> Home
              </Link>
            </nav>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-gray-100 mt-1">
              Wellness Dashboard
            </h1>
          </div>

          {!assessment && (
            <Link
              href="/assess"
              className="px-4 py-2 bg-ayurveda-gold text-white rounded-lg hover:bg-amber-600 transition-all hover:-translate-y-0.5 text-sm self-start sm:self-auto focus:outline-none focus:ring-2 focus:ring-ayurveda-gold focus:ring-offset-2 dark:focus:ring-offset-gray-900"
            >
              Take Assessment
            </Link>
          )}
        </header>

        {/* Grid Layout */}
        <div className="grid lg:grid-cols-3 gap-4 sm:gap-6">
          {/* Left Column - Dosha Profile */}
          <aside ref={leftColumnRef} className="lg:col-span-1 space-y-4 sm:space-y-6">
            {/* Dosha Scores Card */}
            <section 
              className="bg-white dark:bg-gray-900 rounded-2xl shadow-lg p-4 sm:p-6 transition-all hover:shadow-xl"
              aria-labelledby="dosha-profile-title"
            >
              <h2 id="dosha-profile-title" className="text-lg font-semibold text-gray-800 dark:text-gray-100 mb-4">
                Your Dosha Profile
              </h2>

              {assessment ? (
                <>
                  <div className="text-center mb-6">
                    <span className="inline-block px-4 py-2 bg-amber-100 dark:bg-amber-500/20 text-amber-800 dark:text-amber-200 rounded-full font-semibold text-sm sm:text-base">
                      {assessment.constitution_type}
                    </span>
                  </div>
                  <DoshaBars scores={assessment.scores} />
                  <button
                    type="button"
                    onClick={() => {
                      localStorage.removeItem('doshaAssessment');
                      setAssessment(null);
                    }}
                    className="mt-4 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 w-full py-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors focus:outline-none focus:ring-2 focus:ring-ayurveda-gold"
                  >
                    Clear & Retake Assessment
                  </button>
                </>
              ) : (
                <div className="text-center py-6 sm:py-8">
                  <div className="text-3xl sm:text-4xl mb-4" aria-hidden="true">🧬</div>
                  <p className="text-gray-500 dark:text-gray-400 mb-4 text-sm sm:text-base">
                    Complete your Prakriti assessment to see your Dosha profile
                  </p>
                  <Link
                    href="/assess"
                    className="px-6 py-2 bg-ayurveda-gold text-white rounded-lg hover:bg-amber-600 transition-all hover:-translate-y-0.5 inline-block focus:outline-none focus:ring-2 focus:ring-ayurveda-gold focus:ring-offset-2 dark:focus:ring-offset-gray-900"
                  >
                    Start Assessment
                  </Link>
                </div>
              )}
            </section>

            {/* Quick Info Card */}
            <section
              className="bg-white dark:bg-gray-900 rounded-2xl shadow-lg p-4 sm:p-6 transition-all hover:shadow-xl"
              aria-labelledby="dosha-info-title"
            >
              <h2 id="dosha-info-title" className="font-semibold text-gray-800 dark:text-gray-100 mb-3">
                Understanding Doshas
              </h2>
              <dl className="space-y-3 text-sm text-gray-600 dark:text-gray-300">
                <div>
                  <dt className="font-semibold text-vata-600 dark:text-vata-400 inline">Vata</dt>
                  <dd className="inline ml-1">(Air + Space): Governs movement, creativity, and communication.</dd>
                </div>
                <div>
                  <dt className="font-semibold text-pitta-600 dark:text-pitta-400 inline">Pitta</dt>
                  <dd className="inline ml-1">(Fire + Water): Governs metabolism, digestion, and transformation.</dd>
                </div>
                <div>
                  <dt className="font-semibold text-kapha-600 dark:text-kapha-400 inline">Kapha</dt>
                  <dd className="inline ml-1">(Earth + Water): Governs structure, stability, and immunity.</dd>
                </div>
              </dl>
            </section>

            {/* Dosha Trend Chart */}
            <DoshaTrendChart userId="default-user" />
          </aside>

          {/* Right Column - Chat */}
          <div
            className="lg:col-span-2"
            style={chatHeight ? { height: `${chatHeight}px` } : undefined}
          >
            <ErrorBoundary>
              <ChatInterface doshaScores={assessment?.scores} />
            </ErrorBoundary>
          </div>
        </div>

        {/* Disclaimer */}
        <aside className="mt-6 sm:mt-8 p-3 sm:p-4 bg-yellow-50 dark:bg-yellow-500/10 rounded-xl" role="note">
          <p className="text-xs sm:text-sm text-yellow-800 dark:text-yellow-200">
            <strong>Disclaimer:</strong> This application provides wellness and
            educational information only. It is not intended to diagnose, treat,
            cure, or prevent any disease. Always consult a qualified Ayurvedic
            practitioner or healthcare provider for health concerns.
          </p>
        </aside>
      </div>
    </main>
  );
}
