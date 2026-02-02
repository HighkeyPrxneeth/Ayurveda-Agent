'use client';

import { useState, useEffect, useCallback } from 'react';
import { DoshaTrendData, getDoshaTrend, DoshaHistoryEntry, getDoshaHistory } from '@/lib/api';
import { cn } from '@/lib/utils';
import { RefreshCw, TrendingUp } from 'lucide-react';

interface DoshaTrendChartProps {
  userId: string;
  className?: string;
}

const DOSHA_COLORS = {
  vata: { line: '#7C3AED', bg: 'bg-vata-500', text: 'text-vata-600 dark:text-vata-400' },
  pitta: { line: '#DC2626', bg: 'bg-pitta-500', text: 'text-pitta-600 dark:text-pitta-400' },
  kapha: { line: '#0891B2', bg: 'bg-kapha-500', text: 'text-kapha-600 dark:text-kapha-400' },
};

export function DoshaTrendChart({ userId, className }: DoshaTrendChartProps) {
  const [trendData, setTrendData] = useState<DoshaTrendData | null>(null);
  const [history, setHistory] = useState<DoshaHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<'chart' | 'history'>('chart');

  const fetchData = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    setError(null);
    try {
      const [trend, hist] = await Promise.all([
        getDoshaTrend(userId, 30),
        getDoshaHistory(userId, 10),
      ]);
      setTrendData(trend);
      setHistory(hist);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load trend data');
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) {
    return (
      <div className={cn('bg-white dark:bg-gray-900 rounded-2xl shadow-lg p-6', className)}>
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/3"></div>
          <div className="h-40 bg-gray-200 dark:bg-gray-700 rounded"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn('bg-white dark:bg-gray-900 rounded-2xl shadow-lg p-6', className)}>
        <div className="text-center text-gray-500 dark:text-gray-400">
          <p className="mb-2">{error}</p>
          <button onClick={fetchData} className="text-ayurveda-gold hover:underline text-sm">
            Try again
          </button>
        </div>
      </div>
    );
  }

  if (!trendData || trendData.count === 0) {
    return (
      <div className={cn('bg-white dark:bg-gray-900 rounded-2xl shadow-lg p-6', className)}>
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="h-5 w-5 text-ayurveda-gold" />
          <h3 className="font-semibold text-gray-800 dark:text-gray-100">Dosha Trend</h3>
        </div>
        <div className="text-center py-8 text-gray-500 dark:text-gray-400">
          <p className="text-sm">No trend data available yet.</p>
          <p className="text-xs mt-1">Complete assessments over time to see trends.</p>
        </div>
      </div>
    );
  }

  const maxValue = Math.max(
    ...trendData.vata,
    ...trendData.pitta,
    ...trendData.kapha
  );

  return (
    <div className={cn('bg-white dark:bg-gray-900 rounded-2xl shadow-lg p-4 sm:p-6', className)}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-ayurveda-gold" />
          <h3 className="font-semibold text-gray-800 dark:text-gray-100">Dosha Trend</h3>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg bg-gray-100 dark:bg-gray-800 p-0.5">
            <button
              type="button"
              onClick={() => setView('chart')}
              className={cn(
                'px-2 py-1 text-xs rounded-md transition-colors',
                view === 'chart' ? 'bg-white dark:bg-gray-700 shadow-sm' : ''
              )}
            >
              Chart
            </button>
            <button
              type="button"
              onClick={() => setView('history')}
              className={cn(
                'px-2 py-1 text-xs rounded-md transition-colors',
                view === 'history' ? 'bg-white dark:bg-gray-700 shadow-sm' : ''
              )}
            >
              History
            </button>
          </div>
          <button
            type="button"
            onClick={fetchData}
            className="p-1.5 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
            aria-label="Refresh"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Legend */}
      <div className="flex gap-4 mb-4 text-xs">
        {Object.entries(DOSHA_COLORS).map(([dosha, colors]) => (
          <div key={dosha} className="flex items-center gap-1.5">
            <div className={cn('w-3 h-3 rounded-full', colors.bg)} />
            <span className={colors.text}>{dosha.charAt(0).toUpperCase() + dosha.slice(1)}</span>
          </div>
        ))}
      </div>

      {view === 'chart' ? (
        <SimpleTrendChart data={trendData} maxValue={maxValue} />
      ) : (
        <HistoryList history={history} />
      )}

      <p className="text-xs text-gray-400 dark:text-gray-500 mt-3 text-center">
        {trendData.count} assessment{trendData.count !== 1 ? 's' : ''} tracked
      </p>
    </div>
  );
}

