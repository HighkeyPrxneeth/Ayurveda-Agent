'use client';

import { useState, useRef, useEffect, useId, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import { Copy, Edit2, RotateCw, ThumbsDown, ThumbsUp, Download, Trash2 } from 'lucide-react';
import { DoshaScore, chatWithCouncil, streamChatWithCouncil } from '@/lib/api';
import { cn } from '@/lib/utils';

interface ChatInterfaceProps {
  doshaScores?: DoshaScore | null;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  liked?: boolean | null;
  timestamp?: string;
  metadata?: {
    route?: string;
    workers_consulted?: number;
    guardrail_passed?: boolean;
  };
}

// Storage key for chat persistence
const CHAT_STORAGE_KEY = 'ayurveda_chat_history';
const HEALTH_CONDITIONS_KEY = 'ayurveda_health_conditions';

export function ChatInterface({ doshaScores }: ChatInterfaceProps) {
  const defaultMessage: Message = {
    role: 'assistant',
    content:
      "Namaste! 🙏 I'm your Ayurvedic wellness assistant. Ask me about diet recommendations, lifestyle practices, or how to balance your Doshas. I use a multi-step reasoning process to provide safe, personalized guidance.",
    timestamp: new Date().toISOString(),
  };

  const [messages, setMessages] = useState<Message[]>([defaultMessage]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [healthConditions, setHealthConditions] = useState<string[]>([]);
  const [conditionInput, setConditionInput] = useState('');
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [loadingStatus, setLoadingStatus] = useState('Thinking...');
  const [isInitialized, setIsInitialized] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const chatId = useId();

  // Load persisted data on mount
  useEffect(() => {
    try {
      const storedMessages = localStorage.getItem(CHAT_STORAGE_KEY);
      if (storedMessages) {
        const parsed = JSON.parse(storedMessages);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setMessages(parsed);
        }
      }
      const storedConditions = localStorage.getItem(HEALTH_CONDITIONS_KEY);
      if (storedConditions) {
        const parsed = JSON.parse(storedConditions);
        if (Array.isArray(parsed)) {
          setHealthConditions(parsed);
        }
      }
    } catch (error) {
      console.error('Failed to load chat history:', error);
    }
    setIsInitialized(true);
  }, []);

  // Persist messages when they change
  useEffect(() => {
    if (!isInitialized) return;
    try {
      localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages));
    } catch (error) {
      console.error('Failed to save chat history:', error);
    }
  }, [messages, isInitialized]);

  // Persist health conditions when they change
  useEffect(() => {
    if (!isInitialized) return;
    try {
      localStorage.setItem(HEALTH_CONDITIONS_KEY, JSON.stringify(healthConditions));
    } catch (error) {
      console.error('Failed to save health conditions:', error);
    }
  }, [healthConditions, isInitialized]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // Export chat history functions
  const exportAsJSON = useCallback(() => {
    const exportData = {
      exportDate: new Date().toISOString(),
      doshaScores,
      healthConditions,
      messages: messages.map(m => ({
        role: m.role,
        content: m.content,
        timestamp: m.timestamp,
        liked: m.liked,
        metadata: m.metadata,
      })),
    };
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ayurveda-chat-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [messages, doshaScores, healthConditions]);

  const exportAsMarkdown = useCallback(() => {
    const lines: string[] = [
      '# Ayurveda Chat Export',
      '',
      `**Date:** ${new Date().toLocaleDateString()}`,
      '',
    ];
    if (doshaScores) {
      lines.push('## Dosha Profile');
      lines.push(`- **Vata:** ${Math.round(doshaScores.vata * 100)}%`);
      lines.push(`- **Pitta:** ${Math.round(doshaScores.pitta * 100)}%`);
      lines.push(`- **Kapha:** ${Math.round(doshaScores.kapha * 100)}%`);
      lines.push('');
    }
    if (healthConditions.length > 0) {
      lines.push('## Health Conditions');
      healthConditions.forEach(c => lines.push(`- ${c}`));
      lines.push('');
    }
    lines.push('## Conversation');
    lines.push('');
    messages.forEach(m => {
      const role = m.role === 'user' ? '**You**' : '**Assistant**';
      lines.push(`### ${role}`);
      if (m.timestamp) {
        lines.push(`*${new Date(m.timestamp).toLocaleString()}*`);
      }
      lines.push('');
      lines.push(m.content);
      lines.push('');
      lines.push('---');
      lines.push('');
    });
    const blob = new Blob([lines.join('\n')], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ayurveda-chat-${new Date().toISOString().split('T')[0]}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }, [messages, doshaScores, healthConditions]);

  const clearHistory = useCallback(() => {
    if (window.confirm('Are you sure you want to clear all chat history?')) {
      setMessages([defaultMessage]);
      localStorage.removeItem(CHAT_STORAGE_KEY);
    }
  }, []);

  const getStatusLabel = (stage: string, detail?: string | null) => {
    switch (stage) {
      case 'router':
        return 'Routing intent...';
      case 'context':
        return 'Retrieving health context...';
      case 'supervisor':
        return 'Analyzing Dosha profile...';
      case 'worker': {
        if (!detail) return 'Consulting specialist...';
        const cleanedDetail = detail.replace(/_/g, ' ').trim();
        const hasSpecialist = cleanedDetail.toLowerCase().includes('specialist');
        return hasSpecialist
          ? `Consulting ${cleanedDetail}...`
          : `Consulting ${cleanedDetail} specialist...`;
      }
      case 'aggregation':
        return 'Synthesizing specialist insights...';
      case 'guardrail':
        return 'Running safety checks...';
      case 'response':
        return 'Crafting response...';
      case 'fast_responder':
        return 'Drafting response...';
      default:
        return 'Thinking...';
    }
  };

  const normalizeResponse = (text: string) =>
    text
      .split('\n')
      .map((line) => line.replace(/^\s*(\*\*)?get_[\w]+(\*\*)?:\s*/i, ''))
      .join('\n');

  const findLastUserIndex = (list: Message[]) =>
    list.map((msg, index) => ({ msg, index })).filter(({ msg }) => msg.role === 'user').at(-1)?.index ?? -1;

  const submitMessage = async (
    userMessage: string,
    options?: { mode: 'new' | 'edit' | 'retry'; editIndex?: number }
  ) => {
    setLoading(true);
    setLoadingStatus('Thinking...');

    setMessages((prev) => {
      const next = [...prev];

      if (options?.mode === 'new') {
        next.push({ role: 'user', content: userMessage, timestamp: new Date().toISOString() });
      }

      if (options?.mode === 'edit' && options.editIndex !== undefined) {
        const target = next[options.editIndex];
        if (target) {
          next[options.editIndex] = { ...target, content: userMessage, timestamp: new Date().toISOString() };
          if (next[options.editIndex + 1]?.role === 'assistant') {
            next.splice(options.editIndex + 1, 1);
          }
        }
      }

      if (options?.mode === 'retry') {
        const lastUserIndex = findLastUserIndex(next);
        if (lastUserIndex !== -1 && next[lastUserIndex + 1]?.role === 'assistant') {
          next.splice(lastUserIndex + 1, 1);
        }
      }

      return next;
    });

    // Build conversation history from messages (exclude the new user message we just added)
    const conversationHistory = messages
      .filter(msg => msg.content.trim())
      .map(msg => ({
        role: msg.role as 'user' | 'assistant',
        content: msg.content
      }));

    const requestPayload = {
      message: userMessage,
      dosha_scores: doshaScores as Record<string, number> | undefined,
      health_conditions: healthConditions,
      conversation_history: conversationHistory,
    };

    const statusController = new AbortController();
    const statusPromise = streamChatWithCouncil(
      requestPayload,
      (event) => {
        if (event.event === 'status') {
          setLoadingStatus(getStatusLabel(event.data.stage, event.data.detail));
        }
      },
      statusController.signal
    ).catch((error) => {
      if (error instanceof DOMException && error.name === 'AbortError') return;
    });

    try {
      const result = await chatWithCouncil(requestPayload);
      const cleanedResponse = normalizeResponse(result.response);

      setMessages((prev) => {
        const next = [...prev];
        next.push({
          role: 'assistant',
          content: cleanedResponse,
          timestamp: new Date().toISOString(),
          metadata: {
            route: result.route,
            workers_consulted: result.workers_consulted,
            guardrail_passed: result.guardrail_passed,
          },
        });
        return next;
      });
      setLoading(false);
      setEditingIndex(null);
      inputRef.current?.focus();
    } catch (e) {
      setMessages((prev) => {
        const next = [...prev];
        next.push({
          role: 'assistant',
          content: `Sorry, I encountered an error: ${e instanceof Error ? e.message : 'Unknown error'}. Please ensure the backend is running and API keys are configured.`,
          timestamp: new Date().toISOString(),
        });
        return next;
      });
      setLoading(false);
      setEditingIndex(null);
      inputRef.current?.focus();
    } finally {
      statusController.abort();
      await statusPromise;
    }
  };

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput('');

    if (editingIndex !== null) {
      const targetIndex = editingIndex;
      setEditingIndex(null);
      await submitMessage(userMessage, { mode: 'edit', editIndex: targetIndex });
      return;
    }

    await submitMessage(userMessage, { mode: 'new' });
  };

  const handleRetry = async () => {
    if (loading) return;
    const lastUserIndex = findLastUserIndex(messages);
    if (lastUserIndex === -1) return;
    await submitMessage(messages[lastUserIndex].content, { mode: 'retry' });
  };

  const handleEdit = (index: number) => {
    if (loading) return;
    setEditingIndex(index);
    setInput(messages[index].content);
    inputRef.current?.focus();
  };

  const handleCopy = async (content: string) => {
    try {
      await navigator.clipboard.writeText(content);
    } catch {
      const textarea = document.createElement('textarea');
      textarea.value = content;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
    }
  };

  const toggleReaction = (index: number, reaction: boolean) => {
    setMessages((prev) => {
      const next = [...prev];
      const current = next[index];
      if (!current) return prev;
      const nextValue = current.liked === reaction ? null : reaction;
      next[index] = { ...current, liked: nextValue };
      return next;
    });
  };

  const addCondition = () => {
    const condition = conditionInput.trim();
    if (condition && !healthConditions.includes(condition)) {
      setHealthConditions((prev) => [...prev, condition]);
      setConditionInput('');
    }
  };

  const removeCondition = (condition: string) => {
    setHealthConditions((prev) => prev.filter((c) => c !== condition));
  };

  return (
    <section
      className="bg-white dark:bg-gray-900 rounded-2xl shadow-lg flex flex-col h-full animate-fade-in-up"
      aria-labelledby={`${chatId}-title`}
    >
      {/* Header */}
      <header className="p-3 sm:p-4 border-b border-gray-100 dark:border-gray-800">
        <div className="flex items-start justify-between">
          <div>
            <h2 id={`${chatId}-title`} className="font-semibold text-gray-800 dark:text-gray-100">
              Wellness Assistant
            </h2>
            <p className="text-xs text-gray-500 dark:text-gray-400">Powered by Hierarchical Clinical Council</p>
          </div>

          {/* Export and Clear buttons */}
          <div className="flex gap-1">
            <div className="relative group">
              <button
                type="button"
                className="p-2 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-ayurveda-gold"
                aria-label="Export chat"
                aria-haspopup="true"
              >
                <Download className="h-4 w-4" />
              </button>
              <div className="absolute right-0 mt-1 w-32 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-10">
                <button
                  type="button"
                  onClick={exportAsJSON}
                  className="w-full px-3 py-2 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-t-lg"
                >
                  Export JSON
                </button>
                <button
                  type="button"
                  onClick={exportAsMarkdown}
                  className="w-full px-3 py-2 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-b-lg"
                >
                  Export Markdown
                </button>
              </div>
            </div>
            <button
              type="button"
              onClick={clearHistory}
              className="p-2 text-gray-500 dark:text-gray-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-ayurveda-gold"
              aria-label="Clear chat history"
              title="Clear chat history"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Health Conditions */}
        <div className="mt-3">
          <label htmlFor={`${chatId}-condition-input`} className="sr-only">Add health condition</label>
          {healthConditions.length > 0 && (
            <ul className="flex gap-2 flex-wrap mb-2" aria-label="Your health conditions">
              {healthConditions.map((cond) => (
                <li
                  key={cond}
                  className="px-2 py-1 bg-yellow-100 dark:bg-yellow-500/20 text-yellow-800 dark:text-yellow-200 rounded-full text-xs flex items-center gap-1"
                >
                  {cond}
                  <button
                    type="button"
                    onClick={() => removeCondition(cond)}
                    className="hover:text-yellow-900 dark:hover:text-yellow-100 focus:outline-none focus:underline"
                    aria-label={`Remove ${cond}`}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="flex gap-2">
            <input
              id={`${chatId}-condition-input`}
              type="text"
              value={conditionInput}
              onChange={(e) => setConditionInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addCondition())}
              placeholder="Add health condition..."
              className="flex-1 px-3 py-1.5 text-sm border rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 border-gray-200 dark:border-gray-700 focus:outline-none focus:ring-2 focus:ring-ayurveda-gold"
            />
            <button
              type="button"
              onClick={addCondition}
              className="px-3 py-1.5 text-sm bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-ayurveda-gold"
            >
              Add
            </button>
          </div>
        </div>
      </header>

      {/* Messages */}
      <div 
        className="flex-1 overflow-y-auto p-3 sm:p-4 space-y-2 sm:space-y-3"
        role="log"
        aria-live="polite"
        aria-label="Chat messages"
      >
        {messages.map((msg, idx) => {
          const lastUserIndex = findLastUserIndex(messages);
          const isLatestUserMessage = msg.role === 'user' && idx === lastUserIndex;
          const markdownClassName = cn(
            'chat-markdown max-w-none',
            msg.role === 'user' && 'chat-markdown-user'
          );
          const isEmptyMessage = !msg.content.trim();
          const shouldRenderAssistantPlaceholder = msg.role === 'assistant' && isEmptyMessage;
          const displayContent = msg.content;

          return (
          <div
            key={idx}
            className={cn(
              'flex',
              msg.role === 'user' ? 'justify-end' : 'justify-start'
            )}
          >
            <div
              className={cn(
                'flex flex-col gap-1 max-w-[85%] sm:max-w-[80%]',
                msg.role === 'user' ? 'items-end' : 'items-start'
              )}
            >
              {!shouldRenderAssistantPlaceholder && (
                <article
                  className={cn(
                    'rounded-2xl px-3 sm:px-4 py-2 sm:py-3 w-full',
                    msg.role === 'user'
                      ? 'bg-ayurveda-gold text-white rounded-br-none'
                      : 'bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-bl-none'
                  )}
                  aria-label={msg.role === 'user' ? 'Your message' : 'Assistant response'}
                >
                  <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]} className={markdownClassName}>
                    {displayContent}
                  </ReactMarkdown>
                  {msg.metadata && (
                    <footer className="mt-2 pt-2 border-t border-gray-200/30 dark:border-gray-700/50 text-xs text-gray-200 dark:text-gray-400">
                      {msg.metadata.route && (
                        <span className="mr-3">
                          <span aria-hidden="true">🧭</span> {msg.metadata.route}
                        </span>
                      )}
                      {msg.metadata.workers_consulted !== undefined && (
                        <span className="mr-3">
                          <span aria-hidden="true">👥</span> {msg.metadata.workers_consulted} workers
                        </span>
                      )}
                      {msg.metadata.guardrail_passed !== undefined && (
                        <span>
                          {msg.metadata.guardrail_passed
                            ? <><span aria-hidden="true">✓</span> Guardrail pass</>
                            : <><span aria-hidden="true">⚠️</span> Guardrail flagged</>}
                        </span>
                      )}
                    </footer>
                  )}
                </article>
              )}
              {!isEmptyMessage && (
                <div className="flex w-full justify-end gap-2 text-xs text-gray-500 dark:text-gray-400">
                  <button
                    type="button"
                    onClick={() => handleCopy(msg.content)}
                    className="inline-flex items-center gap-1 rounded-md px-2 py-1 hover:bg-gray-100 dark:hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-ayurveda-gold"
                  >
                    <Copy className="h-3.5 w-3.5" /> Copy
                  </button>
                  {msg.role === 'assistant' && (
                    <>
                      <button
                        type="button"
                        onClick={() => toggleReaction(idx, true)}
                        className={cn(
                          'inline-flex items-center gap-1 rounded-md px-2 py-1 hover:bg-gray-100 dark:hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-ayurveda-gold',
                          msg.liked === true && 'text-emerald-600 dark:text-emerald-400'
                        )}
                      >
                        <ThumbsUp className="h-3.5 w-3.5" /> Like
                      </button>
                      <button
                        type="button"
                        onClick={() => toggleReaction(idx, false)}
                        className={cn(
                          'inline-flex items-center gap-1 rounded-md px-2 py-1 hover:bg-gray-100 dark:hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-ayurveda-gold',
                          msg.liked === false && 'text-rose-600 dark:text-rose-400'
                        )}
                      >
                        <ThumbsDown className="h-3.5 w-3.5" /> Dislike
                      </button>
                    </>
                  )}
                  {isLatestUserMessage && (
                    <>
                      <button
                        type="button"
                        onClick={() => handleEdit(idx)}
                        disabled={loading}
                        className="inline-flex items-center gap-1 rounded-md px-2 py-1 hover:bg-gray-100 dark:hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-ayurveda-gold disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <Edit2 className="h-3.5 w-3.5" /> Edit
                      </button>
                      <button
                        type="button"
                        onClick={handleRetry}
                        disabled={loading}
                        className="inline-flex items-center gap-1 rounded-md px-2 py-1 hover:bg-gray-100 dark:hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-ayurveda-gold disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <RotateCw className="h-3.5 w-3.5" /> Retry
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
          );
        })}

        {loading && (
          <div className="flex justify-start" role="status" aria-label="Thinking...">
            <div className="bg-gray-100 dark:bg-gray-800 rounded-2xl rounded-bl-none px-4 py-3">
              <div className="flex gap-1" aria-hidden="true">
                <div className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce [animation-delay:0.2s]"></div>
                <div className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce [animation-delay:0.4s]"></div>
              </div>
              <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                {loadingStatus}
              </p>
              <span className="sr-only">{loadingStatus}</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <footer className="p-3 sm:p-4 border-t border-gray-100 dark:border-gray-800">
        <form 
          className="flex gap-2"
          onSubmit={(e) => { e.preventDefault(); handleSend(); }}
        >
          <label htmlFor={`${chatId}-message-input`} className="sr-only">Type your message</label>
          <input
            ref={inputRef}
            id={`${chatId}-message-input`}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about diet, lifestyle, or Dosha balance..."
            className="flex-1 px-3 sm:px-4 py-2 sm:py-3 border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-ayurveda-gold text-sm sm:text-base"
            disabled={loading}
            aria-describedby={loading ? `${chatId}-loading` : undefined}
          />
          {loading && <span id={`${chatId}-loading`} className="sr-only">Please wait, generating response...</span>}
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className={cn(
              'px-4 sm:px-6 py-2 sm:py-3 rounded-xl font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-ayurveda-gold focus:ring-offset-2 dark:focus:ring-offset-gray-900',
              loading || !input.trim()
                ? 'bg-gray-200 dark:bg-gray-800 text-gray-400 cursor-not-allowed'
                : 'bg-ayurveda-gold text-white hover:bg-amber-600'
            )}
          >
            {loading ? 'Sending...' : 'Send'}
          </button>
        </form>
      </footer>
    </section>
  );
}