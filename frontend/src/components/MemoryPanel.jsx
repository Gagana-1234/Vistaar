import React, { useState, useEffect } from 'react';
import { addMemory, searchMemory, seedMemories, getCogneeStatus } from '../api';

/**
 * MemoryPanel — Cognee merchant memory interface.
 *
 * Lets the merchant:
 *  1. See stored Cognee memories
 *  2. Add new memory entries (context, preferences, events)
 *  3. Search existing memories
 *  4. Seed demo memories for the hackathon demo
 */

const MEMORY_TYPES = [
  { value: 'MERCHANT_CONTEXT',        label: '🏪 Business Context',       desc: 'How your shop normally operates' },
  { value: 'MERCHANT_PREFERENCE',     label: '⚙️ My Preference',          desc: 'How you want alerts and advice' },
  { value: 'BUSINESS_EVENT',          label: '📅 Business Event',          desc: 'Holidays, competitor openings, etc.' },
  { value: 'HISTORICAL_ALERT',        label: '📌 Historical Alert',        desc: 'Something important that happened before' },
  { value: 'PREVIOUS_RECOMMENDATION', label: '💡 Previous Recommendation', desc: 'What Vistaar advised in the past' },
];

function StatusBanner({ status }) {
  if (!status) return null;
  return (
    <div className={`px-3 py-2.5 rounded-xl text-xs flex items-start gap-2 ${status.available ? 'bg-teal-50 border border-teal-200 text-teal-800' : 'bg-slate-50 border border-slate-200 text-slate-600'}`}>
      <span className="text-base">{status.available ? '🧠' : '💤'}</span>
      <div>
        <p className="font-semibold">{status.available ? 'Cognee Memory Active' : 'Cognee Not Configured'}</p>
        <p className="mt-0.5">{status.message}</p>
        {!status.available && (
          <p className="mt-1 text-slate-500">
            To enable: add <code className="bg-slate-100 px-1 rounded">COGNEE_LLM_API_KEY</code> to <code className="bg-slate-100 px-1 rounded">backend/.env</code>
          </p>
        )}
      </div>
    </div>
  );
}

