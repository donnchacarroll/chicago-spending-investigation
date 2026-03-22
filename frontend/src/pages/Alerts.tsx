import { useEffect, useState, useCallback } from "react";
import { getAlerts, getAlertsSummary, getAlertDetail } from "../lib/api";
import { useDateFilter } from "../lib/DateFilterContext";
import type { Alert, AlertsResponse, AlertsSummary, AlertDetail } from "../lib/api";
import { formatCurrency, formatDate, formatNumber } from "../lib/formatters";
import RiskBadge from "../components/RiskBadge";
import Pagination from "../components/Pagination";

export default function Alerts() {
  const { applyToParams, dateFilter } = useDateFilter();
  const [data, setData] = useState<AlertsResponse | null>(null);
  const [summary, setSummary] = useState<AlertsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [page, setPage] = useState(1);
  const [flagType, setFlagType] = useState("");
  const [minRisk, setMinRisk] = useState("");

  // Drill-down state
  const [expandedVoucher, setExpandedVoucher] = useState<string | null>(null);
  const [detail, setDetail] = useState<AlertDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Fetch summary once
  useEffect(() => {
    getAlertsSummary()
      .then(setSummary)
      .catch(() => {});
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {
        page: String(page),
        per_page: "50",
      };
      if (flagType) params.flag_type = flagType;
      if (minRisk) params.min_risk_score = minRisk;

      const alerts = await getAlerts(applyToParams(params));
      setData(alerts);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [page, flagType, minRisk, dateFilter.startDate, dateFilter.endDate]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleExpand = async (alert: Alert) => {
    const key = alert.voucher_number;
    if (!key) return;

    if (expandedVoucher === key) {
      setExpandedVoucher(null);
      setDetail(null);
      return;
    }

    setExpandedVoucher(key);
    setDetailLoading(true);
    try {
      const d = await getAlertDetail(key);
      setDetail(d);
    } catch {
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const flagTypes = summary?.by_flag_type ?? [];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Alerts</h1>
        <p className="text-slate-500 text-sm mt-1">
          Flagged payments and anomalies requiring investigation
        </p>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 mb-6">
          <button
            onClick={() => { setFlagType(""); setMinRisk(""); setPage(1); }}
            className={`card p-4 text-left transition-colors ${
              !flagType && !minRisk ? "border-blue-500/50 bg-blue-500/5" : "hover:bg-slate-800/60"
            }`}
          >
            <p className="text-2xl font-bold text-white">
              {summary.total_count.toLocaleString()}
            </p>
            <p className="text-xs text-slate-500">Total Alerts</p>
            {!flagType && !minRisk && <p className="text-[10px] text-blue-400 mt-1">Showing all</p>}
          </button>
          <button
            onClick={() => { setFlagType(""); setMinRisk("75"); setPage(1); }}
            className={`card p-4 text-left transition-colors ${
              minRisk === "75" && !flagType ? "border-red-500/50 bg-red-500/5" : "border-red-500/30 hover:bg-red-500/5"
            }`}
          >
            <p className="text-2xl font-bold text-red-400">
              {summary.critical_count.toLocaleString()}
            </p>
            <p className="text-xs text-slate-500">Critical (score &gt; 75)</p>
            {minRisk === "75" && !flagType && <p className="text-[10px] text-red-400 mt-1">Filtered</p>}
          </button>
          {flagTypes.map((ft) => (
            <button
              key={ft.flag_type}
              onClick={() => { setFlagType(ft.flag_type); setMinRisk(""); setPage(1); }}
              className={`card p-4 text-left transition-colors ${
                flagType === ft.flag_type ? "border-orange-500/50 bg-orange-500/5" : "hover:bg-slate-800/60"
              }`}
            >
              <p className="text-2xl font-bold text-slate-200">
                {ft.count.toLocaleString()}
              </p>
              <p className="text-xs text-slate-500 truncate">{ft.flag_type}</p>
              {flagType === ft.flag_type && <p className="text-[10px] text-orange-400 mt-1">Filtered</p>}
            </button>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="card p-4 mb-4">
        <div className="flex flex-wrap gap-3">
          <select
            value={flagType}
            onChange={(e) => {
              setFlagType(e.target.value);
              setPage(1);
            }}
            className="input-field"
          >
            <option value="">All Flag Types</option>
            {flagTypes.map((ft) => (
              <option key={ft.flag_type} value={ft.flag_type}>
                {ft.flag_type} ({ft.count})
              </option>
            ))}
          </select>

          <input
            type="number"
            placeholder="Min risk score"
            value={minRisk}
            onChange={(e) => {
              setMinRisk(e.target.value);
              setPage(1);
            }}
            className="input-field px-3 py-2 w-40"
            min="0"
            max="100"
          />

          {(flagType || minRisk) && (
            <button
              onClick={() => {
                setFlagType("");
                setMinRisk("");
                setPage(1);
              }}
              className="btn-secondary"
            >
              Reset
            </button>
          )}
        </div>
      </div>

      {/* Alert list */}
      {loading ? (
        <div className="card p-8 text-center">
          <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          <p className="text-slate-500 text-sm">Loading alerts...</p>
        </div>
      ) : error ? (
        <div className="card p-8 text-center text-red-400">{error}</div>
      ) : data && data.alerts.length > 0 ? (
        <>
          <div className="space-y-2">
            {data.alerts.map((alert, i) => {
              const isExpanded = expandedVoucher === alert.voucher_number;
              return (
                <div key={`${alert.voucher_number}-${alert.flag_type}-${i}`}>
                  {/* Alert row */}
                  <div
                    className={`card p-4 cursor-pointer transition-colors ${
                      isExpanded
                        ? "bg-slate-800/80 border-blue-500/40"
                        : "hover:bg-slate-800/60"
                    }`}
                    onClick={() => handleExpand(alert)}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <span className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded font-medium">
                            {alert.flag_type}
                          </span>
                          <RiskBadge score={alert.risk_score} />
                          {alert.voucher_number && (
                            <span className="text-[10px] text-slate-600">
                              Click to investigate
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-slate-300 mt-1">
                          {alert.description}
                        </p>
                        <div className="flex items-center gap-4 mt-2 text-xs text-slate-500">
                          {alert.vendor_name && (
                            <span>
                              Vendor:{" "}
                              <span className="text-slate-400">
                                {alert.vendor_name}
                              </span>
                            </span>
                          )}
                          {alert.department_name && (
                            <span>
                              Dept:{" "}
                              <span className="text-slate-400">
                                {alert.department_name}
                              </span>
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="text-right flex-shrink-0">
                        {alert.amount > 0 && (
                          <p className="text-emerald-400 font-medium text-sm">
                            {formatCurrency(alert.amount)}
                          </p>
                        )}
                        <span className="text-slate-600 text-lg">
                          {isExpanded ? "\u25B2" : "\u25BC"}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Expanded detail panel */}
                  {isExpanded && (
                    <div className="card p-5 mt-1 border-l-2 border-blue-500/50 ml-2">
                      {detailLoading ? (
                        <div className="flex items-center gap-2 py-4">
                          <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                          <span className="text-slate-500 text-sm">
                            Loading investigation details...
                          </span>
                        </div>
                      ) : detail ? (
                        <AlertDetailPanel detail={detail} />
                      ) : (
                        <p className="text-slate-500 text-sm">
                          No additional details available for this alert.
                        </p>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          <Pagination
            page={data.page}
            pages={data.total_pages || Math.ceil(data.total / data.per_page)}
            total={data.total}
            perPage={data.per_page}
            onPageChange={setPage}
          />
        </>
      ) : (
        <div className="card p-8 text-center text-slate-500">
          No alerts match your filters
        </div>
      )}
    </div>
  );
}

function AlertDetailPanel({ detail }: { detail: AlertDetail }) {
  const { payment, group_stats, comparison_payments, explanation } = detail;
  const stats = group_stats;

  return (
    <div className="space-y-5">
      {/* Inferred Purpose */}
      {detail.inferred_purpose && detail.inferred_purpose.purpose && (
        <div className={`rounded-lg p-4 ${
          detail.inferred_purpose.confidence === "high"
            ? "bg-slate-800/50 border border-slate-700"
            : "bg-yellow-500/5 border border-yellow-500/20"
        }`}>
          <div className="flex items-center gap-2 mb-2">
            <h4 className="text-sm font-semibold text-slate-300">Likely Purpose</h4>
            <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${
              detail.inferred_purpose.confidence === "high"
                ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                : detail.inferred_purpose.confidence === "medium"
                ? "bg-yellow-500/20 text-yellow-400 border-yellow-500/30"
                : "bg-slate-700 text-slate-400 border-slate-600"
            }`}>
              {detail.inferred_purpose.confidence} confidence
            </span>
          </div>
          <p className="text-sm text-white font-medium mb-1">{detail.inferred_purpose.purpose}</p>
          <p className="text-xs text-slate-400">{detail.inferred_purpose.reasoning}</p>
          {detail.inferred_purpose.amount_context && (
            <p className="text-xs text-slate-500 italic mt-1">{detail.inferred_purpose.amount_context}</p>
          )}
          <p className="text-[10px] text-slate-600 mt-2">{detail.inferred_purpose.disclaimer}</p>
        </div>
      )}

      {/* Explanation sections */}
      {explanation && explanation.length > 0 && (
        <div className="space-y-3">
          {explanation.map((section, i) => (
            <div key={i}>
              <h4 className="text-sm font-semibold text-white mb-1">
                {section.title}
              </h4>
              <p className="text-sm text-slate-400 leading-relaxed">
                {section.text}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Group statistics comparison */}
      {stats && stats.payment_count > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-white mb-3">
            Payment Distribution for this Vendor
          </h4>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatBlock
              label="This Payment"
              value={formatCurrency(payment.amount)}
              accent="text-orange-400"
            />
            <StatBlock
              label="Average"
              value={formatCurrency(stats.mean_amount)}
            />
            <StatBlock
              label="Median"
              value={formatCurrency(stats.median_amount)}
            />
            <StatBlock
              label="Total Payments"
              value={formatNumber(stats.payment_count)}
            />
          </div>

          {/* Visual range indicator */}
          <div className="mt-4 bg-slate-800/50 rounded-lg p-4">
            <p className="text-xs text-slate-500 mb-2">Payment Range</p>
            <div className="relative h-8 bg-slate-900 rounded">
              {/* IQR band */}
              {stats.max_amount > stats.min_amount && (
                <>
                  <div
                    className="absolute h-full bg-blue-500/20 rounded"
                    style={{
                      left: `${((stats.p25_amount - stats.min_amount) / (stats.max_amount - stats.min_amount)) * 100}%`,
                      width: `${((stats.p75_amount - stats.p25_amount) / (stats.max_amount - stats.min_amount)) * 100}%`,
                    }}
                  />
                  {/* Median line */}
                  <div
                    className="absolute w-0.5 h-full bg-blue-400"
                    style={{
                      left: `${((stats.median_amount - stats.min_amount) / (stats.max_amount - stats.min_amount)) * 100}%`,
                    }}
                  />
                  {/* This payment marker */}
                  <div
                    className="absolute w-2 h-full bg-orange-500 rounded"
                    style={{
                      left: `${Math.min(100, ((payment.amount - stats.min_amount) / (stats.max_amount - stats.min_amount)) * 100)}%`,
                    }}
                  />
                </>
              )}
            </div>
            <div className="flex justify-between text-[10px] text-slate-600 mt-1">
              <span>{formatCurrency(stats.min_amount)}</span>
              <span className="text-blue-400">
                25th–75th percentile
              </span>
              <span>{formatCurrency(stats.max_amount)}</span>
            </div>
            <div className="flex items-center gap-4 mt-2 text-[10px]">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 bg-blue-400 rounded-full inline-block" />
                <span className="text-slate-500">Median</span>
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 bg-orange-500 rounded-full inline-block" />
                <span className="text-slate-500">This payment</span>
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 bg-blue-500/40 rounded-full inline-block" />
                <span className="text-slate-500">IQR (typical range)</span>
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Comparison payments */}
      {comparison_payments && comparison_payments.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-white mb-2">
            Recent Payments to this Vendor ({comparison_payments.length})
          </h4>
          <div className="max-h-48 overflow-auto rounded border border-slate-700">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-slate-500 border-b border-slate-700 bg-slate-800/50">
                  <th className="text-left px-3 py-2">Date</th>
                  <th className="text-right px-3 py-2">Amount</th>
                  <th className="text-left px-3 py-2">Voucher</th>
                  <th className="text-left px-3 py-2">Contract</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {comparison_payments.map((cp) => {
                  const isThis = cp.voucher_number === payment.voucher_number;
                  return (
                    <tr
                      key={cp.voucher_number}
                      className={isThis ? "bg-orange-500/10" : ""}
                    >
                      <td className="px-3 py-1.5 text-slate-400">
                        {formatDate(cp.check_date)}
                      </td>
                      <td
                        className={`px-3 py-1.5 text-right font-medium ${
                          isThis ? "text-orange-400" : "text-slate-300"
                        }`}
                      >
                        {formatCurrency(cp.amount)}
                        {isThis && (
                          <span className="ml-1 text-[10px] text-orange-500">
                            &larr; THIS
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-1.5 text-slate-500">
                        {cp.voucher_number}
                      </td>
                      <td className="px-3 py-1.5 text-slate-500">
                        {cp.contract_number || "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* All flags for this payment */}
      {detail.alerts && detail.alerts.length > 1 && (
        <div>
          <h4 className="text-sm font-semibold text-white mb-2">
            All Flags for this Payment ({detail.alerts.length})
          </h4>
          <div className="space-y-1.5">
            {detail.alerts.map((a, i) => (
              <div
                key={i}
                className="flex items-center gap-2 bg-slate-800/50 rounded px-3 py-2"
              >
                <span className="text-[10px] bg-slate-700 text-slate-400 px-2 py-0.5 rounded font-medium">
                  {a.flag_type}
                </span>
                <RiskBadge score={a.risk_score} />
                <span className="text-xs text-slate-400 flex-1 truncate">
                  {a.description}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatBlock({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div className="bg-slate-800/50 rounded-lg p-3">
      <p className={`text-sm font-bold ${accent || "text-slate-200"}`}>
        {value}
      </p>
      <p className="text-[10px] text-slate-500">{label}</p>
    </div>
  );
}
