'use client';

import { DoshaScore } from '@/lib/api';
import { cn } from '@/lib/utils';

interface DoshaBarsProps {
  scores: DoshaScore | null;
  animated?: boolean;
}

const DOSHA_CONFIG = {
  vata: {
    label: 'Vata',
    emoji: '💨',
    color: 'bg-vata-500',
    bgColor: 'bg-vata-100',
    description: 'Air & Space - Movement, creativity, flexibility',
  },
  pitta: {
    label: 'Pitta',
    emoji: '🔥',
    color: 'bg-pitta-500',
    bgColor: 'bg-pitta-100',
    description: 'Fire & Water - Metabolism, transformation, intellect',
  },
  kapha: {
    label: 'Kapha',
    emoji: '🌊',
    color: 'bg-kapha-500',
    bgColor: 'bg-kapha-100',
    description: 'Earth & Water - Structure, stability, immunity',
  },
};

export function DoshaBars({ scores, animated = true }: DoshaBarsProps) {
  if (!scores) {
    return (
      <div className="text-center text-gray-400 dark:text-gray-500 py-8" role="status">
        <span aria-hidden="true" className="text-3xl block mb-2">🧬</span>
        Complete the assessment to see your Dosha profile
      </div>
    );
  }

  return (
    <div className="space-y-5 sm:space-y-6 animate-fade-in-up" role="list" aria-label="Dosha scores">
      {(Object.keys(DOSHA_CONFIG) as Array<keyof typeof DOSHA_CONFIG>).map(
        (dosha) => {
          const config = DOSHA_CONFIG[dosha];
          const percentage = Math.round(scores[dosha] * 100);

          return (
            <div key={dosha} role="listitem" className="group">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-lg sm:text-xl" aria-hidden="true">{config.emoji}</span>
                  <span className="font-medium text-gray-700 dark:text-gray-200">
                    {config.label}
                  </span>
                </div>
                <span className="text-base sm:text-lg font-bold text-gray-900 dark:text-gray-100">
                  {percentage}%
                </span>
              </div>

              {/* Progress Bar */}
              <div
                className={cn(
                  'h-3 sm:h-4 rounded-full overflow-hidden dark:bg-opacity-30',
                  config.bgColor
                )}
                role="progressbar"
                aria-valuenow={percentage}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`${config.label}: ${percentage}%`}
              >
                <div
                  className={cn(
                    'h-full rounded-full transition-all duration-1000',
                    config.color,
                    animated && 'dosha-bar-animated'
                  )}
                  style={
                    {
                      width: `${percentage}%`,
                      '--dosha-width': `${percentage}%`,
                    } as React.CSSProperties
                  }
                />
              </div>

              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                {config.description}
              </p>
            </div>
          );
        }
      )}
    </div>
  );
}

interface DoshaCardProps {
  scores: DoshaScore;
  constitutionType: string;
}

export function DoshaCard({ scores, constitutionType }: DoshaCardProps) {
  const dominantDosha = Object.entries(scores).reduce((a, b) =>
    a[1] > b[1] ? a : b
  )[0] as keyof typeof DOSHA_CONFIG;

  const config = DOSHA_CONFIG[dominantDosha];

  return (
    <article 
      className="bg-white dark:bg-gray-900 rounded-2xl shadow-lg p-4 sm:p-6 border border-gray-100 dark:border-gray-800 animate-fade-in-up"
      aria-labelledby="dosha-card-title"
    >
      <header className="text-center mb-6">
        <div className="text-4xl sm:text-5xl mb-2" aria-hidden="true">{config.emoji}</div>
        <h2 id="dosha-card-title" className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-gray-100">
          {constitutionType}
        </h2>
        <p className="text-gray-500 dark:text-gray-400 text-sm sm:text-base">Your Prakriti Constitution</p>
      </header>

      <DoshaBars scores={scores} />

      <footer className="mt-6 p-3 sm:p-4 bg-amber-50 dark:bg-amber-500/10 rounded-xl">
        <p className="text-sm text-amber-800 dark:text-amber-200">
          <strong>Dominant Dosha: {config.label}</strong>
          <br />
          <span className="text-xs sm:text-sm">{config.description}</span>
        </p>
      </footer>
    </article>
  );
}
