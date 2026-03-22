import { useEffect, useState, useCallback } from "react";
import { useDateFilter } from "../lib/DateFilterContext";
import {
  getTrends,
  getTrendsYoY,
  getTrendsPatterns,
} from "../lib/api";
import type {
  TimeseriesResponse,
  YoYResponse,
  PatternsResponse,
} from "../lib/api";
import { formatCompactCurrency, formatNumber } from "../lib/formatters";

// Color palette for series
const SERIES_COLORS = [
  { bg: "bg-blue-500", text: "text-blue-400", hex: "#3b82f6" },
  { bg: "bg-emerald-500", text: "text-emerald-400", hex: "#10b981" },
  { bg: "bg-purple-500", text: "text-purple-400", hex: "#a855f7" },
  { bg: "bg-amber-500", text: "text-amber-400", hex: "#f59e0b" },
  { bg: "bg-cyan-500", text: "text-cyan-400", hex: "#06b6d4" },
  { bg: "bg-rose-500", text: "text-rose-400", hex: "#f43f5e" },
  { bg: "bg-indigo-500", text: "text-indigo-400", hex: "#6366f1" },
  { bg: "bg-orange-500", text: "text-orange-400", hex: "#f97316" },
];

const DIMENSION_OPTIONS = [
  { value: "category", label: "Category" },
  { value: "department", label: "Department" },
  { value: "procurement_type", label: "Procurement Type" },
  { value: "dv_subcategory", label: "DV Subcategory" },
  { value: "vendor", label: "Vendor" },
];

const TOP_N_OPTIONS = [5, 8, 10, 15];

const MONTH_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function monthLabel(year: number, month: number) {
  return `${MONTH_SHORT[month - 1]} ${String(year).slice(2)}`;
}

