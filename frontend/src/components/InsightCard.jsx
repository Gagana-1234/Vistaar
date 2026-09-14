import React, { useState } from 'react';

function InsightCard({ latestCheck, onRefresh }) {
  const [loading, setLoading] = useState(false);

  const handleRefresh = async () => {
    setLoading(true);
    await onRefresh();
    setLoading(false);
  };

  const getPriorityColors = (priority) => {
    switch (priority) {
      case 'HIGH': return 'bg-red-100 text-red-700 border-red-200';
      case 'MEDIUM': return 'bg-amber-100 text-amber-700 border-amber-200';
      default: return 'bg-sky-100 text-sky-700 border-sky-200';
    }
  };

  return (
    <div className="space-y-4">
      {latestCheck && latestCheck.has_alert ? (
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100">
          <div className="flex items-center justify-between mb-3">
            <span className={`px-2.5 py-1 text-xs font-semibold rounded-full border ${getPriorityColors(latestCheck.priority)}`}>
              {latestCheck.priority} PRIORITY
            </span>
            <span className="text-xs text-slate-400">
              {new Date(latestCheck.timestamp || Date.now()).toLocaleString()}
            </span>
          </div>
          <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2 mb-2">
            {latestCheck.priority === 'HIGH' ? '⚠️' : '🔔'} {latestCheck.recommendation}
          </h3>
          <p className="text-slate-600 text-sm leading-relaxed">
            {latestCheck.explanation}
          </p>
        </div>
      ) : (
        <div className="bg-emerald-50 p-5 rounded-2xl shadow-sm border border-emerald-100 flex items-start gap-4">
          <div className="text-2xl mt-1">✅</div>
          <div>
            <h3 className="text-lg font-bold text-emerald-800">All Clear</h3>
            <p className="text-emerald-600 text-sm">No action needed at this time.</p>
            <p className="text-xs text-emerald-500 mt-2">
              Last checked: {new Date(latestCheck?.timestamp || Date.now()).toLocaleString()}
            </p>
          </div>
        </div>
      )}

      <button 
        onClick={handleRefresh}
        disabled={loading}
        className="w-full py-3 px-4 bg-white border border-slate-200 text-sky-600 font-semibold rounded-xl shadow-sm hover:bg-slate-50 transition-colors disabled:opacity-50 flex justify-center items-center gap-2"
      >
        {loading ? (
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-sky-600"></div>
        ) : (
          <>Run New Check <span>🔄</span></>
        )}
      </button>
    </div>
  );
}

export default InsightCard;
