"use client";

import {
  AnimatePresence,
  MotionConfig,
  motion,
} from "framer-motion";
import {
  Activity,
  ArrowDown,
  ArrowDownToLine,
  ArrowUp,
  BookOpen,
  Check,
  ChevronDown,
  CircleHelp,
  Code2,
  Copy,
  FileImage,
  FileText,
  FolderOpen,
  Globe2,
  Menu,
  MessageSquare,
  Moon,
  Paperclip,
  Plus,
  Search,
  Settings2,
  Sparkles,
  Sun,
  Trash2,
  Upload,
  X,
  Zap,
  Pencil,
  PanelLeftClose,
} from "lucide-react";
import Image from "next/image";
import {
  type ChangeEvent,
  type DragEvent,
  type FormEvent,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { MarkdownMessage } from "@/components/markdown-message";
import {
  api,
  type Agent,
  type Chat,
  type ChatMessage,
  type ChatSummary,
  type DocumentDetail,
  type DocumentSummary,
  type Health,
  type SourceEvidence,
  documentDownloadUrl,
  streamMessage,
  uploadDocument,
} from "@/lib/api";

const FALLBACK_AGENTS: Agent[] = [
  { id: "coding", name: "Coding", description: "Build, debug, and test code.", model: "qwen2.5-coder:3b" },
  { id: "research", name: "Research", description: "Explore a topic and verify useful details.", model: "qwen3.5:2b" },
  { id: "study", name: "Study", description: "Understand ideas and create learning plans.", model: "qwen3.5:2b" },
  { id: "rag", name: "RAG", description: "Find answers in your private documents.", model: "qwen3.5:2b" },
];

const AGENT_COPY: Record<string, { icon: typeof Code2; className: string; prompt: string }> = {
  coding: {
    icon: Code2,
    className: "agent-coding",
    prompt: "Write a Python function to check if a number is prime, with tests.",
  },
  research: {
    icon: Globe2,
    className: "agent-research",
    prompt: "Research how local AI agents work and summarize the key ideas.",
  },
  study: {
    icon: BookOpen,
    className: "agent-study",
    prompt: "Explain recursion simply, then make me a short quiz.",
  },
  rag: {
    icon: FolderOpen,
    className: "agent-rag",
    prompt: "Summarize the most important points in my uploaded documents.",
  },
};

const SUGGESTIONS = [
  "Research karo AI agents par aur uska quiz banao",
  "Explain neural networks in simple terms",
  "Write a Python function to check prime numbers",
  "Summarize my uploaded project notes",
  "Compare local and cloud AI models",
  "Help me plan a focused study session",
];
const QUERY_STOP_WORDS = new Set("a an and are as at be by does for from in is it of on or that the this to was were what when where which who with".split(" "));

type Toast = { title: string; detail?: string; kind: "success" | "error" };
type ConfirmState = { kind: "chat"; chat: ChatSummary } | { kind: "all" } | null;
type TextSize = "small" | "medium" | "large" | "extra-large";

function isTextSize(value: string): value is TextSize {
  return value === "small" || value === "medium" || value === "large" || value === "extra-large";
}

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function relativeGroup(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Older";
  const today = new Date();
  const start = (input: Date) => new Date(input.getFullYear(), input.getMonth(), input.getDate()).getTime();
  const days = Math.floor((start(today) - start(date)) / 86_400_000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return "Previous 7 days";
  return "Older";
}

function formatTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function makeMessage(role: ChatMessage["role"], content: string, extra: Partial<ChatMessage> = {}): ChatMessage {
  return { role, content, timestamp: new Date().toISOString(), ...extra };
}

function displayDocumentName(file: string) {
  return file.replace(/^[0-9a-f]{32}_/i, "");
}

function highlightExcerpt(text: string, question: string) {
  const keywords = [...new Set((question.match(/[\p{L}\p{N}]{3,}/gu) || [])
    .filter((word) => !QUERY_STOP_WORDS.has(word.toLocaleLowerCase())))]
    .sort((left, right) => right.length - left.length);
  if (!keywords.length) return text;
  const matcher = new RegExp(`(${keywords.map((word) => word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
  return text.split(matcher).map((part, index) =>
    keywords.some((word) => word.toLocaleLowerCase() === part.toLocaleLowerCase())
      ? <mark className="source-highlight" key={`${index}-${part}`}>{part}</mark>
      : part,
  );
}

function formatSourcePage(page: string) {
  const match = /^page\s*(\d+)$/i.exec(page);
  return match ? `Page ${match[1]}` : page;
}

function getInitialTextSize(): TextSize {
  if (typeof window === "undefined") return "medium";

  try {
    const stored = window.localStorage.getItem("ai-org-text-size");
    if (stored && isTextSize(stored)) return stored;
  } catch (error) {
    console.warn("Could not read the saved text size preference.", error);
  }

  return "medium";
}

export function Workspace() {
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [chat, setChat] = useState<Chat | null>(null);
  const [agents, setAgents] = useState<Agent[]>(FALLBACK_AGENTS);
  const [health, setHealth] = useState<Health | null>(null);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeAgent, setActiveAgent] = useState("");
  const [toast, setToast] = useState<Toast | null>(null);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [textSize, setTextSize] = useState<TextSize>(getInitialTextSize);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [documentsOpen, setDocumentsOpen] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState<DocumentDetail | null>(null);
  const [documentLoading, setDocumentLoading] = useState(false);
  const [documentError, setDocumentError] = useState("");
  const [documentSearch, setDocumentSearch] = useState("");
  const [selectedPage, setSelectedPage] = useState<string | null>(null);
  const [expandedSource, setExpandedSource] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<ConfirmState>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [isLoadingChat, setIsLoadingChat] = useState(false);

  const composerRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const isNearBottom = useRef(true);
  const abortRef = useRef<AbortController | null>(null);
  const lastMessageContent = chat?.messages[chat.messages.length - 1]?.content;

  const refreshChats = useCallback(async () => {
    const result = await api<ChatSummary[]>("/api/chats");
    setChats(result);
    return result;
  }, []);

  const refreshDocuments = useCallback(async () => {
    const result = await api<DocumentSummary[]>("/api/documents");
    setDocuments(result);
  }, []);

  const refreshHealth = useCallback(async () => {
    try {
      setHealth(await api<Health>("/api/health"));
    } catch (error) {
      setHealth({
        status: "offline",
        ollama_connected: false,
        ollama_message: error instanceof Error ? error.message : "API is unavailable.",
        models: [],
        docs_count: 0,
      });
    }
  }, []);

  const loadChat = useCallback(async (id: string) => {
    setIsLoadingChat(true);
    try {
      const selected = await api<Chat>(`/api/chats/${id}`);
      setChat(selected);
      setSidebarOpen(false);
      setExpandedAgent(null);
    } catch (error) {
      setToast({ title: "Couldn't open this chat", detail: error instanceof Error ? error.message : undefined, kind: "error" });
    } finally {
      setIsLoadingChat(false);
    }
  }, []);

  useEffect(() => {
    const preferred = window.localStorage.getItem("ai-org-theme");
    const systemTheme = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    const initial = preferred === "light" || preferred === "dark" ? preferred : systemTheme;
    setTheme(initial);
    document.documentElement.dataset.theme = initial;

    void Promise.all([
      api<Agent[]>("/api/agents").then(setAgents).catch(() => undefined),
      refreshHealth(),
      refreshDocuments(),
      refreshChats().then((items) => {
        if (items.length) void loadChat(items[0].id);
      }),
    ]).catch((error: unknown) => {
      setToast({ title: "API connection failed", detail: error instanceof Error ? error.message : undefined, kind: "error" });
    });
  }, [loadChat, refreshChats, refreshDocuments, refreshHealth]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void refreshHealth();
      void refreshDocuments().catch(() => undefined);
    }, 30_000);
    return () => window.clearInterval(timer);
  }, [refreshDocuments, refreshHealth]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("ai-org-theme", theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.dataset.textSize = textSize;
    try {
      window.localStorage.setItem("ai-org-text-size", textSize);
    } catch (error) {
      console.warn("Could not save the text size preference.", error);
    }
  }, [textSize]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 4200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    const handleShortcut = (event: globalThis.KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        void createChat();
      }
      if ((event.ctrlKey || event.metaKey) && event.key === "/") {
        event.preventDefault();
        composerRef.current?.focus();
      }
      if (event.key === "Escape" && sidebarOpen) setSidebarOpen(false);
      if (event.key === "Escape" && documentsOpen) setDocumentsOpen(false);
    };
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  });

  useEffect(() => {
    if (isNearBottom.current) scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [chat?.messages.length, lastMessageContent]);

  const groupedChats = useMemo(() => {
    const groups = new Map<string, ChatSummary[]>();
    for (const item of chats) {
      const label = relativeGroup(item.updated_at);
      groups.set(label, [...(groups.get(label) || []), item]);
    }
    return ["Today", "Yesterday", "Previous 7 days", "Older"]
      .filter((label) => groups.has(label))
      .map((label) => [label, groups.get(label)!] as const);
  }, [chats]);

  const showToast = (next: Toast) => setToast(next);

  async function createChat() {
    try {
      const created = await api<Chat>("/api/chats", { method: "POST" });
      setChat(created);
      setChats((previous) => [{ id: created.id, title: created.title, updated_at: created.updated_at }, ...previous]);
      setSidebarOpen(false);
      setInput("");
      setSelectedAgent(null);
      composerRef.current?.focus();
    } catch (error) {
      showToast({ title: "Couldn't create a chat", detail: error instanceof Error ? error.message : undefined, kind: "error" });
    }
  }

  async function submitPrompt(value: string) {
    const prompt = value.trim();
    if (!prompt || isStreaming) return;
    let activeChat = chat;
    if (!activeChat) {
      try {
        activeChat = await api<Chat>("/api/chats", { method: "POST" });
      } catch (error) {
        showToast({ title: "Couldn't create a chat", detail: error instanceof Error ? error.message : undefined, kind: "error" });
        return;
      }
    }
    setChat(activeChat);
    const userMessage = makeMessage("user", prompt);
    const assistantMessage = makeMessage("assistant", "", { pending: true, steps: [] });
    setChat((previous) => ({
      ...(previous || activeChat!),
      messages: [...(previous?.messages || activeChat!.messages), userMessage, assistantMessage],
    }));
    setInput("");
    setSelectedAgent(null);
    setActiveAgent("orchestrator");
    setIsStreaming(true);
    isNearBottom.current = true;
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      await streamMessage(activeChat.id, prompt, controller.signal, (name, data) => {
        if (name === "step") {
          setActiveAgent(String(data.agent || "orchestrator"));
          const message = String(data.message || "");
          setChat((previous) => {
            if (!previous) return previous;
            const messages = [...previous.messages];
            const last = messages[messages.length - 1];
            if (last?.pending) messages[messages.length - 1] = { ...last, events: [...(last.events || []), message] };
            return { ...previous, messages };
          });
        }
        if (name === "agent_output") {
          setChat((previous) => {
            if (!previous) return previous;
            const messages = [...previous.messages];
            const last = messages[messages.length - 1];
            if (last?.pending) {
              messages[messages.length - 1] = {
                ...last,
                steps: [...(last.steps || []), { agent: String(data.agent), output: String(data.output) }],
              };
            }
            return { ...previous, messages };
          });
        }
        if (name === "sources") {
          const sources = Array.isArray(data.sources) ? data.sources as SourceEvidence[] : [];
          setChat((previous) => {
            if (!previous) return previous;
            const messages = [...previous.messages];
            const last = messages[messages.length - 1];
            if (last?.pending) {
              messages[messages.length - 1] = {
                ...last,
                agents_used: [...new Set([...(last.agents_used || []), "rag"])],
                sources,
              };
            }
            return { ...previous, messages };
          });
        }
        if (name === "final") {
          const finalMessage: ChatMessage = {
            role: "assistant",
            content: String(data.answer || ""),
            agents_used: Array.isArray(data.agents_used) ? data.agents_used.map(String) : [],
            steps: Array.isArray(data.steps) ? data.steps as ChatMessage["steps"] : [],
            sources: Array.isArray(data.sources) ? data.sources as SourceEvidence[] : undefined,
            timestamp: new Date().toISOString(),
          };
          setChat((previous) => {
            if (!previous) return previous;
            const messages = [...previous.messages];
            messages[messages.length - 1] = finalMessage;
            return { ...previous, messages };
          });
        }
        if (name === "error") {
          setChat((previous) => {
            if (!previous) return previous;
            const messages = [...previous.messages];
            messages[messages.length - 1] = makeMessage("assistant", String(data.message || "The task couldn't be completed."));
            return { ...previous, messages };
          });
          showToast({ title: "Something went wrong", detail: String(data.message || ""), kind: "error" });
        }
        if (name === "sources_error") {
          showToast({ title: "Evidence unavailable", detail: String(data.message || ""), kind: "error" });
        }
      });
      const fresh = await api<Chat>(`/api/chats/${activeChat.id}`);
      setChat(fresh);
      await refreshChats();
    } catch (error) {
      if (controller.signal.aborted) {
        setChat((previous) => {
          if (!previous) return previous;
          const messages = [...previous.messages];
          const last = messages[messages.length - 1];
          if (last?.pending) messages[messages.length - 1] = makeMessage("assistant", "Response stopped. Send another message whenever you're ready.");
          return { ...previous, messages };
        });
      } else {
        const detail = error instanceof Error ? error.message : "The request couldn't reach the local API.";
        setChat((previous) => {
          if (!previous) return previous;
          const messages = [...previous.messages];
          const last = messages[messages.length - 1];
          if (last?.pending) messages[messages.length - 1] = makeMessage("assistant", detail);
          return { ...previous, messages };
        });
        showToast({ title: "Couldn't finish that request", detail, kind: "error" });
      }
    } finally {
      abortRef.current = null;
      setIsStreaming(false);
      setActiveAgent("");
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submitPrompt(input);
  }

  function onComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void submitPrompt(input);
    }
  }

  async function deleteSelected() {
    if (!confirm) return;
    try {
      if (confirm.kind === "all") {
        await api<void>("/api/chats", { method: "DELETE" });
        setChats([]);
        setChat(null);
        showToast({ title: "All conversations deleted", kind: "success" });
      } else {
        await api<void>(`/api/chats/${confirm.chat.id}`, { method: "DELETE" });
        const remaining = chats.filter((item) => item.id !== confirm.chat.id);
        setChats(remaining);
        if (chat?.id === confirm.chat.id) {
          if (remaining[0]) await loadChat(remaining[0].id);
          else setChat(null);
        }
        showToast({ title: "Conversation deleted", kind: "success" });
      }
    } catch (error) {
      showToast({ title: "Couldn't delete conversation", detail: error instanceof Error ? error.message : undefined, kind: "error" });
    } finally {
      setConfirm(null);
    }
  }

  async function saveRename(id: string) {
    const title = renameValue.trim();
    if (!title) return;
    try {
      const renamed = await api<Chat>(`/api/chats/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ title }),
      });
      setChats((previous) => previous.map((item) => item.id === id ? { ...item, title: renamed.title } : item));
      setChat((previous) => previous?.id === id ? { ...previous, title: renamed.title } : previous);
      setRenamingId(null);
    } catch (error) {
      showToast({ title: "Couldn't rename chat", detail: error instanceof Error ? error.message : undefined, kind: "error" });
    }
  }

  async function handleUpload(file?: File) {
    if (!file) return;
    if (file.size > 50 * 1024 * 1024) {
      showToast({ title: "File is larger than 50 MB", kind: "error" });
      return;
    }
    setUploadProgress(0);
    try {
      const result = await uploadDocument(file, setUploadProgress);
      await refreshDocuments();
      await refreshHealth();
      showToast({ title: "Document added to your workspace", detail: result.message, kind: "success" });
    } catch (error) {
      showToast({ title: "Upload or ingest failed", detail: error instanceof Error ? error.message : undefined, kind: "error" });
    } finally {
      setUploadProgress(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function openDocument(file: string, page?: string) {
    setDocumentsOpen(true);
    setSelectedDocument(null);
    setDocumentLoading(true);
    setDocumentError("");
    setDocumentSearch("");
    setSelectedPage(page || null);
    try {
      setSelectedDocument(await api<DocumentDetail>(`/api/documents/${encodeURIComponent(file)}`));
    } catch (error) {
      setDocumentError(error instanceof Error ? error.message : "Couldn't load this document.");
    } finally {
      setDocumentLoading(false);
    }
  }

  async function deleteDocument(document: DocumentSummary) {
    if (!window.confirm(`Permanently delete "${document.name}" and its extracted text?`)) return;
    try {
      await api<void>(`/api/documents/${encodeURIComponent(document.file)}`, { method: "DELETE" });
      if (selectedDocument?.file === document.file) setSelectedDocument(null);
      await Promise.all([refreshDocuments(), refreshHealth()]);
      showToast({ title: "Document deleted", detail: document.name, kind: "success" });
    } catch (error) {
      showToast({ title: "Couldn't delete document", detail: error instanceof Error ? error.message : undefined, kind: "error" });
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    void handleUpload(event.dataTransfer.files[0]);
  }

  function stopResponse() {
    abortRef.current?.abort();
  }

  const showHome = !chat?.messages.length;
  const lastUserMessage = chat?.messages.filter((message) => message.role === "user").at(-1)?.content;
  const currentAssistantIndex = chat?.messages.findIndex((message) => message.pending) ?? -1;
  const selectedDocumentIsPdf = selectedDocument?.name.toLowerCase().endsWith(".pdf") || false;
  const selectedDocumentIsImage = /\.(png|jpe?g|webp|bmp)$/i.test(selectedDocument?.name || "");

  return (
    <MotionConfig reducedMotion="user">
      <div className="workspace">
        <AnimatePresence>
          {sidebarOpen && (
            <motion.button
              className="mobile-backdrop"
              aria-label="Close navigation"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setSidebarOpen(false)}
            />
          )}
        </AnimatePresence>

        <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
          <div className="brand-row">
            <div className="brand-mark"><span /></div>
            <div className="brand-copy">
              <span className="brand-name">AI Organization</span>
              <span className="brand-caption">Your local AI team</span>
            </div>
            <button className="icon-button sidebar-collapse" aria-label="Close sidebar" onClick={() => setSidebarOpen(false)}>
              <PanelLeftClose size={17} />
            </button>
          </div>

          <button className="new-chat-button" onClick={() => void createChat()}>
            <Plus size={17} strokeWidth={2.2} />
            <span>New chat</span>
            <kbd>Ctrl K</kbd>
          </button>

          <div className="sidebar-section-heading">
            <span>Workspace</span>
            <button className="icon-button tiny" aria-label="Search conversations" onClick={() => composerRef.current?.focus()}>
              <Search size={15} />
            </button>
          </div>
          <nav className="chat-navigation" aria-label="Chat history">
            {groupedChats.length === 0 && (
              <div className="history-empty">Your conversations will show up here.</div>
            )}
            {groupedChats.map(([group, items]) => (
              <div className="history-group" key={group}>
                <div className="history-label">{group}</div>
                {items.map((item) => (
                  <div className={`history-item ${chat?.id === item.id ? "history-active" : ""}`} key={item.id}>
                    {renamingId === item.id ? (
                      <form
                        className="rename-form"
                        onSubmit={(event) => {
                          event.preventDefault();
                          void saveRename(item.id);
                        }}
                      >
                        <input
                          autoFocus
                          aria-label="New conversation name"
                          value={renameValue}
                          onChange={(event) => setRenameValue(event.target.value)}
                          onKeyDown={(event) => event.key === "Escape" && setRenamingId(null)}
                        />
                        <button className="icon-button tiny" aria-label="Save name"><Check size={14} /></button>
                      </form>
                    ) : (
                      <>
                        <button className="history-select" onClick={() => void loadChat(item.id)} title={item.title}>
                          <MessageSquare size={15} />
                          <span>{item.title || "New chat"}</span>
                        </button>
                        <div className="history-actions">
                          <button
                            className="icon-button tiny"
                            aria-label={`Rename ${item.title}`}
                            title="Rename"
                            onClick={() => {
                              setRenamingId(item.id);
                              setRenameValue(item.title);
                            }}
                          >
                            <Pencil size={13} />
                          </button>
                          <button
                            className="icon-button tiny danger-hover"
                            aria-label={`Delete ${item.title}`}
                            title="Delete"
                            onClick={() => setConfirm({ kind: "chat", chat: item })}
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                ))}
              </div>
            ))}
          </nav>

          <div className="sidebar-lower">
            <button
              className={`sidebar-link ${documentsOpen ? "sidebar-link-active" : ""}`}
              onClick={() => {
                setSidebarOpen(false);
                setDocumentsOpen(true);
              }}
              aria-haspopup="dialog"
            >
              <FolderOpen size={16} />
              <span>Documents</span>
              <span className="document-count">{documents.length}</span>
            </button>
            <button className="sidebar-link" onClick={() => setConfirm({ kind: "all" })} disabled={!chats.length}>
              <Trash2 size={16} />
              <span>Delete all chats</span>
            </button>
            <div className="system-card">
              <div className="system-title">
                <span className={`status-dot ${health?.ollama_connected ? "status-online" : "status-offline"}`} />
                <span>{health?.ollama_connected ? "Ollama connected" : "Ollama offline"}</span>
                <button className="icon-button tiny refresh-status" onClick={() => void refreshHealth()} aria-label="Refresh system status">
                  <Activity size={14} />
                </button>
              </div>
              <div className="system-meta">
                {health?.models.length ? `${health.models.length} local models` : "Local model runtime"}
                <span className="meta-separator">·</span>
                {health?.docs_count ?? documents.length} docs
              </div>
              {!health?.ollama_connected && <div className="system-warning">{health?.ollama_message || "Start Ollama to run an agent."}</div>}
            </div>
            <div className="sidebar-footer">
              <div className="local-badge"><span /> Local · private · free</div>
              <div className="sidebar-preferences">
                <label className="text-size-control">
                  <span>Text size</span>
                  <select value={textSize} onChange={(event) => {
                    if (isTextSize(event.target.value)) setTextSize(event.target.value);
                  }}>
                    <option value="small">Small</option>
                    <option value="medium">Medium</option>
                    <option value="large">Large</option>
                    <option value="extra-large">Extra large</option>
                  </select>
                </label>
                <button
                  className="theme-toggle"
                  onClick={() => setTheme((current) => current === "dark" ? "light" : "dark")}
                  aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
                  title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
                >
                  {theme === "dark" ? <Sun size={20} strokeWidth={1.8} /> : <Moon size={20} strokeWidth={1.8} />}
                </button>
              </div>
            </div>
          </div>
        </aside>

        <main className="main-panel">
          <header className="topbar">
            <button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setSidebarOpen(true)}>
              <Menu size={19} />
            </button>
            <div className="topbar-context">
              <span className="topbar-mark"><Sparkles size={14} /></span>
              <span>{chat?.title || "Your workspace"}</span>
              {chat && <ChevronDown size={14} className="context-chevron" />}
            </div>
            <div className="topbar-right">
              <div className="local-indicator"><span className={health?.ollama_connected ? "status-online" : "status-offline"} /> {health?.ollama_connected ? "Running locally" : "API ready"}</div>
              <button className="icon-button topbar-help" aria-label="Keyboard shortcuts" title="Ctrl+K: new chat · Ctrl+/: focus composer">
                <CircleHelp size={17} />
              </button>
            </div>
          </header>

          {isLoadingChat ? (
            <div className="loading-view" aria-label="Loading conversation">
              <div className="skeleton-line skeleton-short" />
              <div className="skeleton-card" />
              <div className="skeleton-card skeleton-card-small" />
            </div>
          ) : showHome ? (
            <div className="home-scroll">
              <section className="home-content">
                <motion.div
                  className="welcome-section"
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.28 }}
                >
                  <div className="eyebrow"><span className="eyebrow-line" /> A LOCAL AI WORKSPACE</div>
                  <h1>{greeting()}<br /><span>Your team is ready.</span></h1>
                  <p className="welcome-subtitle">Ek hi jagah, 4 AI departments. Aap bas task batao.</p>
                  <div className="privacy-pill"><span className="privacy-shield">✦</span> Local <i /> Private <i /> Free</div>
                </motion.div>

                <Composer
                  value={input}
                  setValue={setInput}
                  onSubmit={onSubmit}
                  onKeyDown={onComposerKeyDown}
                  onAttach={() => fileInputRef.current?.click()}
                  onStop={stopResponse}
                  isStreaming={isStreaming}
                  uploadProgress={uploadProgress}
                  onDragOver={() => setIsDragging(true)}
                  onDragLeave={() => setIsDragging(false)}
                  onDrop={onDrop}
                  isDragging={isDragging}
                  composerRef={composerRef}
                />
                <input
                  ref={fileInputRef}
                  className="visually-hidden"
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg,.txt,.md"
                  aria-label="Choose a document to upload"
                  onChange={(event: ChangeEvent<HTMLInputElement>) => void handleUpload(event.target.files?.[0])}
                />

                <div className="section-heading agent-heading">
                  <div><span className="section-overline">MEET YOUR DEPARTMENTS</span><h2>One team. Four specialties.</h2></div>
                  <span className="section-note"><Zap size={13} /> Routed automatically</span>
                </div>
                <div className="agent-grid">
                  {agents.filter((agent) => agent.id !== "orchestrator").map((agent, index) => {
                    const copy = AGENT_COPY[agent.id] || AGENT_COPY.study;
                    const Icon = copy.icon;
                    return (
                      <motion.button
                        key={agent.id}
                        className={`agent-card ${copy.className} ${selectedAgent === agent.id ? "agent-card-selected" : ""}`}
                        onClick={() => setSelectedAgent((selected) => selected === agent.id ? null : agent.id)}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.045, duration: 0.24 }}
                        whileHover={{ y: -3 }}
                        whileTap={{ scale: 0.99 }}
                        aria-expanded={selectedAgent === agent.id}
                      >
                        <div className="agent-card-top"><span className="agent-icon"><Icon size={17} /></span><span className="agent-card-arrow"><ArrowDownToLine size={14} /></span></div>
                        <span className="agent-card-name">{agent.name} Agent</span>
                        <span className="agent-card-description">{agent.description}</span>
                        <span className="model-badge"><span />{agent.model}</span>
                      </motion.button>
                    );
                  })}
                </div>
                <AnimatePresence>
                  {selectedAgent && (
                    <motion.div className="agent-example" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}>
                      <span>Try {agents.find((agent) => agent.id === selectedAgent)?.name}:</span>
                      <button onClick={() => void submitPrompt(AGENT_COPY[selectedAgent]?.prompt || SUGGESTIONS[0])}>
                        {AGENT_COPY[selectedAgent]?.prompt || SUGGESTIONS[0]} <ArrowUp size={14} />
                      </button>
                    </motion.div>
                  )}
                </AnimatePresence>

                <div className="suggestion-section">
                  <div className="section-heading compact-heading">
                    <div><span className="section-overline">A GOOD PLACE TO START</span><h2>What are we working on?</h2></div>
                    <span className="suggestion-count">06 IDEAS</span>
                  </div>
                  <div className="suggestion-grid">
                    {SUGGESTIONS.map((suggestion, index) => (
                      <button className="suggestion-chip" key={suggestion} onClick={() => void submitPrompt(suggestion)}>
                        <span className="suggestion-index">0{index + 1}</span><span>{suggestion}</span><ArrowUp size={14} />
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flow-strip">
                  <span className="flow-kicker">HOW IT WORKS</span>
                  <div className="flow-step"><span className="flow-node user-node"><MessageSquare size={13} /></span><span>You</span></div>
                  <span className="flow-connector" />
                  <div className="flow-step"><span className="flow-node orchestrator-node"><Sparkles size={13} /></span><span>Orchestrator</span></div>
                  <span className="flow-connector" />
                  <div className="flow-step"><span className="flow-node agents-node"><Zap size={13} /></span><span>Agents</span></div>
                  <span className="flow-connector" />
                  <div className="flow-step"><span className="flow-node answer-node"><Check size={13} /></span><span>Answer</span></div>
                </div>
                <div className="home-footnote"><Settings2 size={13} /> Your files and conversations stay on this device.</div>
              </section>
            </div>
          ) : (
            <div
              className="conversation-layout"
              onScroll={() => {
                const element = scrollRef.current;
                if (element) isNearBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 120;
              }}
              ref={scrollRef}
            >
              <div className="conversation-content">
                {chat?.messages.map((message, index) => {
                  if (message.role === "user") {
                    return (
                      <motion.div className="user-message-row" key={`${message.timestamp}-${index}`} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
                        <div className="user-message">
                          <p>{message.content}</p>
                          <span className="message-time">{formatTime(message.timestamp || "")}</span>
                        </div>
                      </motion.div>
                    );
                  }
                  const stepKey = `${chat?.id}-${index}`;
                  const question = chat?.messages.slice(0, index).filter((item) => item.role === "user").at(-1)?.content || "";
                  const pending = Boolean(message.pending);
                  return (
                    <motion.article className="assistant-message" key={`${message.timestamp}-${index}`} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
                      <div className="assistant-avatar"><Sparkles size={16} /></div>
                      <div className="assistant-message-body">
                        <div className="assistant-message-header">
                          <span className="assistant-name">AI Organization</span>
                          {!pending && <span className="message-time">{formatTime(message.timestamp || "")}</span>}
                        </div>
                        {message.agents_used?.length ? (
                          <div className="message-agent-badges">
                            {message.agents_used.map((name) => {
                              const style = AGENT_COPY[name]?.className || "agent-study";
                              return <span className={`agent-badge ${style}`} key={name}><span />{name}</span>;
                            })}
                          </div>
                        ) : null}
                        {pending ? (
                          <div className="live-status">
                            <span className="thinking-dots"><i /><i /><i /></span>
                            <span>{activeAgent && activeAgent !== "orchestrator" ? `${activeAgent[0].toUpperCase()}${activeAgent.slice(1)} Agent kaam kar raha hai...` : "Orchestrator plan bana raha hai..."}</span>
                          </div>
                        ) : (
                          <MarkdownMessage content={message.content} />
                        )}
                        {message.agents_used?.includes("rag") && (
                          <section className="sources-section" aria-label={`Sources (${message.sources?.length || 0})`}>
                            <h3><FolderOpen size={14} /> Sources ({message.sources?.length || 0})</h3>
                            {message.sources?.length ? <div className="source-list">
                              {message.sources?.map((source) => {
                                const sourceKey = `${stepKey}-${source.chunk_id}`;
                                const expanded = expandedSource === sourceKey;
                                const score = Math.max(0, Math.min(100, Math.round(source.score * 100)));
                                return (
                                  <article className={`source-card ${expanded ? "source-card-expanded" : ""}`} key={sourceKey}>
                                    <button
                                      className="source-card-trigger"
                                      type="button"
                                      aria-expanded={expanded}
                                      onClick={() => setExpandedSource(expanded ? null : sourceKey)}
                                    >
                                      <FileText size={16} aria-hidden="true" />
                                      <span className="source-file" title={displayDocumentName(source.file)}>{displayDocumentName(source.file)}</span>
                                      <span className="source-page">{formatSourcePage(source.page)}</span>
                                      <span className="source-score">{score}%</span>
                                      <ChevronDown size={14} className={expanded ? "chevron-open" : ""} />
                                    </button>
                                    {expanded && (
                                      <div className="source-card-detail">
                                        <p>{highlightExcerpt(source.text, question)}</p>
                                        <button className="source-open-page" type="button" onClick={() => void openDocument(source.file, source.page)}>
                                          <BookOpen size={13} /> Open full page
                                        </button>
                                      </div>
                                    )}
                                  </article>
                                );
                              })}
                            </div> : <p className="sources-empty">No document excerpts were retrieved.</p>}
                          </section>
                        )}
                        {pending && Boolean(message.events?.length || message.steps?.length) && (
                          <div className="live-events">
                            {[...(message.events || []), ...(message.steps || []).map((step) => `${step.agent}: ${step.output}`)].slice(-3).map((event, eventIndex) => (
                              <div key={eventIndex}><span />{event}</div>
                            ))}
                          </div>
                        )}
                        {!pending && Boolean(message.steps?.length) && (
                          <div className="agent-steps-wrap">
                            <button className="steps-toggle" onClick={() => setExpandedAgent(expandedAgent === stepKey ? null : stepKey)} aria-expanded={expandedAgent === stepKey}>
                              <ChevronDown size={14} className={expandedAgent === stepKey ? "chevron-open" : ""} />
                              {expandedAgent === stepKey ? "Hide agent steps" : `Show agent steps · ${message.steps?.length}`}
                            </button>
                            <AnimatePresence initial={false}>
                              {expandedAgent === stepKey && (
                                <motion.div className="agent-steps" initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}>
                                  {message.steps?.map((step, stepIndex) => (
                                    <div className="step-card" key={`${step.agent}-${stepIndex}`}>
                                      <div className="step-card-title"><span className={`step-dot ${AGENT_COPY[step.agent]?.className || "agent-study"}`} />{step.agent} output</div>
                                      <MarkdownMessage content={step.output} />
                                    </div>
                                  ))}
                                </motion.div>
                              )}
                            </AnimatePresence>
                          </div>
                        )}
                        {!pending && (
                          <div className="message-actions">
                            <button
                              className="icon-button tiny"
                              aria-label="Copy response"
                              title="Copy response"
                              onClick={() => {
                                void navigator.clipboard.writeText(message.content).then(() => showToast({ title: "Response copied", kind: "success" }));
                              }}
                            ><Copy size={14} /></button>
                            {index === currentAssistantIndex || index === (chat?.messages.length || 0) - 1 ? (
                              <button className="icon-button tiny regenerate-button" aria-label="Regenerate response" title="Regenerate" disabled={!lastUserMessage || isStreaming} onClick={() => lastUserMessage && void submitPrompt(lastUserMessage)}>
                                <ArrowDown size={14} />
                              </button>
                            ) : null}
                          </div>
                        )}
                      </div>
                    </motion.article>
                  );
                })}
              </div>
            </div>
          )}

          {!showHome && (
            <div className="conversation-composer-dock">
              <Composer
                value={input}
                setValue={setInput}
                onSubmit={onSubmit}
                onKeyDown={onComposerKeyDown}
                onAttach={() => fileInputRef.current?.click()}
                onStop={stopResponse}
                isStreaming={isStreaming}
                uploadProgress={uploadProgress}
                onDragOver={() => setIsDragging(true)}
                onDragLeave={() => setIsDragging(false)}
                onDrop={onDrop}
                isDragging={isDragging}
                composerRef={composerRef}
                compact
              />
              <input
                ref={fileInputRef}
                className="visually-hidden"
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.txt,.md"
                aria-label="Choose a document to upload"
                onChange={(event: ChangeEvent<HTMLInputElement>) => void handleUpload(event.target.files?.[0])}
              />
              <div className="composer-footnote">AI responses can be inaccurate. Your workspace stays on this device.</div>
            </div>
          )}
        </main>

        <AnimatePresence>
          {documentsOpen && (
            <motion.div
              className="documents-overlay"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onMouseDown={(event) => event.target === event.currentTarget && setDocumentsOpen(false)}
            >
              <motion.section
                className={`documents-dialog ${selectedDocument ? "documents-dialog-detail" : ""}`}
                role="dialog"
                aria-modal="true"
                aria-labelledby="documents-title"
                initial={{ opacity: 0, y: 12, scale: 0.99 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 8 }}
              >
                <header className="documents-dialog-header">
                  <div>
                    <span className="section-overline">KNOWLEDGE BASE</span>
                    <h2 id="documents-title">Documents</h2>
                  </div>
                  <button className="icon-button" aria-label="Close documents" onClick={() => setDocumentsOpen(false)}><X size={17} /></button>
                </header>
                <div className="documents-dialog-content">
                  <section className="documents-table-panel" aria-label="Uploaded documents">
                    <div className="documents-panel-heading">
                      <span>{documents.length} {documents.length === 1 ? "document" : "documents"}</span>
                      <button className="button-secondary" type="button" onClick={() => fileInputRef.current?.click()}><Upload size={13} /> Add files</button>
                    </div>
                    {documents.length ? (
                      <div className="documents-table-scroll">
                        <table className="documents-table">
                          <thead><tr><th>File</th><th>Pages</th><th>Chunks</th><th>Uploaded</th><th><span className="visually-hidden">Actions</span></th></tr></thead>
                          <tbody>
                            {documents.map((document) => {
                              const image = /\.(png|jpe?g|webp|bmp)$/i.test(document.name);
                              return (
                                <tr key={document.file}>
                                  <td>
                                    <button className="document-open" type="button" onClick={() => void openDocument(document.file)}>
                                      {image ? <FileImage size={16} /> : <FileText size={16} />}
                                      <span title={document.name}>{document.name}</span>
                                    </button>
                                  </td>
                                  <td>{document.pages}</td>
                                  <td>{document.chunks}</td>
                                  <td>{document.uploaded_at ? new Date(document.uploaded_at).toLocaleDateString() : "—"}</td>
                                  <td>
                                    <button className="icon-button tiny danger-hover" type="button" aria-label={`Delete ${document.name}`} title={`Delete ${document.name}`} onClick={() => void deleteDocument(document)}>
                                      <Trash2 size={14} />
                                    </button>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="documents-empty-state">
                        <FolderOpen size={22} />
                        <strong>No documents yet</strong>
                        <span>Upload a PDF, image, text, or Markdown file to get started.</span>
                      </div>
                    )}
                  </section>
                  <section className="document-viewer" aria-label="Document preview and extracted text">
                    {documentLoading ? (
                      <div className="document-viewer-empty">Loading extracted text…</div>
                    ) : documentError ? (
                      <div className="document-viewer-empty document-viewer-error">{documentError}</div>
                    ) : selectedDocument ? (
                      <>
                        <header className="document-viewer-header">
                          <div>
                            <strong title={selectedDocument.name}>{selectedDocument.name}</strong>
                            <span>{selectedDocument.pages.length} {selectedDocument.pages.length === 1 ? "page" : "pages"} · OCR / extracted text</span>
                          </div>
                          <a className="button-secondary document-download" href={documentDownloadUrl(selectedDocument.file)} download={selectedDocument.name} aria-label={`Download ${selectedDocument.name}`}>
                            <ArrowDownToLine size={14} /> Download
                          </a>
                        </header>
                        <label className="document-search">
                          <Search size={14} />
                          <input value={documentSearch} onChange={(event) => setDocumentSearch(event.target.value)} placeholder="Search extracted text" aria-label="Search extracted text" />
                        </label>
                        {(selectedDocumentIsPdf || selectedDocumentIsImage) && (
                          <div className="document-preview">
                            {selectedDocumentIsPdf ? (
                              <iframe title={`Preview of ${selectedDocument.name}`} src={documentDownloadUrl(selectedDocument.file)} />
                            ) : (
                              <Image
                                src={documentDownloadUrl(selectedDocument.file)}
                                alt={`Preview of ${selectedDocument.name}`}
                                width={720}
                                height={400}
                                unoptimized
                              />
                            )}
                          </div>
                        )}
                        <div className="extracted-pages">
                          {selectedDocument.pages
                            .filter((page) => !documentSearch || page.text.toLocaleLowerCase().includes(documentSearch.toLocaleLowerCase()))
                            .map((page, pageIndex) => (
                              <article
                                className={`extracted-page ${selectedPage === page.page ? "extracted-page-selected" : ""}`}
                                key={`${page.page}-${pageIndex}`}
                                ref={(element) => {
                                  if (element && selectedPage === page.page) element.scrollIntoView({ block: "nearest" });
                                }}
                              >
                                <h3>{page.page}</h3>
                                <pre>{highlightExcerpt(page.text, documentSearch)}</pre>
                              </article>
                            ))}
                          {!selectedDocument.pages.length && <p className="document-viewer-empty">No extracted text was stored for this file.</p>}
                          {selectedDocument.pages.length > 0 && !selectedDocument.pages.some((page) => !documentSearch || page.text.toLocaleLowerCase().includes(documentSearch.toLocaleLowerCase())) && (
                            <p className="document-viewer-empty">No text matches your search.</p>
                          )}
                        </div>
                      </>
                    ) : (
                      <div className="document-viewer-empty"><FileText size={22} /><span>Select a document to view its extracted pages.</span></div>
                    )}
                  </section>
                </div>
              </motion.section>
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {confirm && (
            <motion.div className="modal-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onMouseDown={(event) => event.target === event.currentTarget && setConfirm(null)}>
              <motion.div className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title" initial={{ opacity: 0, y: 10, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 8 }}>
                <div className="modal-icon"><Trash2 size={19} /></div>
                <h2 id="confirm-title">{confirm.kind === "all" ? "Delete all conversations?" : "Delete this conversation?"}</h2>
                <p>{confirm.kind === "all" ? "This permanently removes all saved web chats. This can't be undone." : `“${confirm.chat.title}” and its messages will be permanently removed.`}</p>
                <div className="modal-actions">
                  <button className="button-secondary" onClick={() => setConfirm(null)}>Cancel</button>
                  <button className="button-danger" onClick={() => void deleteSelected()}>Delete</button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {toast && (
            <motion.div className={`toast toast-${toast.kind}`} role="status" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 12 }}>
              <span className="toast-icon">{toast.kind === "success" ? <Check size={16} /> : <X size={16} />}</span>
              <span><strong>{toast.title}</strong>{toast.detail && <small>{toast.detail}</small>}</span>
              <button className="icon-button tiny" aria-label="Dismiss notification" onClick={() => setToast(null)}><X size={14} /></button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </MotionConfig>
  );
}

type ComposerProps = {
  value: string;
  setValue: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  onAttach: () => void;
  onStop: () => void;
  isStreaming: boolean;
  uploadProgress: number | null;
  onDragOver: () => void;
  onDragLeave: () => void;
  onDrop: (event: DragEvent<HTMLDivElement>) => void;
  isDragging: boolean;
  composerRef: React.RefObject<HTMLTextAreaElement | null>;
  compact?: boolean;
};

function Composer({
  value,
  setValue,
  onSubmit,
  onKeyDown,
  onAttach,
  onStop,
  isStreaming,
  uploadProgress,
  onDragOver,
  onDragLeave,
  onDrop,
  isDragging,
  composerRef,
  compact = false,
}: ComposerProps) {
  return (
    <div
      className={`composer-wrap ${compact ? "composer-compact" : ""} ${isDragging ? "composer-dragging" : ""}`}
      onDragOver={(event) => { event.preventDefault(); onDragOver(); }}
      onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node)) onDragLeave(); }}
      onDrop={onDrop}
    >
      <form className="composer-box" onSubmit={onSubmit}>
        {isDragging && <div className="drop-overlay"><Upload size={19} /> Drop your file to add it to the knowledge base</div>}
        <div className="searching-documents" aria-label="Searching in all documents">
          <FolderOpen size={13} /><span>Searching in:</span><strong>All documents</strong>
        </div>
        <textarea
          ref={composerRef}
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
            event.currentTarget.style.height = "auto";
            event.currentTarget.style.height = `${Math.min(event.currentTarget.scrollHeight, 180)}px`;
          }}
          onKeyDown={onKeyDown}
          placeholder="Ask your team anything..."
          aria-label="Message AI Organization"
          rows={1}
          disabled={isStreaming}
        />
        {uploadProgress !== null && (
          <div className="upload-progress">
            <div><span><Upload size={13} /> Adding document</span><span>{uploadProgress}%</span></div>
            <div className="progress-track"><span style={{ width: `${uploadProgress}%` }} /></div>
          </div>
        )}
        <div className="composer-toolbar">
          <div className="composer-tools">
            <button className="attach-button" type="button" onClick={onAttach} aria-label="Attach a document" title="Add PDF, image, text, or Markdown">
              <Paperclip size={16} /><span>Add files</span>
            </button>
            <span className="composer-hint">PDF · PNG · JPG · TXT · MD</span>
          </div>
          {isStreaming ? (
            <button className="stop-button" type="button" onClick={onStop}><span /> Stop</button>
          ) : (
            <button className="send-button" type="submit" disabled={!value.trim()} aria-label="Send message" title="Send message">
              <span className="send-label">Send</span><ArrowUp size={16} />
            </button>
          )}
        </div>
      </form>
      {!compact && <div className="composer-shortcut"><span>↵</span> to send <i /> <span>⇧ ↵</span> for a new line <i /> <span>Ctrl /</span> to focus</div>}
    </div>
  );
}
