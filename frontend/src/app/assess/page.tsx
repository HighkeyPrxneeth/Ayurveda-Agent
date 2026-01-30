'use client';

import { useState } from 'react';
import { DoshaForm } from '@/components/DoshaForm';
import { DoshaCard } from '@/components/DoshaBars';
import { AssessmentResponse } from '@/lib/api';
import Link from 'next/link';

export default function AssessPage() {
  const [result, setResult] = useState<AssessmentResponse | null>(null);

  const handleComplete = (assessment: AssessmentResponse) => {
    setResult(assessment);
    // Store in localStorage for use in dashboard
    localStorage.setItem('doshaAssessment', JSON.stringify(assessment));
    // Scroll to top to show results
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  if (result) {
    return (
      <main id="main-content" className="min-h-screen p-4 sm:p-8 text-gray-900 dark:text-gray-100">
        <article className="max-w-2xl mx-auto">
          <header className="text-center mb-8 animate-fade-in-up">
            <div className="text-4xl mb-3" aria-hidden="true">🎉</div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-gray-100 mb-2">
              Your Prakriti Results
            </h1>
            <p className="text-gray-600 dark:text-gray-300">
              Based on your responses, here is your Ayurvedic constitution profile.
            </p>
          </header>

          <DoshaCard
            scores={result.scores}
            constitutionType={result.constitution_type}
          />

          <nav className="mt-8 flex flex-col sm:flex-row gap-4 justify-center" aria-label="Next steps">
            <Link
              href="/dashboard"
              className="px-6 py-3 bg-ayurveda-gold text-white font-semibold rounded-xl hover:bg-amber-600 transition-all hover:-translate-y-0.5 text-center focus:outline-none focus:ring-2 focus:ring-ayurveda-gold focus:ring-offset-2 dark:focus:ring-offset-gray-900"
            >
              Go to Dashboard
            </Link>
            <button
              type="button"
              onClick={() => setResult(null)}
              className="px-6 py-3 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-200 font-semibold rounded-xl hover:bg-gray-200 dark:hover:bg-gray-700 transition-all hover:-translate-y-0.5 focus:outline-none focus:ring-2 focus:ring-ayurveda-gold focus:ring-offset-2 dark:focus:ring-offset-gray-900"
            >
              Retake Assessment
            </button>
          </nav>
          
          {/* Print/Download hint */}
          <p className="text-center text-sm text-gray-500 dark:text-gray-400 mt-6">
            <span aria-hidden="true">💾</span> Tip: Your results are saved locally. Visit the Dashboard anytime to view them.
          </p>
        </article>
      </main>
    );
  }

  return (
    <main id="main-content" className="min-h-screen p-4 sm:p-8 text-gray-900 dark:text-gray-100">
      <div className="max-w-3xl mx-auto">
        <nav aria-label="Breadcrumb">
          <Link
            href="/"
            className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 mb-4 inline-flex items-center gap-1 focus:outline-none focus:underline"
          >
            <span aria-hidden="true">←</span> Back to Home
          </Link>
        </nav>

        <header className="text-center mb-8 animate-fade-in-up">
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-gray-100 mb-2">
            Prakriti Assessment
          </h1>
          <p className="text-gray-600 dark:text-gray-300 max-w-lg mx-auto text-sm sm:text-base">
            Answer the following questions honestly based on your natural tendencies
            throughout your life, not your current state.
          </p>
        </header>

        <DoshaForm onComplete={handleComplete} />
      </div>
    </main>
  );
}
