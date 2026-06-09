import { useEffect, useRef, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { Sparkles, X, Send, RotateCcw, ArrowDown } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAtlasStore } from "../store/useAtlasStore";
import { api } from "../lib/api";
import { cn } from "../lib/utils";
import type { ChatContext, ChatMessage } from "../lib/types";

export function ChatAssistant() {
  const {
    chatOpen, setChatOpen,
    chatMessages, appendChatMessage,
    chatSending, setChatSending,
    resetChat, pushToast,
  } = useAtlasStore();
  const selectedTeam = useAtlasStore(s => s.selectedTeam);
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const ctx = useChatContext(selectedTeam);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [chatMessages, chatSending]);

  // Focus textarea when panel opens
  useEffect(() => {
    if (chatOpen) setTimeout(() => inputRef.current?.focus(), 200);
  }, [chatOpen]);

  const send = async (override?: string) => {
    const text = (override ?? input).trim();
    if (!text || chatSending) return;
    setInput("");
    const userMsg: ChatMessage = { role: "user", content: text };
    appendChatMessage(userMsg);
    setChatSending(true);
    try {
      const resp = await api.chat({ messages: [...chatMessages, userMsg], context: ctx });
      appendChatMessage({ role: "assistant", content: resp.content });
    } catch (e: any) {
      pushToast("Chat failed: " + e.message, "error");
      appendChatMessage({ role: "assistant", content: `_Sorry, couldn't respond. ${e.message}_` });
    } finally {
      setChatSending(false);
    }
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(); }
  };

  // Panel triggered by TopBar button.
  // Plain div + CSS transition — NO Framer Motion on the panel so no will-change:transform.
  // position:fixed + top:64px + h-full gives exact height = viewport - topbar.
  return (
    <>
      {/* Panel — top:64 + bottom:0 pins it to the viewport (no height calc).
          No Framer Motion = no will-change:transform = bottom:0 works correctly. */}
      <div
        className="fixed right-0 w-[420px] max-w-full z-40
                   bg-white border-l border-ink-200 shadow-[-8px_0_32px_-8px_rgba(15,23,42,.15)]
                   flex flex-col overflow-hidden"
        style={{
          top: 64,
          bottom: 0,
          transform: chatOpen ? "translateX(0)" : "translateX(100%)",
          transition: "transform 0.28s cubic-bezier(0.32,0.72,0,1)",
          pointerEvents: chatOpen ? "auto" : "none",
        }}
      >
          {/* ── Header ───────────────────────────────── */}
          <header className="flex items-center gap-3 px-4 py-3 border-b border-ink-200 bg-gradient-to-r from-brand-50 via-white to-white">
            <div className="w-8 h-8 rounded-lg bg-brand-grad text-white inline-flex items-center justify-center shadow-glow shrink-0">
              <Sparkles className="w-4 h-4" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-bold text-ink-900 leading-none">ChangePilot Assistant</div>
              <div className="text-[10.5px] text-ink-500 leading-tight mt-0.5 truncate">
                {ctx.page === "scorecard"     ? `Scorecard · ${ctx.selected_team ?? "all teams"}` :
                 ctx.page === "change-briefs" ? "CAB brief help" :
                 ctx.page === "ledger"        ? "Decision ledger" :
                 ctx.page === "insights"      ? "Platform KPIs" :
                 ctx.page === "settings"      ? "Config & onboarding" :
                 ctx.current_pr_id            ? `PR #${ctx.current_pr_id}` :
                                               "Reviews · scorecards · briefs"}
              </div>
            </div>
            {chatMessages.length > 0 && (
              <button
                onClick={resetChat}
                className="w-7 h-7 rounded-md text-ink-400 hover:text-ink-700 hover:bg-ink-100 inline-flex items-center justify-center transition-colors"
                title="Clear history"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
            )}
            <button
              onClick={() => setChatOpen(false)}
              className="w-7 h-7 rounded-md text-ink-400 hover:text-ink-700 hover:bg-ink-100 inline-flex items-center justify-center transition-colors"
              title="Close"
            >
              <X className="w-4 h-4" />
            </button>
          </header>

          {/* ── Messages — flex-1 min-h-0 scrolls internally ── */}
          <div
            ref={scrollRef}
            className="flex-1 min-h-0 overflow-y-auto px-4 py-4 space-y-3"
          >
            {chatMessages.length === 0
              ? <Welcome context={ctx} onPick={q => void send(q)} />
              : chatMessages.map((m, i) => <Bubble key={i} msg={m} />)
            }
            {chatSending && <TypingDots />}
          </div>

          {/* ── Input — shrink-0 always at bottom ── */}
          <div className="shrink-0 border-t border-ink-200 bg-ink-50 px-3 py-2.5">
            <div className="flex items-center gap-2 bg-white rounded-xl border border-ink-200 px-3 py-2
                            focus-within:border-brand-400 focus-within:shadow-glow transition-all">
              <textarea
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={onKey}
                rows={1}
                placeholder="Ask anything… Enter to send"
                className="flex-1 bg-transparent text-sm text-ink-900 placeholder:text-ink-400
                           focus:outline-none resize-none leading-5 max-h-24 overflow-y-auto"
                style={{ minHeight: 20 }}
              />
              <button
                onClick={() => void send()}
                disabled={!input.trim() || chatSending}
                className="shrink-0 inline-flex items-center justify-center w-8 h-8 rounded-lg
                           bg-brand-grad text-white shadow-soft hover:shadow-glow
                           disabled:opacity-35 disabled:cursor-not-allowed transition-all"
                title="Send (Enter)"
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </div>
            <p className="text-[10px] text-ink-400 mt-1 px-1">Shift+Enter for new line · powered by Databricks Claude</p>
          </div>
      </div>
    </>
  );
}

