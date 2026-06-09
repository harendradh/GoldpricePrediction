import { create } from "zustand";
import type { ChatMessage } from "../lib/types";

type ToastVariant = "default" | "success" | "warning" | "error";
interface ToastMsg { id: number; text: string; variant: ToastVariant; }

interface AtlasState {
  toasts: ToastMsg[];
  pushToast: (text: string, variant?: ToastVariant) => void;
  dismissToast: (id: number) => void;

  quickReviewOpen: boolean;
  setQuickReviewOpen: (open: boolean) => void;

  repoDrawerOpen: boolean;
  setRepoDrawerOpen: (open: boolean) => void;

  backendUp: boolean;
  setBackendUp: (up: boolean) => void;

  // Active team scope · drives Inbox / Triage / Insights filters
  selectedTeam: string;
  setSelectedTeam: (team: string) => void;

  // Chat assistant
  chatOpen: boolean;
  setChatOpen: (open: boolean) => void;
  chatMessages: ChatMessage[];
  chatSending: boolean;
  appendChatMessage: (msg: ChatMessage) => void;
  setChatSending: (sending: boolean) => void;
  resetChat: () => void;
}

let _toastId = 0;

export const useAtlasStore = create<AtlasState>((set, get) => ({
  toasts: [],
  pushToast: (text, variant = "default") => {
    const id = ++_toastId;
    set(s => ({ toasts: [...s.toasts, { id, text, variant }] }));
    setTimeout(() => { get().dismissToast(id); }, 3200);
  },
  dismissToast: id => set(s => ({ toasts: s.toasts.filter(t => t.id !== id) })),

  quickReviewOpen: false,
  setQuickReviewOpen: open => set({ quickReviewOpen: open }),

  repoDrawerOpen: false,
  setRepoDrawerOpen: open => set({ repoDrawerOpen: open }),

  backendUp: true,
  setBackendUp: up => set({ backendUp: up }),

  selectedTeam: "all",
  setSelectedTeam: team => set({ selectedTeam: team }),

  chatOpen: false,
  setChatOpen: open => set({ chatOpen: open }),
  chatMessages: [],
  chatSending: false,
  appendChatMessage: msg => set(s => ({ chatMessages: [...s.chatMessages, msg] })),
  setChatSending: sending => set({ chatSending: sending }),
  resetChat: () => set({ chatMessages: [], chatSending: false }),
}));
