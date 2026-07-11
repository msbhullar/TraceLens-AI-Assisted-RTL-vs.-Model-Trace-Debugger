"use client";

import { useState } from "react";

interface Finding {
  mismatch_type: string;
  txn_ids: string[];
  description: string;
  timestamp_ns: number | null;
}

interface AnalyzeResponse {
  total_findings: number;
  first_divergence: Finding | null;
  timeline: Finding[];
  explanation: string | null;
}

const API_URL = "http://127.0.0.1:8000";

export default function Home() {
  const [rtlLog, setRtlLog] = useState("");
  const [tlmLog, setTlmLog] = useState("");
  const [includeExplanation, setIncludeExplanation] = useState(true);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAnalyze() {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(`${API_URL}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rtl_log: rtlLog,
          tlm_log: tlmLog,
          timing_threshold_ns: 100,
          include_explanation: includeExplanation,
        }),
      });

      if (!response.ok) {
        const errBody = await response.json().catch(() => null);
        throw new Error(errBody?.detail || `Request failed with status ${response.status}`);
      }

      const data: AnalyzeResponse = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 p-8">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold mb-2">TraceLens</h1>
        <p className="text-gray-400 mb-8">AI-assisted RTL vs. TLM simulation trace debugger</p>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium mb-2">RTL Log</label>
            <textarea
              className="w-full h-64 bg-gray-900 border border-gray-700 rounded p-3 font-mono text-sm"
              placeholder="Paste RTL log text here..."
              value={rtlLog}
              onChange={(e) => setRtlLog(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">TLM Log</label>
            <textarea
              className="w-full h-64 bg-gray-900 border border-gray-700 rounded p-3 font-mono text-sm"
              placeholder="Paste TLM log text here..."
              value={tlmLog}
              onChange={(e) => setTlmLog(e.target.value)}
            />
          </div>
        </div>

        <div className="flex items-center gap-4 mb-6">
          <button
            onClick={handleAnalyze}
            disabled={loading || !rtlLog || !tlmLog}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white font-medium px-6 py-2 rounded"
          >
            {loading ? "Analyzing..." : "Analyze"}
          </button>

          <label className="flex items-center gap-2 text-sm text-gray-400">
            <input
              type="checkbox"
              checked={includeExplanation}
              onChange={(e) => setIncludeExplanation(e.target.checked)}
            />
            Include LLM explanation
          </label>
        </div>

        {error && (
          <div className="bg-red-950 border border-red-800 text-red-300 rounded p-4 mb-6">
            {error}
          </div>
        )}

        {result && (
          <div className="space-y-6">
            <div className="bg-gray-900 border border-gray-700 rounded p-4">
              <div className="text-sm text-gray-400">Total Findings</div>
              <div className="text-2xl font-bold">{result.total_findings}</div>
            </div>

            {result.first_divergence && (
              <div className="bg-amber-950 border border-amber-700 rounded p-4">
                <div className="text-sm text-amber-400 font-medium mb-1">
                  First Divergence
                </div>
                <div className="font-mono text-sm">
                  <span className="text-amber-300">{result.first_divergence.mismatch_type}</span>
                  {" "}@ t={result.first_divergence.timestamp_ns}ns
                </div>
                <div className="text-gray-300 mt-1">{result.first_divergence.description}</div>
              </div>
            )}

            {result.explanation && (
              <div className="bg-gray-900 border border-gray-700 rounded p-4">
                <div className="text-sm text-gray-400 font-medium mb-2">Debug Summary</div>
                <p className="text-gray-200 leading-relaxed">{result.explanation}</p>
              </div>
            )}

            {result.timeline.length > 0 && (
              <div className="bg-gray-900 border border-gray-700 rounded p-4">
                <div className="text-sm text-gray-400 font-medium mb-3">
                  Full Timeline ({result.timeline.length})
                </div>
                <div className="space-y-2">
                  {result.timeline.map((finding, i) => (
                    <div
                      key={i}
                      className="border-l-2 border-gray-700 pl-3 py-1 font-mono text-sm"
                    >
                      <span className="text-gray-500">t={finding.timestamp_ns}ns</span>{" "}
                      <span className="text-blue-400">{finding.mismatch_type}</span>{" "}
                      <span className="text-gray-300">{finding.description}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {result.total_findings === 0 && (
              <div className="bg-green-950 border border-green-800 text-green-300 rounded p-4">
                No mismatches found — RTL and TLM traces match.
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