// ─── Context hook ────────────────────────────────────────────
function useChatContext(selectedTeam: string): ChatContext {
  const loc = useLocation();
  const params = useParams();
  let page = "inbox";
  if      (loc.pathname.startsWith("/triage"))        page = "triage";
  else if (loc.pathname.startsWith("/insights"))      page = "insights";
  else if (loc.pathname.startsWith("/scorecard"))     page = "scorecard";
  else if (loc.pathname.startsWith("/change-briefs")) page = "change-briefs";
  else if (loc.pathname.startsWith("/ledger"))        page = "ledger";
  else if (loc.pathname.startsWith("/settings"))      page = "settings";
  else if (loc.pathname.startsWith("/inbox"))         page = "inbox";
  const prId = params.prId ? parseInt(params.prId, 10) : undefined;
  return { page, current_pr_id: prId, selected_team: selectedTeam };
}

// ─── Welcome screen ──────────────────────────────────────────
const QUESTIONS: Record<string, { title: string; qs: string[] }> = {
  inbox:          { title: "Help with the inbox?",       qs: ["What's the difference between BLOCKER and MAJOR?","Which PRs should I triage first?","What threshold should I pick for auto-post?","Explain confidence scores"] },
  triage:         { title: "Help with this finding?",    qs: ["Why does this finding matter?","Should I accept or dismiss?","Show me a typical fix","What's the blast radius?"] },
  insights:       { title: "Interpreting KPIs?",         qs: ["What does auto-post rate mean?","Why is blockers-caught a leading indicator?","Which rule fires most often?","Is our review volume healthy?"] },
  scorecard:      { title: "How is the team doing?",     qs: ["Is our blocker-leakage healthy?","Why is cycle time so high?","Which dimension drives most findings?","What auto-post rate to target?"] },
  "change-briefs":{ title: "CAB brief help?",            qs: ["What does the brief contain?","How is risk level computed?","Where do I paste into ServiceNow?","Why is a section empty?"] },
  ledger:         { title: "Searching the ledger?",      qs: ["Why was this finding dismissed?","How do I filter for dismissals?","What's the audit value?","Show me what Atlas missed last month"] },
  settings:       { title: "Platform setup?",            qs: ["How do I onboard a new repo?","Where do I set the webhook secret?","How do I assign a repo to a team?","Should I enable block-on-BLOCKER?"] },
};

