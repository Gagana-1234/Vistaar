import React, { useState, useEffect } from 'react';
import { getInventory, getSignals, runDailyCheck } from '../api';

/**
 * AlertsPanel — Full alerts + inventory risk view.
 *
 * Shows:
 *  1. Active signals with severity
 *  2. Inventory risk table (days of stock per product)
 *  3. Run Now button to trigger n8n-equivalent pipeline via backend
 */

const SIGNAL_CONFIG = {
  DEMAND_SPIKE: { icon: '📈', bg: 'bg-orange-50',  border: 'border-orange-200', text: 'text-orange-700', label: 'Demand Spike' },
  DEMAND_DROP:  { icon: '📉', bg: 'bg-blue-50',    border: 'border-blue-200',   text: 'text-blue-700',   label: 'Demand Drop' },
  LOW_STOCK:    { icon: '📦', bg: 'bg-red-50',     border: 'border-red-200',    text: 'text-red-700',    label: 'Low Stock' },
};

function SignalCard({ signal }) {
  const cfg = SIGNAL_CONFIG[signal.signal_type] || SIGNAL_CONFIG.DEMAND_SPIKE;
  const hasDev = signal.signal_type !== 'LOW_STOCK';

  return (
    <div className={`p-4 rounded-xl border ${cfg.bg} ${cfg.border}`}>
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-xl">{cfg.icon}</span>
          <div>
            <p className={`text-xs font-bold uppercase tracking-wide ${cfg.text}`}>{cfg.label}</p>
            <p className="text-sm font-semibold text-slate-800 capitalize">
              {signal.category.replace(/_/g, ' ')}
            </p>
          </div>
        </div>
        {hasDev && (
          <span className={`text-sm font-bold ${signal.deviation_pct > 0 ? 'text-orange-600' : 'text-blue-600'}`}>
            {signal.deviation_pct > 0 ? '+' : ''}{signal.deviation_pct?.toFixed(1)}%
          </span>
        )}
      </div>

      <div className="grid grid-cols-3 gap-2 mt-3">
        <div className="text-center">
          <p className="text-xs text-slate-400">Actual/day</p>
          <p className="text-sm font-semibold text-slate-800">{signal.actual_avg_units?.toFixed(1)}</p>
        </div>
        <div className="text-center">
          <p className="text-xs text-slate-400">Expected/day</p>
          <p className="text-sm font-semibold text-slate-800">{signal.expected_avg_units?.toFixed(1)}</p>
        </div>
        <div className="text-center">
          <p className="text-xs text-slate-400">Stock days</p>
          <p className={`text-sm font-semibold ${signal.stock_coverage_days < 3 ? 'text-red-600' : signal.stock_coverage_days < 7 ? 'text-amber-600' : 'text-emerald-600'}`}>
            {signal.stock_coverage_days > 90 ? '90+' : signal.stock_coverage_days?.toFixed(1)}d
          </p>
        </div>
      </div>

      <p className="text-xs text-slate-500 mt-2 leading-relaxed">{signal.description}</p>
    </div>
  );
}

