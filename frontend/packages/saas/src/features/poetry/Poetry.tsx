/**
 * Poetry - Browse, search, and discover classical Chinese poems.
 * Owner: Jason
 *
 * Features:
 *   - Semantic search via ChromaDB vector
 *   - Browse/filter by dynasty, author, theme
 *   - Random discovery mode
 *   - Poem detail view with full content
 *
 * Uses SaaS brand tokens + Tailwind utility classes.
 */
import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { createSaasApiClient } from "../../api/saasApiClient";
import { IS_OVERSEAS } from "../../config/region";

interface Poem {
  id: number;
  title: string;
  author: string;
  dynasty: string;
  theme: string;
  content_preview?: string;
  content?: string;
  tags?: string;
}

interface BrowseResult {
  items: Poem[];
  total: number;
  page: number;
  per_page: number;
}

interface SearchResult {
  results: {
    title: string;
    author: string;
    dynasty: string;
    content: string;
    theme: string;
  }[];
  query: string;
  count: number;
}

interface PoetryStats {
  total: number;
  dynasties: { name: string; count: number }[];
  themes: { name: string; count: number }[];
}

type ViewMode = "browse" | "search" | "discover";

export default function Poetry() {
  // Core state
  const [mode, setMode] = useState<ViewMode>("browse");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult | null>(null);
  const [browseResult, setBrowseResult] = useState<BrowseResult | null>(null);
  const [randomPoems, setRandomPoems] = useState<Poem[]>([]);
  const [stats, setStats] = useState<PoetryStats | null>(null);

  // Filters
  const [dynastyFilter, setDynastyFilter] = useState<string | null>(null);
  const [authorFilter, _setAuthorFilter] = useState<string>("");
  const [themeFilter, _setThemeFilter] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  // Detail modal
  const [selectedPoem, setSelectedPoem] = useState<Poem | null>(null);
  const [poemDetail, setPoemDetail] = useState<Poem | null>(null);

  // Loading states
  const [loading, setLoading] = useState(false);

  const api = useCallback(
    () => createSaasApiClient(),
    [],
  );

  // Load stats on mount
  useEffect(() => {
    api()
      .get<PoetryStats>("/v1/poetry/stats")
      .then(setStats)
      .catch(() => {});
  }, [api]);

  // Browse when filters change
  const fetchBrowse = useCallback(
    async (p: number) => {
      setLoading(true);
      try {
        const params: Record<string, string | number> = { page: p, per_page: 20 };
        if (dynastyFilter) params.dynasty = dynastyFilter;
        if (authorFilter) params.author = authorFilter;
        if (themeFilter) params.theme = themeFilter;

        const result = await api().get<BrowseResult>("/v1/poetry/browse", params);
        setBrowseResult(result);
        setPage(p);
      } catch (e) {
        console.error("Browse failed:", e);
      } finally {
        setLoading(false);
      }
    },
    [api, dynastyFilter, authorFilter, themeFilter]
  );

  // Initial browse load
  useEffect(() => {
    if (mode === "browse") fetchBrowse(1);
  }, [mode, dynastyFilter, themeFilter, fetchBrowse]);

  // Search
  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    try {
      const result = await api().get<SearchResult>("/v1/poetry/search", {
        q: searchQuery,
        n: 5,
      });
      setSearchResults(result);
      setMode("search");
    } catch (e) {
      console.error("Search failed:", e);
    } finally {
      setLoading(false);
    }
  }, [api, searchQuery]);

  // Random discovery
  const fetchRandom = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api().get<{ results: Poem[]; count: number }>(
        "/v1/poetry/random",
        { count: 6 }
      );
      setRandomPoems(result.results);
      setMode("discover");
    } catch (e) {
      console.error("Random failed:", e);
    } finally {
      setLoading(false);
    }
  }, [api]);

  // Poem detail
  const fetchDetail = useCallback(
    async (poemId: number) => {
      try {
        const poem = await api().get<Poem>(`/v1/poetry/${poemId}`);
        setPoemDetail(poem);
      } catch (e) {
        console.error("Detail fetch failed:", e);
      }
    },
    [api]
  );

  const handlePoemClick = (poem: Poem) => {
    setSelectedPoem(poem);
    fetchDetail(poem.id);
  };

  const closeDetail = () => {
    setSelectedPoem(null);
    setPoemDetail(null);
  };

  // Dynasty chips from stats
  const dynastyChips = stats?.dynasties.slice(0, 8) || [];

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-1">
        <h1
          className="text-2xl font-bold"
          style={{ color: "var(--color-text-primary)" }}
        >
          诗词文库
        </h1>
        {IS_OVERSEAS && (
          <Link
            to="/poetry/challenge"
            className="text-sm shrink-0 no-underline px-3 py-1.5 rounded-lg text-white"
            style={{ backgroundColor: "var(--color-primary)" }}
          >
            Translate Challenge
          </Link>
        )}
      </div>
      <p
        className="text-sm mb-5"
        style={{ color: "var(--color-text-secondary)" }}
      >
        {stats
          ? `收录 ${stats.total.toLocaleString()} 诗词，${stats.dynasties.length} 个朝代`
          : "浏览与搜索古典诗词"}
      </p>

      {/* Mode switcher + Search */}
      <div
        className="flex items-center gap-3 mb-5 rounded-lg p-4"
        style={{ backgroundColor: "var(--color-bg-card)", boxShadow: "var(--shadow-sm)" }}
      >
        <div
          className="flex rounded-md overflow-hidden border text-xs shrink-0"
          style={{ borderColor: "var(--color-border)" }}
        >
          {(["browse", "search", "discover"] as ViewMode[]).map((m) => (
            <button
              key={m}
              onClick={() => {
                setMode(m);
                if (m === "discover") fetchRandom();
              }}
              className="px-3 py-1.5 border-none cursor-pointer transition-colors"
              style={{
                backgroundColor: mode === m ? "var(--color-primary)" : "transparent",
                color: mode === m ? "#fff" : "var(--color-text-secondary)",
              }}
            >
              {m === "browse" ? "浏览" : m === "search" ? "搜索" : "发现"}
            </button>
          ))}
        </div>

        {/* Search input */}
        <div className="flex flex-1 gap-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="输入诗词名、作者或关键词..."
            className="flex-1 px-4 py-2 text-sm rounded-lg border outline-none"
            style={{
              borderColor: "var(--color-border)",
              color: "var(--color-text-primary)",
            }}
            onFocus={(e) => (e.target.style.borderColor = "var(--color-primary)")}
            onBlur={(e) => (e.target.style.borderColor = "var(--color-border)")}
          />
          <button
            onClick={handleSearch}
            disabled={loading}
            className="px-4 py-2 text-sm rounded-lg text-white cursor-pointer border-none shrink-0 disabled:opacity-40"
            style={{ backgroundColor: "var(--color-primary)" }}
          >
            {loading ? "搜索中..." : "搜索"}
          </button>
        </div>
      </div>

      {/* Dynasty filter chips */}
      {mode === "browse" && dynastyChips.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          <button
            onClick={() => setDynastyFilter(null)}
            className="px-3 py-1 text-xs rounded-full border cursor-pointer transition-colors"
            style={{
              backgroundColor: dynastyFilter === null ? "var(--color-primary)" : "transparent",
              color: dynastyFilter === null ? "#fff" : "var(--color-text-secondary)",
              borderColor: dynastyFilter === null ? "var(--color-primary)" : "var(--color-border)",
            }}
          >
            全部
          </button>
          {dynastyChips.map((d) => (
            <button
              key={d.name}
              onClick={() => setDynastyFilter(d.name === dynastyFilter ? null : d.name)}
              className="px-3 py-1 text-xs rounded-full border cursor-pointer transition-colors"
              style={{
                backgroundColor: dynastyFilter === d.name ? "var(--color-primary)" : "transparent",
                color: dynastyFilter === d.name ? "#fff" : "var(--color-text-secondary)",
                borderColor: dynastyFilter === d.name ? "var(--color-primary)" : "var(--color-border)",
              }}
            >
              {d.name} ({d.count.toLocaleString()})
            </button>
          ))}
        </div>
      )}

      {/* Content area */}
      {/* BROWSE MODE */}
      {mode === "browse" && browseResult && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mb-4">
            {browseResult.items.map((poem) => (
              <div
                key={poem.id}
                onClick={() => handlePoemClick(poem)}
                className="rounded-lg p-4 cursor-pointer transition-shadow hover:shadow-md"
                style={{
                  backgroundColor: "var(--color-bg-card)",
                  boxShadow: "var(--shadow-sm)",
                  borderLeft: "3px solid var(--color-primary)",
                }}
              >
                <h3
                  className="text-sm font-bold mb-1"
                  style={{ color: "var(--color-text-primary)" }}
                >
                  {poem.title}
                </h3>
                <p className="text-xs mb-2" style={{ color: "var(--color-text-secondary)" }}>
                  {poem.dynasty} · {poem.author}
                </p>
                <p
                  className="text-xs leading-relaxed"
                  style={{ color: "var(--color-text-muted)" }}
                >
                  {poem.content_preview}
                </p>
              </div>
            ))}
          </div>

          {/* Pagination */}
          {browseResult.total > browseResult.per_page && (
            <div className="flex items-center justify-center gap-2 mt-4">
              <button
                onClick={() => fetchBrowse(page - 1)}
                disabled={page <= 1}
                className="px-3 py-1 text-sm rounded border cursor-pointer disabled:opacity-30"
                style={{ borderColor: "var(--color-border)", color: "var(--color-text-secondary)" }}
              >
                上一页
              </button>
              <span className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                {page} / {Math.ceil(browseResult.total / browseResult.per_page)} 页
                · 共 {browseResult.total.toLocaleString()} 首
              </span>
              <button
                onClick={() => fetchBrowse(page + 1)}
                disabled={page >= Math.ceil(browseResult.total / browseResult.per_page)}
                className="px-3 py-1 text-sm rounded border cursor-pointer disabled:opacity-30"
                style={{ borderColor: "var(--color-border)", color: "var(--color-text-secondary)" }}
              >
                下一页
              </button>
            </div>
          )}
        </>
      )}

      {/* SEARCH MODE */}
      {mode === "search" && searchResults && (
        <div className="space-y-3">
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            搜索 "{searchResults.query}" — 找到 {searchResults.count} 首
          </p>
          {searchResults.results.map((r, i) => (
            <div
              key={i}
              className="rounded-lg p-5"
              style={{
                backgroundColor: "var(--color-bg-card)",
                boxShadow: "var(--shadow-sm)",
              }}
            >
              <h3 className="text-base font-bold mb-1" style={{ color: "var(--color-text-primary)" }}>
                {r.title}
              </h3>
              <p className="text-xs mb-3" style={{ color: "var(--color-text-secondary)" }}>
                {r.dynasty} · {r.author} · {r.theme || "未分类"}
              </p>
              <div
                className="text-sm leading-loose whitespace-pre-wrap"
                style={{ color: "var(--color-text-primary)" }}
              >
                {r.content}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* DISCOVER MODE */}
      {mode === "discover" && randomPoems.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium" style={{ color: "var(--color-text-primary)" }}>
              随机发现
            </h2>
            <button
              onClick={fetchRandom}
              className="text-sm px-3 py-1 rounded border cursor-pointer"
              style={{
                borderColor: "var(--color-primary)",
                color: "var(--color-primary)",
              }}
            >
              再来一组 ⟳
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {randomPoems.map((poem) => (
              <div
                key={poem.id}
                onClick={() => handlePoemClick(poem)}
                className="rounded-lg p-5 cursor-pointer transition-shadow hover:shadow-md"
                style={{
                  backgroundColor: "var(--color-bg-card)",
                  boxShadow: "var(--shadow-sm)",
                }}
              >
                <h3 className="text-base font-bold mb-1" style={{ color: "var(--color-text-primary)" }}>
                  {poem.title}
                </h3>
                <p className="text-xs mb-3" style={{ color: "var(--color-text-secondary)" }}>
                  {poem.dynasty} · {poem.author}
                </p>
                <div
                  className="text-sm leading-loose whitespace-pre-wrap"
                  style={{ color: "var(--color-text-muted)" }}
                >
                  {poem.content_preview}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {mode === "browse" && !loading && browseResult && browseResult.items.length === 0 && (
        <div className="flex flex-col items-center py-12" style={{ color: "var(--color-text-muted)" }}>
          <span className="text-4xl opacity-20 mb-2">📖</span>
          <p className="mb-1">诗词文库正在筹备中</p>
          <p className="text-xs opacity-60">请稍后再来浏览经典诗词</p>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-12" style={{ color: "var(--color-text-muted)" }}>
          <span className="text-sm">加载中...</span>
        </div>
      )}

      {/* Detail Modal */}
      {selectedPoem && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ backgroundColor: "rgba(0,0,0,0.4)" }}
          onClick={closeDetail}
        >
          <div
            className="rounded-xl p-6 max-w-lg w-full mx-4 relative overflow-hidden"
            style={{
              backgroundColor: "var(--color-bg-card)",
              boxShadow: "var(--shadow-lg)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close button */}
            <button
              onClick={closeDetail}
              className="absolute top-3 right-3 text-lg bg-transparent border-none cursor-pointer"
              style={{ color: "var(--color-text-muted)" }}
            >
              ✕
            </button>

            <h2 className="text-xl font-bold mb-2" style={{ color: "var(--color-text-primary)" }}>
              {selectedPoem.title}
            </h2>
            <p className="text-sm mb-4" style={{ color: "var(--color-text-secondary)" }}>
              {selectedPoem.dynasty} · {selectedPoem.author}
              {selectedPoem.theme && ` · ${selectedPoem.theme}`}
            </p>

            {/* Full content */}
            <div
              className="text-base leading-loose whitespace-pre-wrap max-h-[60vh] overflow-y-auto"
              style={{ color: "var(--color-text-primary)" }}
            >
              {poemDetail?.content || selectedPoem.content_preview || "加载中..."}
            </div>

            {/* Tags */}
            {(poemDetail?.tags || selectedPoem.tags) && (
              <div className="flex flex-wrap gap-1 mt-4">
                {(poemDetail?.tags || selectedPoem.tags || "")
                  .split(",")
                  .filter(Boolean)
                  .map((tag) => (
                    <span
                      key={tag}
                      className="px-2 py-0.5 text-xs rounded"
                      style={{
                        backgroundColor: "var(--color-primary-light)",
                        color: "var(--color-primary)",
                      }}
                    >
                      {tag}
                    </span>
                  ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
