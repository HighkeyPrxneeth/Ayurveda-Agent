/**
 * API Client for communicating with the FastAPI backend
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';
const DEFAULT_TIMEOUT_MS = 60000;

async function fetchWithTimeout(input: RequestInfo | URL, init: RequestInit = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}

// Types matching backend Pydantic models
export interface QuestionAnswer {
  question_id: string;
  answer_value: number;
}

export interface DoshaScore {
  vata: number;
  pitta: number;
  kapha: number;
}

export interface AssessmentResponse {
  scores: DoshaScore;
  dominant_dosha: string;
  constitution_type: string;
}

export interface Question {
  question_id: string;
  question_text: string;
  category: string;
  weight: number;
}

export interface TreatmentRequest {
  query: string;
  dosha_scores?: Record<string, number>;
  health_conditions?: string[];
}

export interface TreatmentResponse {
  response: string;
  safety_notes: string[];
  is_safe: boolean;
  steps_executed: number;
  disclaimer: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatRequest {
  message: string;
  user_id?: string;
  dosha_scores?: Record<string, number>;
  health_conditions?: string[];
  conversation_history?: ChatMessage[];
}

export interface ChatResponse {
  response: string;
  route: string;
  guardrail_passed: boolean;
  guardrail_violations: Array<Record<string, unknown>>;
  workers_consulted: number;
  disclaimer: string;
}

export type ChatStreamEvent =
  | { event: 'status'; data: { stage: string; detail?: string | null } }
  | { event: 'delta'; data: { text: string } }
  | { event: 'done'; data: ChatResponse }
  | { event: 'error'; data: { message: string } };

// API Functions
export async function getQuestions(): Promise<Question[]> {
  const res = await fetchWithTimeout(`${API_BASE}/api/v1/questions`);
  if (!res.ok) throw new Error('Failed to fetch questions');
  return res.json();
}

export async function assessDosha(answers: QuestionAnswer[]): Promise<AssessmentResponse> {
  const res = await fetchWithTimeout(`${API_BASE}/api/v1/assess-dosha`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers }),
  });
  if (!res.ok) throw new Error('Failed to assess Dosha');
  return res.json();
}

export async function assessVitals(vitals: {
  heart_rate?: number;
  hrv?: number;
  skin_temp?: number;
  respiration_rate?: number;
}): Promise<AssessmentResponse> {
  const res = await fetchWithTimeout(`${API_BASE}/api/v1/assess-vitals`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(vitals),
  });
  if (!res.ok) throw new Error('Failed to assess vitals');
  return res.json();
}

export async function generateTreatmentPlan(
  request: TreatmentRequest
): Promise<TreatmentResponse> {
  const res = await fetchWithTimeout(`${API_BASE}/api/v1/generate-plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  }, DEFAULT_TIMEOUT_MS);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to generate plan');
  }
  return res.json();
}

export async function chatWithCouncil(
  request: ChatRequest
): Promise<ChatResponse> {
  const res = await fetchWithTimeout(`${API_BASE}/api/v1/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  }, DEFAULT_TIMEOUT_MS);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to process chat');
  }
  return res.json();
}

export async function streamChatWithCouncil(
  request: ChatRequest,
  onEvent: (event: ChatStreamEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
    signal,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to process chat stream');
  }

  if (!res.body) {
    throw new Error('Streaming response not available');
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split(/\r?\n\r?\n/);
    buffer = parts.pop() ?? '';

    for (const part of parts) {
      const lines = part.replace(/\r/g, '').split('\n').filter(Boolean);
      let eventName = 'message';
      const dataLines: string[] = [];

      for (const line of lines) {
        if (line.startsWith('event:')) {
          eventName = line.slice(6).trim();
          continue;
        }
        if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).trimStart());
        }
      }

      const data = dataLines.join('\n');
      if (!data) continue;

      try {
        const parsed = JSON.parse(data);
        let normalizedEvent = eventName as ChatStreamEvent['event'];
        if (normalizedEvent === 'message') {
          if ('response' in parsed) normalizedEvent = 'done';
          else if ('text' in parsed) normalizedEvent = 'delta';
          else if ('stage' in parsed) normalizedEvent = 'status';
        }
        onEvent({ event: normalizedEvent, data: parsed } as ChatStreamEvent);
      } catch {
        if (eventName === 'error') {
          onEvent({ event: 'error', data: { message: data } });
        } else {
          onEvent({ event: 'delta', data: { text: data } });
        }
      }
    }
  }

  if (buffer.trim()) {
    const lines = buffer.replace(/\r/g, '').split('\n').filter(Boolean);
    let eventName = 'message';
    const dataLines: string[] = [];

    for (const line of lines) {
      if (line.startsWith('event:')) {
        eventName = line.slice(6).trim();
        continue;
      }
      if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trimStart());
      }
    }

    const data = dataLines.join('\n');
    if (data) {
      try {
        const parsed = JSON.parse(data);
        let normalizedEvent = eventName as ChatStreamEvent['event'];
        if (normalizedEvent === 'message') {
          if ('response' in parsed) normalizedEvent = 'done';
          else if ('text' in parsed) normalizedEvent = 'delta';
          else if ('stage' in parsed) normalizedEvent = 'status';
        }
        onEvent({ event: normalizedEvent, data: parsed } as ChatStreamEvent);
      } catch {
        if (eventName === 'error') {
          onEvent({ event: 'error', data: { message: data } });
        } else {
          onEvent({ event: 'delta', data: { text: data } });
        }
      }
    }
  }
}
