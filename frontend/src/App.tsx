import { Routes, Route, Navigate } from "react-router-dom";
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { TopBar } from "./components/TopBar";
import { Sidebar } from "./components/Sidebar";
import { Toaster } from "./components/Toaster";
import { QuickReviewDrawer } from "./components/QuickReviewDrawer";
import { RepoDrawer } from "./components/RepoDrawer";
import { ChatAssistant } from "./components/ChatAssistant";
import Inbox from "./pages/Inbox";
import Triage from "./pages/Triage";
import Insights from "./pages/Insights";
import Scorecard from "./pages/Scorecard";
import CABBriefs from "./pages/CABBriefs";
import Ledger from "./pages/Ledger";
import Settings from "./pages/Settings";
import { api } from "./lib/api";
import { useAtlasStore } from "./store/useAtlasStore";

export default function App() {
  const setBackendUp = useAtlasStore(s => s.setBackendUp);

  // Heartbeat · retry aggressively on startup so slow skill-loading
  // (6-8s) doesn't leave the app permanently showing "Backend down"
  const { isError, isSuccess } = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 10_000,   // check every 10s (not 20)
    retry: 5,                  // up to 5 retries
    retryDelay: 2_000,         // 2s between retries
  });
  useEffect(() => {
    if (isError) setBackendUp(false);
    if (isSuccess) setBackendUp(true);
  }, [isError, isSuccess, setBackendUp]);

  return (
    <div className="h-screen flex flex-col bg-ink-50">
      <TopBar />
      <div className="flex-1 flex overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-[1500px] mx-auto px-8 py-7">
            <Routes>
              <Route path="/" element={<Navigate to="/inbox" replace />} />
              <Route path="/inbox" element={<Inbox />} />
              <Route path="/triage/:prId?" element={<Triage />} />
              <Route path="/insights" element={<Insights />} />
              <Route path="/scorecard" element={<Scorecard />} />
              <Route path="/change-briefs" element={<CABBriefs />} />
              <Route path="/ledger" element={<Ledger />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </div>
        </main>
      </div>
      <Toaster />
      <QuickReviewDrawer />
      <RepoDrawer />
      <ChatAssistant />
    </div>
  );
}