function Welcome({ context, onPick }: { context: ChatContext; onPick: (q: string) => void }) {
  const set = QUESTIONS[context.page ?? "inbox"] ?? QUESTIONS.inbox;
  return (
    <div className="space-y-4 pt-2">
      <div className="text-center">
        <div className="inline-flex w-11 h-11 rounded-xl bg-brand-grad items-center justify-center shadow-glow mb-2">
          <Sparkles className="w-5 h-5 text-white" />
        </div>
        <h3 className="text-[13.5px] font-bold text-ink-900">{set.title}</h3>
      </div>
      <div className="space-y-1.5">
        {set.qs.map((q, i) => (
          <motion.button
            key={q}
            onClick={() => onPick(q)}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06 }}
            className="group w-full text-left text-[12.5px] px-3 py-2.5 rounded-lg bg-ink-50 hover:bg-brand-50
                       border border-ink-200 hover:border-brand-300 transition-all flex items-center justify-between gap-2"
          >
            <span className="text-ink-700 group-hover:text-brand-700 font-medium">{q}</span>
            <ArrowDown className="w-3 h-3 text-ink-400 group-hover:text-brand-500 shrink-0 -rotate-90" />
          </motion.button>
        ))}
      </div>
    </div>
  );
}

// ─── Message bubble ──────────────────────────────────────────
function Bubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  return (
    <div className={cn("flex gap-2", isUser ? "justify-end" : "justify-start")}>
      {!isUser && (
        <div className="shrink-0 w-6 h-6 rounded-full bg-brand-grad text-white inline-flex items-center justify-center mt-0.5">
          <Sparkles className="w-3 h-3" />
        </div>
      )}
      <div className={cn(
        "max-w-[82%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed",
        isUser
          ? "bg-brand-grad text-white rounded-br-sm"
          : "bg-ink-50 text-ink-900 rounded-bl-sm border border-ink-200",
      )}>
        {isUser ? (
          <span className="whitespace-pre-wrap break-words">{msg.content}</span>
        ) : (
          <div className="prose prose-sm max-w-none
            prose-p:my-1 prose-p:text-ink-700
            prose-headings:font-bold prose-headings:text-ink-900 prose-headings:mt-2 prose-headings:mb-1
            prose-ul:my-1 prose-ul:pl-4 prose-li:my-0 prose-li:text-ink-700
            prose-strong:text-ink-900
            prose-code:text-brand-700 prose-code:bg-brand-50 prose-code:rounded prose-code:px-1 prose-code:text-[11.5px] prose-code:before:content-[''] prose-code:after:content-['']
            prose-a:text-brand-600 prose-a:no-underline hover:prose-a:underline">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Typing indicator ────────────────────────────────────────
function TypingDots() {
  return (
    <div className="flex gap-2">
      <div className="shrink-0 w-6 h-6 rounded-full bg-brand-grad text-white inline-flex items-center justify-center">
        <Sparkles className="w-3 h-3" />
      </div>
      <div className="bg-ink-50 border border-ink-200 rounded-2xl rounded-bl-sm px-3.5 py-3 inline-flex items-center gap-1.5">
        {[0, 0.15, 0.3].map(d => (
          <motion.span key={d} animate={{ y: [0, -3, 0], opacity: [0.4, 1, 0.4] }}
            transition={{ duration: 0.9, repeat: Infinity, delay: d }}
            className="w-1.5 h-1.5 rounded-full bg-brand-500 block" />
        ))}
      </div>
    </div>
  );
}
