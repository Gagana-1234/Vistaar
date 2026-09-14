import React, { useState } from 'react';

function HistoryItem({ item }) {
  const [expanded, setExpanded] = useState(false);

  const getBadgeColors = (priority) => {
    if (!item.has_alert) return 'bg-emerald-100 text-emerald-700 border-emerald-200';
    switch (priority) {
      case 'HIGH': return 'bg-red-100 text-red-700 border-red-200';
      case 'MEDIUM': return 'bg-amber-100 text-amber-700 border-amber-200';
      default: return 'bg-sky-100 text-sky-700 border-sky-200';
    }
  };

  return (
    <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-100">
      <div className="flex justify-between items-start cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className={`px-2 py-0.5 text-[10px] font-bold rounded-full border ${getBadgeColors(item.priority)}`}>
              {!item.has_alert ? 'CLEAR' : item.priority}
            </span>
            <span className="text-xs text-slate-400">
              {new Date(item.timestamp).toLocaleString()}
            </span>
          </div>
          <p className={`text-sm font-medium text-slate-800 ${!expanded && 'truncate max-w-[250px]'}`}>
            {item.has_alert ? item.recommendation : 'No action needed'}
          </p>
        </div>
        <button className="text-slate-400 p-1">
          {expanded ? '▲' : '▼'}
        </button>
      </div>
      
      {expanded && (
        <div className="mt-3 pt-3 border-t border-slate-100">
          <p className="text-sm text-slate-600">
            {item.explanation || (item.has_alert ? 'No explanation provided.' : 'All metrics look good.')}
          </p>
          {item.signals && item.signals.length > 0 && (
            <p className="text-xs text-slate-400 mt-2">
              Based on {item.signals.length} signal(s)
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function HistoryView({ history }) {
  if (!history || history.length === 0) {
    return (
      <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100 text-center">
        <p className="text-slate-500 mb-2">No history yet.</p>
        <p className="text-sm text-slate-400">Run a check to see insights here.</p>
      </div>
    );
  }

  // Sort newest first
  const sortedHistory = [...history].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

  return (
    <div className="space-y-3 relative before:absolute before:inset-0 before:ml-5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-sky-200 before:to-transparent">
      {sortedHistory.map((item, index) => (
        <div key={item.id || index} className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
          <div className="flex items-center justify-center w-10 h-10 rounded-full border border-white bg-slate-100 text-slate-500 shadow shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2 absolute left-0 md:left-1/2 z-10">
            {item.has_alert ? (item.priority === 'HIGH' ? '⚠️' : '🔔') : '✅'}
          </div>
          <div className="w-[calc(100%-3rem)] md:w-[calc(50%-2.5rem)] ml-14 md:ml-0 md:group-odd:pr-0 md:group-even:pl-0">
            <HistoryItem item={item} />
          </div>
        </div>
      ))}
    </div>
  );
}

export default HistoryView;
