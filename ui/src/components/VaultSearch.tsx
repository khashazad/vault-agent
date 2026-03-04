import { useState } from "react";
import { searchVault } from "../api/client";
import type { ChunkInfo, SearchResponse } from "../types";

function SearchResultCard({ result }: { result: ChunkInfo }) {
  return (
    <div className="search-result-card">
      <div className="result-card-header">
        <span className="result-path">{result.note_path}</span>
        {result.heading && (
          <>
            <span className="result-heading-sep">#</span>
            <span className="result-heading">{result.heading}</span>
          </>
        )}
        <span className="result-score">score: {result.score.toFixed(4)}</span>
      </div>
      <pre className="result-content">{result.content}</pre>
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
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="vault-search">
      <form className="search-form" onSubmit={handleSearch}>
        <label>
          <span>Search passage</span>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            rows={4}
            placeholder="Enter a passage to find semantically similar vault content..."
          />
        </label>
        <div className="search-controls">
          <label className="search-n-label">
            <span>Results</span>
            <input
              type="number"
              value={n}
              min={1}
              max={50}
              onChange={(e) => setN(Number(e.target.value))}
            />
          </label>
          <button type="submit" disabled={loading || !query.trim()}>
            {loading ? "Searching..." : "Search"}
          </button>
        </div>
      </form>

      {error && (
        <div className="error-banner">
          <strong>Error:</strong> {error}
        </div>
      )}

      {response && (
        <div className="search-results">
          <div className="search-results-meta">
            Model: {response.embedding_model} | Dimensions: {response.vector_dimensions} | Search: {response.search_type} |{" "}
            {response.count} result{response.count !== 1 ? "s" : ""} for &ldquo;{response.query}&rdquo;
          </div>
          {response.results.length === 0 ? (
            <div className="empty-state">No results found.</div>
          ) : (
            <div className="search-result-list">
              {response.results.map((r, i) => (
                <SearchResultCard key={i} result={r} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
