'use client';

import { useState, useEffect, useRef, useId } from 'react';
import { Question, QuestionAnswer, assessDosha, getQuestions, AssessmentResponse } from '@/lib/api';
import { cn } from '@/lib/utils';

interface DoshaFormProps {
  onComplete: (result: AssessmentResponse) => void;
}

const LIKERT_LABELS: Record<number, string> = {
  1: 'Not at all',
  2: 'Slightly',
  3: 'Moderately',
  4: 'Mostly',
  5: 'Exactly me',
};

export function DoshaForm({ onComplete }: DoshaFormProps) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [currentCategory, setCurrentCategory] = useState<string>('Physical');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const categoryContainerRef = useRef<HTMLDivElement>(null);
  const formId = useId();

  // Fetch questions on mount
  useEffect(() => {
    getQuestions()
      .then(setQuestions)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const categories = [...new Set(questions.map((q) => q.category))];
  const currentQuestions = questions.filter((q) => q.category === currentCategory);

  const totalAnswered = Object.keys(answers).length;
  const progress = questions.length > 0 ? Math.round((totalAnswered / questions.length) * 100) : 0;
  
  // Calculate remaining questions per category
  const getCategoryProgress = (cat: string) => {
    const catQuestions = questions.filter((q) => q.category === cat);
    const catAnswered = catQuestions.filter((q) => answers[q.question_id]).length;
    return { answered: catAnswered, total: catQuestions.length, remaining: catQuestions.length - catAnswered };
  };

  const handleAnswer = (questionId: string, value: number) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
    setError(null); // Clear error when user answers
  };

  const handleCategoryChange = (cat: string) => {
    setCurrentCategory(cat);
    // Scroll to top of questions on category change
    categoryContainerRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleSubmit = async () => {
    const minRequired = Math.ceil(questions.length * 0.5);
    if (totalAnswered < minRequired) {
      setError(`Please answer at least ${minRequired} questions (currently ${totalAnswered}/${questions.length})`);
      return;
    }

    setSubmitting(true);
    setError(null);

    const answerList: QuestionAnswer[] = Object.entries(answers).map(
      ([question_id, answer_value]) => ({ question_id, answer_value })
    );

    try {
      const result = await assessDosha(answerList);
      onComplete(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Assessment failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3" role="status" aria-live="polite">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-ayurveda-gold" aria-hidden="true"></div>
        <span className="text-gray-500 dark:text-gray-400">Loading questions...</span>
      </div>
    );
  }

  if (!questions.length && !loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3 text-center p-6" role="alert">
        <span className="text-4xl" aria-hidden="true">⚠️</span>
        <p className="text-gray-600 dark:text-gray-300">Unable to load questions. Please check that the backend is running.</p>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 bg-ayurveda-gold text-white rounded-lg hover:bg-amber-600 transition-colors focus:outline-none focus:ring-2 focus:ring-ayurveda-gold focus:ring-offset-2"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <form 
      className="bg-white dark:bg-gray-900 rounded-2xl shadow-lg p-4 sm:p-6 animate-fade-in-up"
      onSubmit={(e) => { e.preventDefault(); handleSubmit(); }}
      aria-label="Prakriti Assessment Form"
    >
      {/* Progress Bar */}
      <div className="mb-6" role="region" aria-label="Progress">
        <div className="flex justify-between text-sm text-gray-600 dark:text-gray-400 mb-2">
          <span id={`${formId}-progress-label`}>Progress</span>
          <span aria-live="polite">{totalAnswered} / {questions.length} questions answered</span>
        </div>
        <div 
          className="h-2 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden"
          role="progressbar"
          aria-valuenow={progress}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-labelledby={`${formId}-progress-label`}
        >
          <div
            className="h-full bg-ayurveda-gold transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
          {progress < 50 ? `Answer at least ${Math.ceil(questions.length * 0.5) - totalAnswered} more questions to submit` : 'You can submit your assessment'}
        </p>
      </div>

      {/* Category Tabs */}
      <nav className="mb-6" aria-label="Question categories">
        <div 
          className="flex gap-2 overflow-x-auto pb-2 scrollbar-thin" 
          role="tablist"
          aria-label="Assessment categories"
        >
          {categories.map((cat) => {
            const { answered, total, remaining } = getCategoryProgress(cat);
            const isComplete = remaining === 0;
            const isCurrent = currentCategory === cat;

            return (
              <button
                key={cat}
                type="button"
                role="tab"
                aria-selected={isCurrent}
                aria-controls={`${formId}-panel-${cat}`}
                id={`${formId}-tab-${cat}`}
                onClick={() => handleCategoryChange(cat)}
                className={cn(
                  'px-3 sm:px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap focus:outline-none focus:ring-2 focus:ring-ayurveda-gold focus:ring-offset-2 dark:focus:ring-offset-gray-900',
                  isCurrent
                    ? 'bg-ayurveda-gold text-white shadow-md'
                    : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700',
                  isComplete && !isCurrent && 'ring-2 ring-green-500 ring-offset-1 dark:ring-offset-gray-900'
                )}
              >
                {cat}
                <span className="ml-1.5 text-xs opacity-75">
                  {answered}/{total}
                </span>
                {isComplete && <span className="ml-1" aria-label="complete">✓</span>}
              </button>
            );
          })}
        </div>
      </nav>

      {/* Questions */}
      <div 
        ref={categoryContainerRef}
        id={`${formId}-panel-${currentCategory}`}
        role="tabpanel"
        aria-labelledby={`${formId}-tab-${currentCategory}`}
        className="space-y-6 max-h-[50vh] overflow-y-auto pr-2 scrollbar-thin"
      >
        {currentQuestions.map((question, idx) => {
          const questionNum = questions.findIndex(q => q.question_id === question.question_id) + 1;
          const isAnswered = answers[question.question_id] !== undefined;
          
          return (
            <fieldset 
              key={question.question_id} 
              className={cn(
                'border-b border-gray-100 dark:border-gray-800 pb-6 transition-opacity',
                isAnswered && 'opacity-80'
              )}
            >
              <legend className="text-gray-800 dark:text-gray-200 mb-3 w-full">
                <span className="text-gray-400 dark:text-gray-500 text-sm mr-2">Q{questionNum}.</span>
                {question.question_text}
              </legend>

              {/* Likert Scale */}
              <div 
                className="flex flex-wrap sm:flex-nowrap justify-between gap-1 sm:gap-2"
                role="radiogroup"
                aria-label={`Rating for: ${question.question_text}`}
              >
                {[1, 2, 3, 4, 5].map((value) => {
                  const isSelected = answers[question.question_id] === value;
                  return (
                    <button
                      key={value}
                      type="button"
                      role="radio"
                      aria-checked={isSelected}
                      aria-label={`${value}: ${LIKERT_LABELS[value]}`}
                      onClick={() => handleAnswer(question.question_id, value)}
                      className={cn(
                        'flex-1 min-w-[40px] py-2 px-2 sm:px-3 rounded-lg text-sm font-medium transition-all focus:outline-none focus:ring-2 focus:ring-ayurveda-gold focus:ring-offset-1 dark:focus:ring-offset-gray-900',
                        isSelected
                          ? 'bg-ayurveda-gold text-white scale-105 shadow-md'
                          : 'bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                      )}
                    >
                      {value}
                    </button>
                  );
                })}
              </div>
              <div className="flex justify-between text-xs text-gray-400 dark:text-gray-500 mt-2">
                <span>{LIKERT_LABELS[1]}</span>
                <span className="hidden sm:inline">{LIKERT_LABELS[3]}</span>
                <span>{LIKERT_LABELS[5]}</span>
              </div>
            </fieldset>
          );
        })}
      </div>

      {/* Error Message */}
      {error && (
        <div 
          role="alert" 
          className="mt-4 p-3 bg-red-50 dark:bg-red-500/10 text-red-700 dark:text-red-200 rounded-lg text-sm flex items-center gap-2"
        >
          <span aria-hidden="true">⚠️</span>
          {error}
        </div>
      )}

      {/* Submit Button */}
      <div className="mt-8 flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          {totalAnswered === questions.length 
            ? '✓ All questions answered' 
            : `${questions.length - totalAnswered} questions remaining`}
        </p>
        <button
          type="submit"
          disabled={submitting || totalAnswered < Math.ceil(questions.length * 0.5)}
          aria-busy={submitting}
          className={cn(
            'px-6 sm:px-8 py-3 rounded-xl font-semibold transition-all focus:outline-none focus:ring-2 focus:ring-ayurveda-gold focus:ring-offset-2 dark:focus:ring-offset-gray-900',
            submitting || totalAnswered < Math.ceil(questions.length * 0.5)
              ? 'bg-gray-200 dark:bg-gray-800 text-gray-400 cursor-not-allowed'
              : 'bg-ayurveda-gold text-white hover:bg-amber-600 shadow-lg hover:-translate-y-0.5'
          )}
        >
          {submitting ? (
            <span className="flex items-center gap-2">
              <span className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" aria-hidden="true"></span>
              Calculating...
            </span>
          ) : (
            'Calculate My Prakriti'
          )}
        </button>
      </div>
    </form>
  );
}
