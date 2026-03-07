import { useState } from "react";
import { searchVault } from "../api/client";
import type { ChunkInfo, SearchResponse } from "../types";
import { ErrorAlert } from "./ErrorAlert";
import { formatError } from "../utils";

function SearchResultCard({ result }: { result: ChunkInfo }) {
  return (
    <div className="bg-surface border border-border rounded p-3">
      <div className="flex items-center gap-1.5 mb-2 flex-wrap">
        <span className="font-mono text-[13px] text-accent">
          {result.note_path}
        </span>
        {result.heading && (
          <>
            <span className="text-muted text-[13px]">#</span>
            <span className="text-[13px] text-text">{result.heading}</span>
          </>
        )}
        <span className="ml-auto font-mono text-xs text-muted">
          score: {result.score.toFixed(4)}
        </span>
      </div>
      <pre className="bg-bg rounded py-2.5 px-3 font-mono text-xs leading-relaxed whitespace-pre-wrap break-words m-0">
        {result.content}
      </pre>
    </div>
  );
}

export function VaultSearch() {
  const [query, setQuery] = useState("");
  const [n, setN] = useState(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<SearchResponse | null>(null);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResponse(null);
    try {
      const result = await searchVault(query.trim(), n);
      setResponse(result);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4 max-w-[900px]">
      <form
        className="bg-surface border border-border rounded p-5 flex flex-col gap-3"
        onSubmit={handleSearch}
      >
        <label>
          <span className="block text-[13px] text-muted mb-1">
            Search passage
          </span>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            rows={4}
            placeholder="Enter a passage to find semantically similar vault content..."
            className="w-full bg-bg border border-border rounded text-text py-2 px-3 text-sm font-sans resize-y focus:outline-none focus:border-accent"
          />
        </label>
        <div className="flex items-end gap-3">
          <label className="flex flex-col gap-1">
            <span className="block text-[13px] text-muted mb-1">Results</span>
            <input
              type="number"
              value={n}
              min={1}
              max={50}
              onChange={(e) => setN(Number(e.target.value))}
              className="w-[72px] bg-bg border border-border rounded text-text py-2 px-3 text-sm font-sans focus:outline-none focus:border-accent"
            />
          </label>
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="bg-accent text-white border-none py-2 px-5 rounded text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Searching..." : "Search"}
          </button>
        </div>
      </form>

      {error && <ErrorAlert message={error} />}

      {response && (
        <div className="flex flex-col gap-3">
          <div className="text-xs text-muted font-mono">
            Model: {response.embedding_model} | Dimensions:{" "}
            {response.vector_dimensions} | Search: {response.search_type} |{" "}
            {response.count} result{response.count !== 1 ? "s" : ""} for &ldquo;
            {response.query}&rdquo;
          </div>
          {response.results.length === 0 ? (
            <div className="text-muted text-center py-8">
              No results found.
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {response.results.map((r, i) => (
                <SearchResultCard key={`${r.note_path}::${r.heading}`} result={r} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