// Simple trend chart using SVG
function SimpleTrendChart({ data, maxValue }: { data: DoshaTrendData; maxValue: number }) {
  const height = 120;
  const width = 280;
  const padding = { top: 10, right: 10, bottom: 20, left: 30 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  const points = data.labels.length;
  if (points === 0) return null;

  const xStep = points > 1 ? chartWidth / (points - 1) : chartWidth;

  const getY = (value: number) => {
    const normalized = maxValue > 0 ? value / maxValue : 0;
    return chartHeight - normalized * chartHeight + padding.top;
  };

  const createPath = (values: number[]) => {
    if (values.length === 0) return '';
    return values
      .map((v, i) => {
        const x = padding.left + i * xStep;
        const y = getY(v);
        return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
      })
      .join(' ');
  };

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full min-w-[280px] h-32">
        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => (
          <line
            key={ratio}
            x1={padding.left}
            y1={padding.top + chartHeight * (1 - ratio)}
            x2={width - padding.right}
            y2={padding.top + chartHeight * (1 - ratio)}
            stroke="currentColor"
            strokeOpacity={0.1}
            strokeDasharray="2,2"
          />
        ))}

        {/* Y-axis labels */}
        <text x={padding.left - 5} y={padding.top + 4} fontSize="8" fill="currentColor" fillOpacity={0.5} textAnchor="end">
          {Math.round(maxValue * 100)}%
        </text>
        <text x={padding.left - 5} y={height - padding.bottom + 4} fontSize="8" fill="currentColor" fillOpacity={0.5} textAnchor="end">
          0%
        </text>

        {/* Lines */}
        <path d={createPath(data.vata)} fill="none" stroke={DOSHA_COLORS.vata.line} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        <path d={createPath(data.pitta)} fill="none" stroke={DOSHA_COLORS.pitta.line} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        <path d={createPath(data.kapha)} fill="none" stroke={DOSHA_COLORS.kapha.line} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />

        {/* X-axis labels - show first, middle, and last */}
        {data.labels.length > 0 && (
          <>
            <text x={padding.left} y={height - 4} fontSize="7" fill="currentColor" fillOpacity={0.5} textAnchor="start">
              {data.labels[0]}
            </text>
            {data.labels.length > 2 && (
              <text x={width - padding.right} y={height - 4} fontSize="7" fill="currentColor" fillOpacity={0.5} textAnchor="end">
                {data.labels[data.labels.length - 1]}
              </text>
            )}
          </>
        )}
      </svg>
    </div>
  );
}

// History list component
function HistoryList({ history }: { history: DoshaHistoryEntry[] }) {
  if (history.length === 0) {
    return (
      <div className="text-center py-4 text-gray-500 dark:text-gray-400 text-sm">
        No assessment history available.
      </div>
    );
  }

  return (
    <div className="space-y-2 max-h-48 overflow-y-auto">
      {history.map((entry, index) => (
        <div
          key={index}
          className="flex items-center justify-between p-2 rounded-lg bg-gray-50 dark:bg-gray-800/50 text-sm"
        >
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className={cn(
                'px-2 py-0.5 rounded-full text-xs font-medium',
                entry.dominant_dosha === 'vata' && 'bg-vata-100 dark:bg-vata-900/30 text-vata-700 dark:text-vata-300',
                entry.dominant_dosha === 'pitta' && 'bg-pitta-100 dark:bg-pitta-900/30 text-pitta-700 dark:text-pitta-300',
                entry.dominant_dosha === 'kapha' && 'bg-kapha-100 dark:bg-kapha-900/30 text-kapha-700 dark:text-kapha-300',
              )}>
                {entry.dominant_dosha.charAt(0).toUpperCase() + entry.dominant_dosha.slice(1)}
              </span>
              <span className="text-xs text-gray-500 dark:text-gray-400">
                {entry.constitution_type}
              </span>
            </div>
            <div className="flex gap-3 mt-1 text-xs text-gray-500 dark:text-gray-400">
              <span>V: {Math.round(entry.vata * 100)}%</span>
              <span>P: {Math.round(entry.pitta * 100)}%</span>
              <span>K: {Math.round(entry.kapha * 100)}%</span>
            </div>
          </div>
          <div className="text-xs text-gray-400 dark:text-gray-500 text-right">
            {new Date(entry.timestamp).toLocaleDateString()}
          </div>
        </div>
      ))}
    </div>
  );
}
