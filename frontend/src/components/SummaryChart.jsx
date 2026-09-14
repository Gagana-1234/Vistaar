import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

function SummaryChart({ chartData, summary }) {
  if (!chartData || chartData.length === 0) {
    return (
      <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 text-center text-slate-500">
        Loading chart data...
      </div>
    );
  }

  const formatINR = (value) => {
    if (value >= 100000) return `₹${(value / 100000).toFixed(1)}L`;
    if (value >= 1000) return `₹${(value / 1000).toFixed(1)}K`;
    return `₹${Math.round(value)}`;
  };

  const categories = summary?.categories || {};
  const overall30dRevenue = summary?.overall?.total_revenue_30d || 0;
  const total7dUnits = Object.values(categories).reduce((acc, c) => acc + (c.units_sold_7d || 0), 0);

  let topCat = '-';
  let maxRev = 0;
  Object.entries(categories).forEach(([cat, stats]) => {
    if (stats.total_revenue_30d > maxRev) {
      maxRev = stats.total_revenue_30d;
      topCat = cat.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
  });

  const last7 = chartData.slice(-7);
  const rev7d = last7.reduce((acc, d) => acc + (d.revenue || 0), 0);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-100">
          <p className="text-xs text-slate-500 mb-1">Revenue (7d)</p>
          <p className="text-xl font-bold text-slate-800">{formatINR(Math.round(rev7d))}</p>
        </div>
        <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-100">
          <p className="text-xs text-slate-500 mb-1">Units Sold (7d)</p>
          <p className="text-xl font-bold text-slate-800">{Math.round(total7dUnits).toLocaleString()}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-100">
          <p className="text-xs text-slate-500 mb-1">Revenue (30d)</p>
          <p className="text-xl font-bold text-teal-600">{formatINR(Math.round(overall30dRevenue))}</p>
        </div>
        <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-100">
          <p className="text-xs text-slate-500 mb-1">Top Category</p>
          <p className="text-sm font-bold text-slate-800 leading-tight mt-1">{topCat}</p>
        </div>
      </div>

      <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-100">
        <h3 className="text-sm font-semibold text-slate-700 mb-4">Daily Revenue — Last 30 Days</h3>
        <div className="h-56 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#94a3b8' }} tickFormatter={(val) => val.slice(5)} interval={4} />
              <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} tickFormatter={formatINR} width={52} />
              <Tooltip
                formatter={(value) => [formatINR(value), 'Revenue']}
                labelFormatter={(label) => `Date: ${label}`}
                contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)', fontSize: '12px' }}
              />
              <Line type="monotone" dataKey="revenue" stroke="#0ea5e9" strokeWidth={2.5} dot={false} activeDot={{ r: 5, fill: '#0ea5e9' }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-100">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Category Snapshot</h3>
        <div className="space-y-1">
          {Object.entries(categories).map(([cat, stats]) => {
            const pct = stats.growth_pct || 0;
            const isPositive = pct >= 0;
            const coverageDays = stats.stock_coverage_days === Infinity ? 999 : (stats.stock_coverage_days || 0);
            const lowStock = coverageDays < 7;
            return (
              <div key={cat} className="flex items-center justify-between py-2 border-b border-slate-50 last:border-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-slate-700 capitalize">{cat.replace(/_/g, ' ')}</span>
                  {lowStock && <span className="text-xs bg-red-100 text-red-600 px-1.5 py-0.5 rounded-full font-medium">Low stock</span>}
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-slate-400">{coverageDays > 90 ? '90+' : Math.round(coverageDays)}d stock</span>
                  <span className={`text-xs font-semibold ${isPositive ? 'text-emerald-600' : 'text-red-500'}`}>
                    {isPositive ? '+' : ''}{pct.toFixed(1)}%
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default SummaryChart;

