import React, { useState, useEffect } from 'react';
import { getHistory, runDailyCheck, getSummary, getChartData } from './api';
import SummaryChart from './components/SummaryChart';
import InsightCard  from './components/InsightCard';
import ChatPanel    from './components/ChatPanel';
import HistoryView  from './components/HistoryView';
import AlertsPanel  from './components/AlertsPanel';
import MemoryPanel  from './components/MemoryPanel';

/**
 * App.jsx — Vistaar frontend root.
 *
 * Tabs:
 *   Dashboard — 30-day revenue chart + category snapshot
 *   Alerts    — Active signals, inventory risk, Run Now button  [NEW]
 *   Insights  — AI-powered recommendation with full explainability
 *   Memory    — Cognee merchant memory interface                 [NEW]
 *   Chat      — Conversational Q&A
 *   History   — Past daily checks
 */

const TABS = [
  { id: 'Dashboard', label: '📊 Dashboard' },
  { id: 'Alerts',    label: '⚠️ Alerts'    },
  { id: 'Insights',  label: '💡 Insights'  },
  { id: 'Memory',    label: '🧠 Memory'    },
  { id: 'Chat',      label: '💬 Chat'      },
  { id: 'History',   label: '📋 History'   },
];

function App() {
  const [activeTab,    setActiveTab]    = useState('Dashboard');
  const [history,      setHistory]      = useState([]);
  const [latestCheck,  setLatestCheck]  = useState(null);
  const [summary,      setSummary]      = useState(null);
  const [chartData,    setChartData]    = useState([]);
  const [loading,      setLoading]      = useState(true);

  const loadData = async () => {
    setLoading(true);
    try {
      const [historyData, summaryData, chartRes] = await Promise.all([
        getHistory(),
        getSummary(),
        getChartData(),
      ]);
      const savedHistory = historyData?.history || [];
      setHistory(savedHistory);
      setLatestCheck(savedHistory[0] || null);
      setSummary(summaryData);
      setChartData(chartRes);
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  // Show alert dot on Alerts tab if there are active signals
  const hasActiveAlerts = latestCheck?.has_alert;

  return (
    <div className="max-w-2xl mx-auto min-h-screen bg-slate-50 flex flex-col font-sans">
      {/* ── Header */}
      <header className="bg-gradient-to-r from-sky-500 to-teal-500 text-white p-6 shadow-md rounded-b-3xl">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          Vistaar <span>⚡</span>
        </h1>
        <p className="text-sky-100 text-sm mt-1">
          Proactive AI Business Advisor
        </p>
        <div className="flex items-center gap-3 mt-3">
          <span className="text-xs bg-white/20 text-white px-2 py-0.5 rounded-full">n8n Powered</span>
          <span className="text-xs bg-white/20 text-white px-2 py-0.5 rounded-full">Cognee Memory</span>
          <span className="text-xs bg-white/20 text-white px-2 py-0.5 rounded-full">Groq AI</span>
        </div>
      </header>

      {/* ── Tabs */}
      <div className="px-4 pt-3 flex gap-2 overflow-x-auto pb-2 border-b border-slate-200">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`relative px-3 py-2 rounded-full whitespace-nowrap text-xs font-medium transition-colors flex-shrink-0 ${
              activeTab === tab.id
                ? 'bg-sky-500 text-white shadow-sm'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
            }`}
          >
            {tab.label}
            {/* Alert dot on Alerts tab */}
            {tab.id === 'Alerts' && hasActiveAlerts && activeTab !== 'Alerts' && (
              <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-red-500 rounded-full" />
            )}
          </button>
        ))}
      </div>

      {/* ── Main content */}
      <main className="flex-1 p-4 overflow-y-auto">
        {loading ? (
          <div className="flex justify-center items-center h-40 text-sky-500">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-current" />
          </div>
        ) : (
          <div className="space-y-4">
            {activeTab === 'Dashboard' && (
              <SummaryChart chartData={chartData} summary={summary} />
            )}
            {activeTab === 'Alerts' && (
              <AlertsPanel />
            )}
            {activeTab === 'Insights' && (
              <InsightCard latestCheck={latestCheck} onRefresh={loadData} />
            )}
            {activeTab === 'Memory' && (
              <MemoryPanel />
            )}
            {activeTab === 'Chat' && (
              <ChatPanel />
            )}
            {activeTab === 'History' && (
              <HistoryView history={history} />
            )}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
