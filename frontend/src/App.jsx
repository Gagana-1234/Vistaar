import React, { useState, useEffect } from 'react';
import { getHistory, runDailyCheck, getSummary, getChartData } from './api';
import SummaryChart from './components/SummaryChart';
import InsightCard from './components/InsightCard';
import ChatPanel from './components/ChatPanel';
import HistoryView from './components/HistoryView';

function App() {
  const [activeTab, setActiveTab] = useState('Dashboard');
  const [history, setHistory] = useState([]);
  const [latestCheck, setLatestCheck] = useState(null);
  const [summary, setSummary] = useState(null);
  const [chartData, setChartData] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    setLoading(true);
    try {
      const [historyData, checkData, summaryData, chartRes] = await Promise.all([
        getHistory(),
        runDailyCheck(),
        getSummary(),
        getChartData()
      ]);
      setHistory(historyData?.history || []);
      setLatestCheck(checkData);
      setSummary(summaryData);
      setChartData(chartRes);
    } catch (error) {
      console.error("Error loading data", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const tabs = ['Dashboard', 'Insights', 'Chat', 'History'];

  return (
    <div className="max-w-2xl mx-auto min-h-screen bg-slate-50 flex flex-col font-sans">
      <header className="bg-gradient-to-r from-sky-500 to-teal-500 text-white p-6 shadow-md rounded-b-3xl">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          Vistaar <span>⚡</span>
        </h1>
        <p className="text-sky-100 text-sm mt-1">AI Business Advisor</p>
      </header>

      <div className="p-4 flex gap-2 overflow-x-auto pb-2 border-b border-slate-200">
        {tabs.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 rounded-full whitespace-nowrap text-sm font-medium transition-colors ${
              activeTab === tab
                ? 'bg-sky-500 text-white shadow-sm'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      <main className="flex-1 p-4 overflow-y-auto">
        {loading ? (
          <div className="flex justify-center items-center h-40 text-sky-500">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-current"></div>
          </div>
        ) : (
          <div className="space-y-4">
            {activeTab === 'Dashboard' && (
              <SummaryChart chartData={chartData} summary={summary} />
            )}
            {activeTab === 'Insights' && (
              <InsightCard latestCheck={latestCheck} onRefresh={loadData} />
            )}
            {activeTab === 'Chat' && <ChatPanel />}
            {activeTab === 'History' && <HistoryView history={history} />}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