export default function Trends() {
  const { applyToParams, dateFilter } = useDateFilter();
  const [dimension, setDimension] = useState("category");
  const [topN, setTopN] = useState(8);

  const [timeseries, setTimeseries] = useState<TimeseriesResponse | null>(null);
  const [yoy, setYoY] = useState<YoYResponse | null>(null);
  const [patterns, setPatterns] = useState<PatternsResponse | null>(null);

  const [loadingTs, setLoadingTs] = useState(true);
  const [loadingYoY, setLoadingYoY] = useState(true);
  const [loadingPatterns, setLoadingPatterns] = useState(true);

  const [errorTs, setErrorTs] = useState<string | null>(null);
  const [errorYoY, setErrorYoY] = useState<string | null>(null);
  const [errorPatterns, setErrorPatterns] = useState<string | null>(null);

  const fetchAll = useCallback(() => {
    const baseParams = applyToParams({ dimension, top_n: String(topN) });

    setLoadingTs(true);
    setErrorTs(null);
    getTrends(baseParams)
      .then(setTimeseries)
      .catch((e) => setErrorTs(e.message))
      .finally(() => setLoadingTs(false));

    setLoadingYoY(true);
    setErrorYoY(null);
    getTrendsYoY(baseParams)
      .then(setYoY)
      .catch((e) => setErrorYoY(e.message))
      .finally(() => setLoadingYoY(false));

    setLoadingPatterns(true);
    setErrorPatterns(null);
    getTrendsPatterns(applyToParams({ dimension }))
      .then(setPatterns)
      .catch((e) => setErrorPatterns(e.message))
      .finally(() => setLoadingPatterns(false));
  }, [dimension, topN, dateFilter.startDate, dateFilter.endDate]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  return (
    <div>
      {/* Header + Controls */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Trends & Analytics</h1>
        <p className="text-slate-500 text-sm mt-1">
          Spending patterns, year-over-year comparisons, and anomaly detection
        </p>
      </div>

      {/* Controls bar */}
      <div className="card p-4 mb-6 flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Dimension
          </label>
          <select
            value={dimension}
            onChange={(e) => setDimension(e.target.value)}
            className="bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500 min-w-[180px]"
          >
            {DIMENSION_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Top N
          </label>
          <div className="flex gap-1">
            {TOP_N_OPTIONS.map((n) => (
              <button
                key={n}
                onClick={() => setTopN(n)}
                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                  topN === n
                    ? "bg-blue-600/20 text-blue-400 border border-blue-500/40"
                    : "text-slate-500 border border-slate-700 hover:text-slate-300 hover:border-slate-600"
                }`}
              >
                {n}
              </button>
            ))}
          </div>
        </div>
        <div className="ml-auto text-xs text-slate-600">
          Analyzing by{" "}
          <span className="text-blue-400 font-medium">
            {DIMENSION_OPTIONS.find((d) => d.value === dimension)?.label}
          </span>
        </div>
      </div>

      {/* Section 1: Spending Timeline */}
      <SectionWrapper title="Spending Timeline" loading={loadingTs} error={errorTs}>
        {timeseries && <TimelineChart data={timeseries} />}
      </SectionWrapper>

      {/* Section 2: Year-over-Year */}
      <SectionWrapper title="Year-over-Year Comparison" loading={loadingYoY} error={errorYoY}>
        {yoy && <YoYTable data={yoy} />}
      </SectionWrapper>

      {/* Section 3: Patterns & Insights */}
      <SectionWrapper title="Patterns & Insights" loading={loadingPatterns} error={errorPatterns}>
        {patterns && <PatternsSection data={patterns} />}
      </SectionWrapper>
    </div>
  );
}

/* ─── Section wrapper with independent loading ─── */

function SectionWrapper({
  title,
  loading,
  error,
  children,
}: {
  title: string;
  loading: boolean;
  error: string | null;
  children: React.ReactNode;
}) {
  return (
    <div className="card p-5 mb-6">
      <h2 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">
        {title}
      </h2>
      {loading ? (
        <div className="flex items-center justify-center h-40">
          <div className="text-center">
            <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
            <p className="text-slate-500 text-xs">Loading...</p>
          </div>
        </div>
      ) : error ? (
        <div className="flex items-center justify-center h-40">
          <div className="text-center">
            <p className="text-red-400 text-sm font-medium mb-1">Failed to load</p>
            <p className="text-slate-500 text-xs">{error}</p>
          </div>
        </div>
      ) : (
        children
      )}
    </div>
  );
}

/* ─── Section 1: Timeline Chart ─── */

function TimelineChart({ data }: { data: TimeseriesResponse }) {
  const { monthly_totals, series } = data;
  if (!monthly_totals || monthly_totals.length === 0) {
    return <p className="text-slate-500 text-sm">No timeseries data available.</p>;
  }

  const maxAmount = Math.max(...monthly_totals.map((m) => m.amount));

  return (
    <div>
      {/* Legend */}
      <div className="flex flex-wrap gap-3 mb-4">
        {series.map((s, i) => (
          <div key={s.name} className="flex items-center gap-1.5">
            <div
              className={`w-3 h-3 rounded-sm ${SERIES_COLORS[i % SERIES_COLORS.length].bg}`}
            />
            <span className="text-xs text-slate-400 truncate max-w-[150px]" title={s.name}>
              {s.name}
            </span>
            <span className="text-xs text-slate-600">
              ({formatCompactCurrency(s.total)})
            </span>
          </div>
        ))}
      </div>

      {/* Monthly total bar chart - hero viz */}
      <div className="h-64 flex items-end gap-[2px] overflow-x-auto pb-6 relative">
        {monthly_totals.map((m, idx) => {
          const pct = maxAmount > 0 ? (m.amount / maxAmount) * 100 : 0;
          // Build stacked segments for this month
          const segments = buildSegments(m, series, idx);

          return (
            <div
              key={`${m.year}-${m.month}`}
              className="flex-1 min-w-[12px] max-w-[40px] flex flex-col items-center group relative"
              style={{ height: "100%" }}
            >
              {/* Tooltip on hover */}
              <div className="hidden group-hover:block absolute bottom-full mb-1 z-10 bg-slate-900 border border-slate-700 rounded px-2 py-1.5 text-xs whitespace-nowrap shadow-lg">
                <p className="text-white font-medium">{monthLabel(m.year, m.month)}</p>
                <p className="text-slate-400">
                  Total: {formatCompactCurrency(m.amount)}
                </p>
                <p className="text-slate-500">{formatNumber(m.count)} payments</p>
              </div>
              {/* Bar */}
              <div
                className="w-full flex flex-col justify-end rounded-t overflow-hidden"
                style={{ height: `${pct}%`, minHeight: m.amount > 0 ? "2px" : "0px" }}
              >
                {segments.length > 0 ? (
                  segments.map((seg, si) => (
                    <div
                      key={si}
                      className={`w-full ${seg.color} opacity-90`}
                      style={{ height: `${seg.pct}%`, minHeight: seg.pct > 0 ? "1px" : "0px" }}
                    />
                  ))
                ) : (
                  <div className="w-full h-full bg-blue-500/60 rounded-t" />
                )}
              </div>
              {/* X-axis label - show every few months */}
              {(idx === 0 || m.month === 1 || m.month === 7) && (
                <span className="text-[9px] text-slate-600 mt-1 absolute -bottom-5 whitespace-nowrap">
                  {monthLabel(m.year, m.month)}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Sparklines for each series */}
      <div className="mt-6 space-y-2">
        {series.map((s, i) => {
          const color = SERIES_COLORS[i % SERIES_COLORS.length];
          const seriesMax = Math.max(...s.data.map((d) => d.amount), 1);
          return (
            <div key={s.name} className="flex items-center gap-3">
              <div className="w-[140px] flex-shrink-0 truncate">
                <span className={`text-xs ${color.text}`} title={s.name}>
                  {s.name}
                </span>
              </div>
              <div className="flex-1 flex items-end gap-[1px] h-6">
                {s.data.map((d, di) => {
                  const h = seriesMax > 0 ? (d.amount / seriesMax) * 100 : 0;
                  return (
                    <div
                      key={di}
                      className={`flex-1 ${color.bg} opacity-70 rounded-t`}
                      style={{ height: `${h}%`, minHeight: d.amount > 0 ? "1px" : "0px" }}
                    />
                  );
                })}
              </div>
              <span className="text-xs text-slate-500 w-[70px] text-right flex-shrink-0">
                {formatCompactCurrency(s.total)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Build stacked color segments for a single month bar */
function buildSegments(
  monthTotal: { year: number; month: number; amount: number },
  series: TimeseriesResponse["series"],
  _idx: number
) {
  if (monthTotal.amount <= 0) return [];
  const segments: { color: string; pct: number }[] = [];
  let accountedFor = 0;

  series.forEach((s, i) => {
    const point = s.data.find(
      (d) => d.year === monthTotal.year && d.month === monthTotal.month
    );
    if (point && point.amount > 0) {
      const pct = (point.amount / monthTotal.amount) * 100;
      segments.push({
        color: SERIES_COLORS[i % SERIES_COLORS.length].bg,
        pct,
      });
      accountedFor += point.amount;
    }
  });

  // Remaining "other" portion
  const remaining = monthTotal.amount - accountedFor;
  if (remaining > 0) {
    segments.push({
      color: "bg-slate-600",
      pct: (remaining / monthTotal.amount) * 100,
    });
  }

  return segments;
}

/* ─── Section 2: Year-over-Year Table ─── */

function YoYTable({ data }: { data: YoYResponse }) {
  const { years, items } = data;
  if (!items || items.length === 0) {
    return <p className="text-slate-500 text-sm">No year-over-year data available.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-dashboard-border">
            <th className="text-left py-2 px-3 text-xs font-semibold text-slate-400 uppercase">
              Name
            </th>
            {years.map((y) => (
              <th
                key={y}
                className="text-right py-2 px-3 text-xs font-semibold text-slate-400 uppercase"
              >
                {y}
              </th>
            ))}
            <th className="text-right py-2 px-3 text-xs font-semibold text-slate-400 uppercase">
              Total
            </th>
            <th className="text-right py-2 px-3 text-xs font-semibold text-slate-400 uppercase">
              YoY %
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, idx) => (
            <tr
              key={item.name}
              className={`border-b border-slate-800/50 ${
                idx % 2 === 0 ? "" : "bg-slate-800/20"
              }`}
            >
              <td className="py-2.5 px-3 text-slate-300 truncate max-w-[200px]" title={item.name}>
                {item.name}
              </td>
              {years.map((y) => {
                const val = item.by_year[String(y)] ?? 0;
                return (
                  <td key={y} className="py-2.5 px-3 text-right text-slate-400 font-mono text-xs">
                    {val > 0 ? formatCompactCurrency(val) : (
                      <span className="text-slate-700">-</span>
                    )}
                  </td>
                );
              })}
              <td className="py-2.5 px-3 text-right text-white font-medium font-mono text-xs">
                {formatCompactCurrency(item.total)}
              </td>
              <td className="py-2.5 px-3 text-right">
                <YoYBadge value={item.yoy_change_pct} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function YoYBadge({ value }: { value: number | null }) {
  if (value === null || value === undefined || !isFinite(value)) {
    return <span className="text-xs text-slate-600">N/A</span>;
  }
  const isPositive = value > 0;
  const isZero = value === 0;
  const color = isZero
    ? "text-slate-500"
    : isPositive
    ? "text-emerald-400"
    : "text-red-400";
  const bgColor = isZero
    ? "bg-slate-800"
    : isPositive
    ? "bg-emerald-500/10"
    : "bg-red-500/10";

  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${color} ${bgColor}`}
    >
      {isPositive ? "+" : ""}
      {value.toFixed(1)}%
    </span>
  );
}

/* ─── Section 3: Patterns & Insights ─── */

function PatternsSection({ data }: { data: PatternsResponse }) {
  return (
    <div className="space-y-8">
      {/* Seasonality */}
      <SeasonalityChart data={data.seasonality} />

      {/* Quarterly Trend */}
      <QuarterlyChart data={data.quarterly} />

      {/* Growth / Decline cards */}
      {data.growth && <GrowthCards data={data.growth} />}

      {/* Spending Spikes */}
      {data.spikes && data.spikes.length > 0 && <SpikesTable data={data.spikes} />}
    </div>
  );
}

function SeasonalityChart({ data }: { data: PatternsResponse["seasonality"] }) {
  if (!data || data.length === 0) return null;
  const max = Math.max(...data.map((d) => d.avg_spending));
  const avg = data.reduce((s, d) => s + d.avg_spending, 0) / data.length;

  return (
    <div>
      <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3">
        Monthly Seasonality (Average)
      </h3>
      <div className="flex items-end gap-2 h-40">
        {data.map((d) => {
          const pct = max > 0 ? (d.avg_spending / max) * 100 : 0;
          const isAboveAvg = d.avg_spending > avg * 1.15;
          return (
            <div
              key={d.month}
              className="flex-1 flex flex-col items-center gap-1 group relative"
            >
              <div className="hidden group-hover:block absolute bottom-full mb-1 z-10 bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs whitespace-nowrap shadow-lg">
                <p className="text-white">{d.label}</p>
                <p className="text-slate-400">{formatCompactCurrency(d.avg_spending)}</p>
              </div>
              <span className="text-[9px] text-slate-500">
                {formatCompactCurrency(d.avg_spending)}
              </span>
              <div
                className={`w-full rounded-t transition-all ${
                  isAboveAvg ? "bg-amber-500" : "bg-blue-500/70"
                }`}
                style={{ height: `${pct}%`, minHeight: "2px" }}
              />
              <span className="text-[10px] text-slate-500">{d.label?.slice(0, 3) || MONTH_SHORT[d.month - 1]}</span>
            </div>
          );
        })}
      </div>
      <div className="flex items-center gap-3 mt-2 text-xs text-slate-600">
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 bg-amber-500 rounded-sm" />
          Above average ({">"}15%)
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 bg-blue-500/70 rounded-sm" />
          Normal range
        </div>
      </div>
    </div>
  );
}

function QuarterlyChart({ data }: { data: PatternsResponse["quarterly"] }) {
  if (!data || data.length === 0) return null;

  // Group by year
  const years = [...new Set(data.map((d) => d.year))].sort();
  const yearColors = [
    "bg-blue-500",
    "bg-emerald-500",
    "bg-purple-500",
    "bg-amber-500",
    "bg-cyan-500",
  ];
  const max = Math.max(...data.map((d) => d.amount));

  return (
    <div>
      <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3">
        Quarterly Spending by Year
      </h3>
      <div className="flex flex-wrap gap-2 mb-3">
        {years.map((y, i) => (
          <div key={y} className="flex items-center gap-1.5">
            <div className={`w-3 h-3 rounded-sm ${yearColors[i % yearColors.length]}`} />
            <span className="text-xs text-slate-400">{y}</span>
          </div>
        ))}
      </div>
      <div className="flex gap-6">
        {[1, 2, 3, 4].map((q) => (
          <div key={q} className="flex-1">
            <p className="text-xs text-slate-500 text-center mb-2">Q{q}</p>
            <div className="flex items-end justify-center gap-1 h-32">
              {years.map((y, yi) => {
                const point = data.find((d) => d.year === y && d.quarter === q);
                const amt = point?.amount ?? 0;
                const pct = max > 0 ? (amt / max) * 100 : 0;
                return (
                  <div
                    key={y}
                    className="flex-1 max-w-[30px] group relative flex flex-col items-center"
                  >
                    <div className="hidden group-hover:block absolute bottom-full mb-1 z-10 bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs whitespace-nowrap shadow-lg">
                      <p className="text-white">{y} Q{q}</p>
                      <p className="text-slate-400">{formatCompactCurrency(amt)}</p>
                    </div>
                    <div
                      className={`w-full rounded-t ${yearColors[yi % yearColors.length]}`}
                      style={{ height: `${pct}%`, minHeight: amt > 0 ? "2px" : "0px" }}
                    />
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function GrowthCards({ data }: { data: PatternsResponse["growth"] }) {
  const sorted = [...(data.by_dimension || [])].sort(
    (a, b) => b.change_pct - a.change_pct
  );
  const growing = sorted.filter((d) => d.change_pct > 0).slice(0, 5);
  const declining = sorted.filter((d) => d.change_pct < 0).slice(-5).reverse();

  return (
    <div>
      <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3">
        Growth: {data.prior_year} vs {data.latest_year}
      </h3>

      {/* Overall growth card */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
        <div className="bg-slate-800/50 rounded-lg p-4">
          <p className="text-xs text-slate-500 mb-1">{data.prior_year} Total</p>
          <p className="text-lg font-bold text-slate-300">
            {formatCompactCurrency(data.prior_total)}
          </p>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-4">
          <p className="text-xs text-slate-500 mb-1">{data.latest_year} Total</p>
          <p className="text-lg font-bold text-white">
            {formatCompactCurrency(data.latest_total)}
          </p>
        </div>
        <div
          className={`rounded-lg p-4 ${
            data.growth_pct >= 0
              ? "bg-emerald-500/10 border border-emerald-500/20"
              : "bg-red-500/10 border border-red-500/20"
          }`}
        >
          <p className="text-xs text-slate-500 mb-1">Overall Change</p>
          <p
            className={`text-lg font-bold ${
              data.growth_pct >= 0 ? "text-emerald-400" : "text-red-400"
            }`}
          >
            {data.growth_pct >= 0 ? "+" : ""}
            {data.growth_pct?.toFixed(1)}%
          </p>
        </div>
      </div>

      {/* Fastest growing / declining */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {growing.length > 0 && (
          <div>
            <p className="text-xs text-emerald-400 font-medium mb-2">Fastest Growing</p>
            <div className="space-y-2">
              {growing.map((item) => (
                <div
                  key={item.name}
                  className="flex items-center justify-between bg-slate-800/30 rounded px-3 py-2"
                >
                  <span className="text-xs text-slate-300 truncate mr-2">{item.name}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500">
                      {formatCompactCurrency(item.prior)} -&gt; {formatCompactCurrency(item.latest)}
                    </span>
                    <span className="text-xs font-medium text-emerald-400">
                      +{item.change_pct.toFixed(1)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        {declining.length > 0 && (
          <div>
            <p className="text-xs text-red-400 font-medium mb-2">Fastest Declining</p>
            <div className="space-y-2">
              {declining.map((item) => (
                <div
                  key={item.name}
                  className="flex items-center justify-between bg-slate-800/30 rounded px-3 py-2"
                >
                  <span className="text-xs text-slate-300 truncate mr-2">{item.name}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500">
                      {formatCompactCurrency(item.prior)} -&gt; {formatCompactCurrency(item.latest)}
                    </span>
                    <span className="text-xs font-medium text-red-400">
                      {item.change_pct.toFixed(1)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function SpikesTable({ data }: { data: PatternsResponse["spikes"] }) {
  return (
    <div>
      <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
        Spending Spikes
      </h3>
      <p className="text-xs text-slate-600 mb-3">
        Months where spending was 1.5x+ the historical average for that month. Investigate these for unusual activity.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-dashboard-border">
              <th className="text-left py-2 px-3 text-xs font-semibold text-slate-400 uppercase">
                Month
              </th>
              <th className="text-right py-2 px-3 text-xs font-semibold text-slate-400 uppercase">
                Amount
              </th>
              <th className="text-right py-2 px-3 text-xs font-semibold text-slate-400 uppercase">
                Avg for Month
              </th>
              <th className="text-right py-2 px-3 text-xs font-semibold text-slate-400 uppercase">
                Spike Ratio
              </th>
              <th className="text-left py-2 px-3 text-xs font-semibold text-slate-400 uppercase">
                Top Vendor
              </th>
            </tr>
          </thead>
          <tbody>
            {data.map((spike, idx) => (
              <tr
                key={`${spike.year}-${spike.month}`}
                className={`border-b border-slate-800/50 ${
                  spike.spike_ratio >= 2
                    ? "bg-red-500/5"
                    : idx % 2 === 0
                    ? ""
                    : "bg-slate-800/20"
                }`}
              >
                <td className="py-2.5 px-3 text-slate-300">
                  {monthLabel(spike.year, spike.month)}
                  {spike.spike_ratio >= 2 && (
                    <span className="ml-2 text-[10px] text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded">
                      investigate
                    </span>
                  )}
                </td>
                <td className="py-2.5 px-3 text-right text-white font-medium font-mono text-xs">
                  {formatCompactCurrency(spike.amount)}
                </td>
                <td className="py-2.5 px-3 text-right text-slate-500 font-mono text-xs">
                  {formatCompactCurrency(spike.avg_for_month)}
                </td>
                <td className="py-2.5 px-3 text-right">
                  <span
                    className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                      spike.spike_ratio >= 2
                        ? "bg-red-500/15 text-red-400"
                        : "bg-amber-500/15 text-amber-400"
                    }`}
                  >
                    {spike.spike_ratio.toFixed(1)}x
                  </span>
                </td>
                <td className="py-2.5 px-3 text-slate-400 text-xs truncate max-w-[200px]">
                  {spike.top_vendor || "N/A"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
