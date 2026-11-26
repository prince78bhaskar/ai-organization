export type Agent = {
  id: string;
  name: string;
  description: string;
  model: string;
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  agents_used?: string[];
  steps?: { agent: string; output: string }[];
  sources?: SourceEvidence[];
  events?: string[];
  timestamp?: string;
  pending?: boolean;
};

export type SourceEvidence = {
  file: string;
  page: string;
  text: string;
  score: number;
  chunk_id: string;
};

export type DocumentSummary = {
  file: string;
  name: string;
  pages: number;
  chunks: number;
  uploaded_at: string | null;
};

export type DocumentDetail = {
  file: string;
  name: string;
  pages: { page: string; text: string }[];
  chunks: { page: string; text: string; chunk_id: string }[];
};

export type Chat = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
};

export type ChatSummary = Pick<Chat, "id" | "title" | "updated_at">;

export type Health = {
  status: string;
  ollama_connected: boolean;
  ollama_message: string;
  models: string[];
  docs_count: number;
};

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export function documentDownloadUrl(file: string) {
  return `${API_URL}/api/documents/${encodeURIComponent(file)}/download`;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...init?.headers,
    },
    cache: "no-store",
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail || body.message || message;
    } catch {
      // Keep the useful HTTP status when an error body isn't JSON.
    }
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function streamMessage(
  chatId: string,
  content: string,
  signal: AbortSignal,
  onEvent: (name: string, data: Record<string, unknown>) => void,
) {
  const response = await fetch(`${API_URL}/api/chats/${chatId}/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ content }),
    signal,
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail || body.message || message;
    } catch {
      // Fall back to the HTTP status.
    }
    throw new Error(message);
  }
  if (!response.body) throw new Error("Streaming isn't supported by this browser.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() || "";
    for (const block of blocks) {
      let event = "message";
      const data: string[] = [];
      for (const line of block.split(/\r?\n/)) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        if (line.startsWith("data:")) data.push(line.slice(5).trim());
      }
      if (data.length) onEvent(event, JSON.parse(data.join("\n")) as Record<string, unknown>);
    }
    if (done) break;
  }
}

export async function uploadDocument(file: File, onProgress: (progress: number) => void) {
  const form = new FormData();
  form.append("file", file);
  return new Promise<{ name: string; message: string }>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${API_URL}/api/upload`);
    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) onProgress(Math.max(1, Math.round((event.loaded / event.total) * 90)));
    });
    request.addEventListener("load", () => {
      let payload: { name?: string; message?: string; detail?: string };
      try {
        payload = JSON.parse(request.responseText) as typeof payload;
      } catch {
        reject(new Error(`Upload failed (${request.status}).`));
        return;
      }
      if (request.status < 200 || request.status >= 300) {
        reject(new Error(payload.detail || `Upload failed (${request.status}).`));
        return;
      }
      onProgress(100);
      resolve({ name: payload.name || file.name, message: payload.message || "Document added." });
    });
    request.addEventListener("error", () => reject(new Error("Upload couldn't reach the local API.")));
    request.addEventListener("abort", () => reject(new Error("Upload was cancelled.")));
    request.send(form);
  });
}