function MemoryPanel() {
  const [cogneeStatus, setCogneeStatus] = useState(null);
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [newMemory, setNewMemory] = useState('');
  const [memoryType, setMemoryType] = useState('MERCHANT_CONTEXT');
  const [adding, setAdding] = useState(false);
  const [searching, setSearching] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [addResult, setAddResult] = useState(null);
  const [seedResult, setSeedResult] = useState(null);

  useEffect(() => {
    getCogneeStatus().then(setCogneeStatus).catch(() => setCogneeStatus({ available: false, message: 'Could not reach backend.' }));
  }, []);

  const handleAddMemory = async () => {
    if (!newMemory.trim()) return;
    const textToSave = newMemory.trim();

    // Optimistic UI — show success immediately so user isn't waiting
    setAdding(true);
    setAddResult(null);
    setNewMemory('');                           // clear textarea right away
    setAddResult({ success: true, message: '⏳ Saving to Cognee memory...' });

    try {
      const result = await addMemory(textToSave, memoryType);
      // Update with real server result once it comes back
      setAddResult({
        success: result.success,
        message: result.success ? '✅ Memory saved!' : `❌ ${result.message}`,
      });
      // Auto-clear success message after 3s
      if (result.success) setTimeout(() => setAddResult(null), 3000);
    } catch (err) {
      setAddResult({ success: false, message: '❌ Error connecting to backend.' });
    } finally {
      setAdding(false);
    }
  };

  const handleSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    setSearchResults(null);
    try {
      const result = await searchMemory(query.trim());
      setSearchResults(result);
    } catch (err) {
      setSearchResults({ results: [], error: 'Search failed.' });
    } finally {
      setSearching(false);
    }
  };

  const handleSeed = async () => {
    setSeeding(true);
    setSeedResult(null);
    try {
      const result = await seedMemories();
      setSeedResult(result);
    } catch (err) {
      setSeedResult({ success: false, message: 'Seed failed.' });
    } finally {
      setSeeding(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h2 className="text-base font-bold text-slate-800 flex items-center gap-2">
          🧠 Merchant Memory
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          Teach Vistaar about your business. These memories help the AI give you smarter, personalised advice.
        </p>
      </div>

      {/* Status banner */}
      {cogneeStatus && <StatusBanner status={cogneeStatus} />}

      {/* ── Add Memory */}
      <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-100 space-y-3">
        <h3 className="text-sm font-semibold text-slate-700">Tell Vistaar Something</h3>
        <p className="text-xs text-slate-400">
          Example: "Monday sales are low because the market is closed" or "Festival season starts in October"
        </p>

        {/* Type selector */}
        <div className="grid grid-cols-1 gap-1">
          {MEMORY_TYPES.map(t => (
            <label key={t.value} className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-colors ${memoryType === t.value ? 'bg-teal-50 border-teal-300' : 'border-slate-100 hover:bg-slate-50'}`}>
              <input
                type="radio"
                name="memtype"
                value={t.value}
                checked={memoryType === t.value}
                onChange={() => setMemoryType(t.value)}
                className="accent-teal-500"
              />
              <div>
                <p className="text-xs font-semibold text-slate-700">{t.label}</p>
                <p className="text-[10px] text-slate-400">{t.desc}</p>
              </div>
            </label>
          ))}
        </div>

        {/* Text input */}
        <textarea
          value={newMemory}
          onChange={e => setNewMemory(e.target.value)}
          placeholder="Type your memory here..."
          rows={3}
          className="w-full px-3 py-2 border border-slate-200 rounded-xl text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-teal-400 resize-none"
        />

        <button
          onClick={handleAddMemory}
          disabled={adding || !newMemory.trim()}
          className="w-full py-2.5 bg-teal-500 text-white text-sm font-semibold rounded-xl hover:bg-teal-600 disabled:opacity-50 flex justify-center items-center gap-2"
        >
          {adding ? <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" /> : '💾'}
          {adding ? 'Saving...' : 'Save Memory'}
        </button>

        {/* Add result feedback */}
        {addResult && (
          <div className={`px-3 py-2 rounded-lg text-xs flex items-center gap-2 ${addResult.success ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-red-50 text-red-700 border border-red-200'}`}>
            <span>{addResult.success ? '✅' : '❌'}</span>
            {addResult.message}
          </div>
        )}
      </div>

      {/* ── Search Memory */}
      <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-100 space-y-3">
        <h3 className="text-sm font-semibold text-slate-700">Search Memories</h3>
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            placeholder="e.g. Monday sales pattern"
            className="flex-1 px-3 py-2 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-teal-400"
          />
          <button
            onClick={handleSearch}
            disabled={searching || !query.trim()}
            className="px-3 py-2 bg-teal-500 text-white text-sm font-semibold rounded-xl hover:bg-teal-600 disabled:opacity-50"
          >
            {searching ? '...' : '🔍'}
          </button>
        </div>

        {searchResults && (
          <div className="space-y-2">
            {searchResults.results?.length > 0 ? (
              searchResults.results.map((r, i) => (
                <div key={i} className="px-3 py-2 bg-teal-50 border border-teal-100 rounded-lg text-xs text-teal-800">
                  {r.text}
                </div>
              ))
            ) : (
              <p className="text-xs text-slate-400 text-center py-2">
                {searchResults.error || `No memories found for "${searchResults.query || query}"`}
              </p>
            )}
          </div>
        )}
      </div>

      {/* ── Demo Seed */}
      <div className="bg-violet-50 p-4 rounded-2xl border border-violet-200">
        <h3 className="text-sm font-semibold text-violet-800 mb-1">🎯 Hackathon Demo</h3>
        <p className="text-xs text-violet-600 mb-3">
          Seed 5 demo memories into Cognee to showcase contextual AI reasoning in the three demo scenarios.
        </p>
        <button
          onClick={handleSeed}
          disabled={seeding}
          className="w-full py-2 bg-violet-500 text-white text-sm font-semibold rounded-xl hover:bg-violet-600 disabled:opacity-50 flex justify-center items-center gap-2"
        >
          {seeding ? <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" /> : '🌱'}
          {seeding ? 'Seeding...' : 'Seed Demo Memories'}
        </button>
        {seedResult && (
          <div className={`mt-2 px-3 py-2 rounded-lg text-xs flex items-start gap-2 ${seedResult.success ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'}`}>
            <span>{seedResult.success ? '✅' : '❌'}</span>
            <span>{seedResult.message}</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default MemoryPanel;