function InventoryTable({ inventory }) {
  if (!inventory || inventory.length === 0) return null;

  return (
    <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-100">
      <h3 className="text-sm font-semibold text-slate-700 mb-3">📦 Inventory Snapshot</h3>
      <div className="space-y-2">
        {inventory.map((item, i) => {
          const pct = Math.min(100, (item.current_stock / (item.reorder_level * 3)) * 100);
          const isLow = item.current_stock <= item.reorder_level;
          const isVeryLow = item.current_stock <= item.reorder_level * 0.5;
          return (
            <div key={i} className="space-y-1">
              <div className="flex justify-between items-center">
                <span className="text-xs text-slate-700">{item.product}</span>
                <div className="flex items-center gap-2">
                  {isVeryLow && <span className="text-[10px] bg-red-100 text-red-600 px-1.5 py-0.5 rounded-full font-bold">CRITICAL</span>}
                  {isLow && !isVeryLow && <span className="text-[10px] bg-amber-100 text-amber-600 px-1.5 py-0.5 rounded-full font-bold">LOW</span>}
                  <span className="text-xs font-semibold text-slate-600">{item.current_stock} units</span>
                </div>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-1.5">
                <div
                  className={`h-1.5 rounded-full transition-all ${isVeryLow ? 'bg-red-500' : isLow ? 'bg-amber-400' : 'bg-emerald-400'}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
      <p className="text-[10px] text-slate-400 mt-2">Reorder level shown as reference. Bar = stock vs 3× reorder level.</p>
    </div>
  );
}

function AlertsPanel() {
  const [signals, setSignals] = useState([]);
  const [inventory, setInventory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [lastRun, setLastRun] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const [sigRes, invRes] = await Promise.all([getSignals(), getInventory()]);
      setSignals(sigRes?.signals || []);
      setInventory(invRes?.inventory || []);
    } catch (err) {
      console.error('AlertsPanel load error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleRunNow = async () => {
    setRunning(true);
    try {
      const result = await runDailyCheck();
      setLastRun(result);
      await load();
    } catch (err) {
      console.error('Run check error:', err);
    } finally {
      setRunning(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-40 text-sky-500">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-current" />
      </div>
    );
  }

  const highSignals   = signals.filter(s => s.signal_type === 'LOW_STOCK' || Math.abs(s.deviation_pct) >= 30);
  const otherSignals  = signals.filter(s => !highSignals.includes(s));

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-slate-800">Active Alerts</h2>
          <p className="text-xs text-slate-400">
            {signals.length === 0 ? 'No signals detected' : `${signals.length} signal${signals.length > 1 ? 's' : ''} detected`}
          </p>
        </div>
        <button
          onClick={handleRunNow}
          disabled={running}
          className="px-3 py-1.5 bg-sky-500 text-white text-xs font-semibold rounded-lg hover:bg-sky-600 disabled:opacity-50 flex items-center gap-1.5"
        >
          {running ? <div className="animate-spin rounded-full h-3 w-3 border-b border-white" /> : '⚡'}
          {running ? 'Running...' : 'Run Now'}
        </button>
      </div>

      {/* n8n reminder pill */}
      <div className="flex items-center gap-2 px-3 py-2 bg-violet-50 border border-violet-200 rounded-xl">
        <span className="text-sm">🔁</span>
        <p className="text-xs text-violet-700">
          <strong>n8n</strong> runs this automatically every day at 9:00 AM.
          Import <code className="bg-violet-100 px-1 rounded">n8n/vistaar_workflow.json</code> to activate.
        </p>
      </div>

      {/* Last run result */}
      {lastRun && (
        <div className={`px-3 py-2 rounded-lg text-xs border ${lastRun.has_alert ? 'bg-amber-50 border-amber-200 text-amber-700' : 'bg-emerald-50 border-emerald-200 text-emerald-700'}`}>
          <strong>Last run:</strong> {lastRun.priority} — {lastRun.recommendation || 'No action needed'}
        </div>
      )}

      {/* No signals state */}
      {signals.length === 0 && (
        <div className="bg-emerald-50 p-6 rounded-2xl border border-emerald-100 text-center">
          <div className="text-3xl mb-2">✅</div>
          <p className="text-emerald-800 font-semibold">All Clear</p>
          <p className="text-sm text-emerald-600 mt-1">All metrics are within your normal range.</p>
        </div>
      )}

      {/* High priority signals */}
      {highSignals.length > 0 && (
        <div className="space-y-3">
          <p className="text-xs font-semibold text-red-600 uppercase tracking-wide flex items-center gap-1">
            <span>⚠️</span> High Priority
          </p>
          {highSignals.map((sig, i) => <SignalCard key={i} signal={sig} />)}
        </div>
      )}

      {/* Other signals */}
      {otherSignals.length > 0 && (
        <div className="space-y-3">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide flex items-center gap-1">
            <span>🔔</span> Other Signals
          </p>
          {otherSignals.map((sig, i) => <SignalCard key={i} signal={sig} />)}
        </div>
      )}

      {/* Inventory table */}
      <InventoryTable inventory={inventory} />
    </div>
  );
}

export default AlertsPanel;
