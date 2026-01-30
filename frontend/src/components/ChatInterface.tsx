'use client';

import { useState, useRef, useEffect, useId } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import { Copy, Edit2, RotateCw, ThumbsDown, ThumbsUp } from 'lucide-react';
import { DoshaScore, chatWithCouncil, streamChatWithCouncil } from '@/lib/api';
import { cn } from '@/lib/utils';

interface ChatInterfaceProps {
  doshaScores?: DoshaScore | null;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  liked?: boolean | null;
  metadata?: {
    route?: string;
    workers_consulted?: number;
    guardrail_passed?: boolean;
  };
}

export function ChatInterface({ doshaScores }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content:
        "Namaste! 🙏 I'm your Ayurvedic wellness assistant. Ask me about diet recommendations, lifestyle practices, or how to balance your Doshas. I use a multi-step reasoning process to provide safe, personalized guidance.",
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [healthConditions, setHealthConditions] = useState<string[]>([]);
  const [conditionInput, setConditionInput] = useState('');
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [loadingStatus, setLoadingStatus] = useState('Thinking...');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const chatId = useId();

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

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
        next.push({ role: 'user', content: userMessage });
      }

      if (options?.mode === 'edit' && options.editIndex !== undefined) {
        const target = next[options.editIndex];
        if (target) {
          next[options.editIndex] = { ...target, content: userMessage };
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
        <h2 id={`${chatId}-title`} className="font-semibold text-gray-800 dark:text-gray-100">
          Wellness Assistant
        </h2>
        <p className="text-xs text-gray-500 dark:text-gray-400">Powered by Hierarchical Clinical Council</p>

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