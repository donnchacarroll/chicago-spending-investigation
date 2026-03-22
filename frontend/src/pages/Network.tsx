import { useEffect, useState, useCallback } from "react";
import {
  getNetworkSummary,
  getAddressClusters,
  getVendorAliases,
  getClusterDetail,
} from "../lib/api";
import type {
  NetworkSummary,
  AddressCluster,
  AddressClustersResponse,
  VendorAliasesResponse,
  ClusterDetail,
} from "../lib/api";
import { useDateFilter } from "../lib/DateFilterContext";
import {
  formatCurrency,
  formatCompactCurrency,
  formatNumber,
} from "../lib/formatters";

// --- Helpers ---

function vendorCountColor(count: number): string {
  if (count >= 8) return "text-red-400 bg-red-500/20 border-red-500/30";
  if (count >= 5) return "text-orange-400 bg-orange-500/20 border-orange-500/30";
  if (count >= 3) return "text-yellow-400 bg-yellow-500/20 border-yellow-500/30";
  return "text-green-400 bg-green-500/20 border-green-500/30";
}

function vendorCountBorder(count: number): string {
  if (count >= 8) return "border-red-500/30";
  if (count >= 5) return "border-orange-500/30";
  if (count >= 3) return "border-yellow-500/30";
  return "border-slate-700";
}

function riskFlagStyle(flag: string): string {
  const lower = flag.toLowerCase();
  if (lower.includes("jv") || lower.includes("joint venture"))
    return "bg-red-500/20 text-red-400 border-red-500/40";
  if (lower.includes("single department"))
    return "bg-orange-500/20 text-orange-400 border-orange-500/40";
  if (lower.includes("sole source"))
    return "bg-yellow-500/20 text-yellow-400 border-yellow-500/40";
  return "bg-slate-500/20 text-slate-400 border-slate-500/40";
}

function riskFlagIcon(flag: string): string {
  const lower = flag.toLowerCase();
  if (lower.includes("jv") || lower.includes("joint venture")) return "!!";
  if (lower.includes("single department")) return "!";
  if (lower.includes("sole source")) return "S";
  return "?";
}

// --- Components ---

function Spinner({ message }: { message: string }) {
  return (
    <div className="card p-8 text-center">
      <div className="w-6 h-6 border-2 border-red-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
      <p className="text-slate-500 text-sm">{message}</p>
    </div>
  );
}

function SummaryCard({
  label,
  value,
  sub,
  accent = "text-white",
}: {
  label: string;
  value: string | number;
  sub?: string;
  accent?: string;
}) {
  return (
    <div className="bg-dashboard-card border border-dashboard-border rounded-lg p-5">
      <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-1">
        {label}
      </p>
      <p className={`text-2xl font-bold ${accent}`}>{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
    </div>
  );
}

function RiskFlagBadge({ flag }: { flag: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold uppercase border ${riskFlagStyle(
        flag
      )}`}
    >
      <span className="opacity-70">{riskFlagIcon(flag)}</span>
      {flag}
    </span>
  );
}

// --- Cluster Detail Modal ---

function ClusterDetailModal({
  detail,
  loading,
  onClose,
}: {
  detail: ClusterDetail | null;
  loading: boolean;
  onClose: () => void;
}) {
  if (!detail && !loading) return null;
  return (
    <div
      className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-dashboard-card border border-red-500/20 rounded-lg p-6 max-w-4xl w-full max-h-[85vh] overflow-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {loading ? (
          <div className="text-center py-8">
            <div className="w-6 h-6 border-2 border-red-500 border-t-transparent rounded-full animate-spin mx-auto" />
          </div>
        ) : detail ? (
          <>
            {/* Header */}
            <div className="flex items-start justify-between mb-5">
              <div>
                <p className="text-xs text-red-400 uppercase tracking-wider font-semibold mb-1">
                  Cluster Investigation
                </p>
                <h2 className="text-xl font-bold text-white">{detail.address}</h2>
                <p className="text-sm text-slate-500 mt-1">
                  {detail.vendors.length} vendors at this address
                </p>
              </div>
              <button
                onClick={onClose}
                className="text-slate-500 hover:text-white text-xl leading-none"
              >
                &times;
              </button>
            </div>

            {/* Risk Assessment */}
            <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-4 mb-6">
              <h3 className="text-sm font-semibold text-red-400 mb-3 flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                </svg>
                Risk Assessment
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="bg-slate-900/50 rounded p-3">
                  <p className="text-lg font-bold text-red-400">{detail.risk_assessment.jv_entities}</p>
                  <p className="text-[10px] text-slate-500 uppercase">JV Entities</p>
                </div>
                <div className="bg-slate-900/50 rounded p-3">
                  <p className="text-lg font-bold text-orange-400">{detail.risk_assessment.sole_source_contracts}</p>
                  <p className="text-[10px] text-slate-500 uppercase">Sole Source</p>
                </div>
                <div className="bg-slate-900/50 rounded p-3">
                  <p className="text-lg font-bold text-yellow-400">{detail.risk_assessment.single_department_pct.toFixed(1)}%</p>
                  <p className="text-[10px] text-slate-500 uppercase">Single Dept %</p>
                </div>
                <div className="bg-slate-900/50 rounded p-3">
                  <p className="text-lg font-bold text-slate-200">{detail.risk_assessment.largest_vendor_pct.toFixed(1)}%</p>
                  <p className="text-[10px] text-slate-500 uppercase">Largest Vendor %</p>
                </div>
              </div>
            </div>

            {/* Shared Departments */}
            {detail.shared_departments.length > 0 && (
              <div className="mb-6">
                <h3 className="text-sm font-semibold text-white mb-2">Shared Departments</h3>
                <div className="flex flex-wrap gap-2">
                  {detail.shared_departments.map((dept) => (
                    <span
                      key={dept}
                      className="px-2 py-1 rounded bg-orange-500/10 border border-orange-500/20 text-orange-400 text-xs"
                    >
                      {dept}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Vendors */}
            <div>
              <h3 className="text-sm font-semibold text-white mb-3">
                Vendors ({detail.vendors.length})
              </h3>
              <div className="space-y-3">
                {detail.vendors.map((v) => (
                  <div
                    key={v.vendor_id || v.vendor_name}
                    className="bg-slate-800/50 border border-slate-700 rounded-lg p-4"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <p className="text-white font-medium">{v.vendor_name}</p>
                        <p className="text-[10px] text-slate-600 font-mono">{v.vendor_id}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-emerald-400 font-bold">
                          {formatCompactCurrency(v.total_awards)}
                        </p>
                        <p className="text-[10px] text-slate-500">
                          {formatCompactCurrency(v.total_paid)} paid
                        </p>
                      </div>
                    </div>
                    {/* Departments */}
                    <div className="flex flex-wrap gap-1 mb-2">
                      {v.departments.map((d) => (
                        <span
                          key={d}
                          className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700/50 text-slate-400"
                        >
                          {d}
                        </span>
                      ))}
                    </div>
                    {/* Contracts */}
                    {v.contracts.length > 0 && (
                      <div className="space-y-1 mt-2">
                        {v.contracts.slice(0, 5).map((c, i) => (
                          <div
                            key={i}
                            className="flex items-center justify-between text-xs bg-slate-900/50 rounded px-3 py-1.5"
                          >
                            <span className="text-slate-400 font-mono">
                              #{c.contract_number}
                            </span>
                            <span className="text-slate-500 truncate max-w-[200px] mx-2">
                              {c.description}
                            </span>
                            <span className="text-emerald-400">
                              {formatCompactCurrency(c.award_amount)}
                            </span>
                          </div>
                        ))}
                        {v.contracts.length > 5 && (
                          <p className="text-[10px] text-slate-600 pl-3">
                            +{v.contracts.length - 5} more contracts
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}

// --- Main Page ---

export default function Network() {
  const { applyToParams, dateFilter } = useDateFilter();

  // State
  const [summary, setSummary] = useState<NetworkSummary | null>(null);
  const [clusters, setClusters] = useState<AddressClustersResponse | null>(null);
  const [aliases, setAliases] = useState<VendorAliasesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [minVendors, setMinVendors] = useState("2");
  const [clusterPage, setClusterPage] = useState(1);

  // Cluster detail
  const [selectedCluster, setSelectedCluster] = useState<ClusterDetail | null>(null);
  const [clusterDetailLoading, setClusterDetailLoading] = useState(false);

  // Section visibility
  const [showAliases, setShowAliases] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const baseParams = applyToParams({});
      const [summaryData, clustersData, aliasesData] = await Promise.all([
        getNetworkSummary(baseParams),
        getAddressClusters(
          applyToParams({
            min_vendors: minVendors,
            sort: "total_awards",
            page: String(clusterPage),
            per_page: "20",
          })
        ),
        getVendorAliases(baseParams),
      ]);
      setSummary(summaryData);
      setClusters(clustersData);
      setAliases(aliasesData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load network data");
    } finally {
      setLoading(false);
    }
  }, [minVendors, clusterPage, dateFilter.startDate, dateFilter.endDate]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleClusterClick = async (cluster: AddressCluster) => {
    setClusterDetailLoading(true);
    setSelectedCluster(null);
    try {
      const detail = await getClusterDetail(
        cluster.address,
        applyToParams({})
      );
      setSelectedCluster(detail);
    } catch {
      setSelectedCluster(null);
    } finally {
      setClusterDetailLoading(false);
    }
  };

  if (loading && !summary) {
    return (
      <div>
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white">Vendor Network Analysis</h1>
          <p className="text-slate-500 text-sm mt-1">
            Investigating vendor relationships, shared addresses, and alias patterns
          </p>
        </div>
        <Spinner message="Analyzing vendor networks..." />
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white">Vendor Network Analysis</h1>
        </div>
        <div className="card p-8 text-center text-red-400">{error}</div>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-1">
          <svg className="w-7 h-7 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
          </svg>
          <h1 className="text-2xl font-bold text-white">Vendor Network Analysis</h1>
        </div>
        <p className="text-slate-500 text-sm">
          Investigating vendor relationships, shared addresses, and alias patterns to surface potential fraud and conflicts
        </p>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <SummaryCard
            label="Address Clusters"
            value={formatNumber(summary.address_clusters.total)}
            sub={`${summary.address_clusters.with_3plus} with 3+ vendors`}
            accent="text-red-400"
          />
          <SummaryCard
            label="Vendor Aliases Detected"
            value={formatNumber(summary.vendor_aliases.total_groups)}
            sub={`${formatCompactCurrency(summary.vendor_aliases.total_awards)} in awards`}
            accent="text-orange-400"
          />
          <SummaryCard
            label="Awards in Clusters"
            value={formatCompactCurrency(summary.address_clusters.total_awards)}
            sub={`Across all clustered vendors`}
            accent="text-yellow-400"
          />
          <SummaryCard
            label="Sole Source Repeat Winners"
            value={formatNumber(summary.sole_source_stats.repeat_winners)}
            sub={`of ${formatNumber(summary.sole_source_stats.total_vendors)} sole source vendors`}
            accent="text-red-400"
          />
        </div>
      )}

      {/* Top Risk Clusters Quick View */}
      {summary && summary.top_risk_clusters.length > 0 && (
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-red-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
            </svg>
            Highest Risk Clusters
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {summary.top_risk_clusters.slice(0, 6).map((rc, i) => (
              <div
                key={i}
                className="bg-red-500/5 border border-red-500/20 rounded-lg p-3 hover:border-red-500/40 transition-colors cursor-pointer"
              >
                <div className="flex items-start justify-between mb-2">
                  <p className="text-sm text-white font-medium">{rc.address}, {rc.city}</p>
                  <span className={`text-lg font-bold px-2 py-0.5 rounded border ${vendorCountColor(rc.vendor_count)}`}>
                    {rc.vendor_count}
                  </span>
                </div>
                <p className="text-emerald-400 text-sm font-medium mb-2">
                  {formatCompactCurrency(rc.total_awards)}
                </p>
                <div className="flex flex-wrap gap-1">
                  {rc.risk_flags.map((f, j) => (
                    <RiskFlagBadge key={j} flag={f} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Address Cluster Explorer */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <svg className="w-5 h-5 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
              </svg>
              Address Cluster Explorer
            </h2>
            {clusters && (
              <p className="text-xs text-slate-500 mt-1">
                {formatNumber(clusters.total_clusters)} clusters
                {" / "}
                {formatNumber(clusters.total_vendors_in_clusters)} vendors
                {" / "}
                {formatCompactCurrency(clusters.total_awards_in_clusters)} total awards
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">Min vendors:</span>
            {["2", "3", "5"].map((v) => (
              <button
                key={v}
                onClick={() => {
                  setMinVendors(v);
                  setClusterPage(1);
                }}
                className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                  minVendors === v
                    ? "bg-red-600/20 border border-red-500/40 text-red-400"
                    : "bg-slate-800 border border-slate-700 text-slate-400 hover:text-slate-200"
                }`}
              >
                {v}+
              </button>
            ))}
          </div>
        </div>

        {clusters && clusters.clusters.length > 0 ? (
          <div className="space-y-3">
            {clusters.clusters.map((cluster, i) => (
              <div
                key={i}
                className={`bg-dashboard-card border ${vendorCountBorder(
                  cluster.vendor_count
                )} rounded-lg p-4 hover:bg-slate-800/50 transition-colors cursor-pointer`}
                onClick={() => handleClusterClick(cluster)}
              >
                <div className="flex items-start justify-between">
                  {/* Left: Address & Vendors */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <span
                        className={`text-2xl font-bold px-3 py-1 rounded border ${vendorCountColor(
                          cluster.vendor_count
                        )}`}
                      >
                        {cluster.vendor_count}
                      </span>
                      <div>
                        <p className="text-white font-medium">
                          {cluster.address}
                        </p>
                        <p className="text-xs text-slate-500">
                          {cluster.city} {cluster.zip}
                        </p>
                      </div>
                    </div>

                    {/* Vendor names (truncated) */}
                    <div className="flex flex-wrap gap-1 mb-2">
                      {cluster.vendors.slice(0, 4).map((v, j) => (
                        <span
                          key={j}
                          className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 truncate max-w-[200px]"
                        >
                          {v}
                        </span>
                      ))}
                      {cluster.vendors.length > 4 && (
                        <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-500">
                          +{cluster.vendors.length - 4} more
                        </span>
                      )}
                    </div>

                    {/* Departments */}
                    <div className="flex flex-wrap gap-1 mb-2">
                      {cluster.departments.slice(0, 3).map((d, j) => (
                        <span
                          key={j}
                          className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20"
                        >
                          {d}
                        </span>
                      ))}
                      {cluster.departments.length > 3 && (
                        <span className="text-[10px] text-slate-600">
                          +{cluster.departments.length - 3} depts
                        </span>
                      )}
                    </div>

                    {/* Risk flags */}
                    {cluster.risk_flags.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {cluster.risk_flags.map((f, j) => (
                          <RiskFlagBadge key={j} flag={f} />
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Right: Awards */}
                  <div className="text-right ml-4 flex-shrink-0">
                    <p className="text-emerald-400 font-bold text-lg">
                      {formatCompactCurrency(cluster.total_awards)}
                    </p>
                    <p className="text-[10px] text-slate-500">total awards</p>
                    {cluster.total_paid > 0 && (
                      <>
                        <p className="text-slate-300 text-sm mt-1">
                          {formatCompactCurrency(cluster.total_paid)}
                        </p>
                        <p className="text-[10px] text-slate-600">paid</p>
                      </>
                    )}
                  </div>
                </div>

                {/* Expand hint */}
                <div className="mt-2 pt-2 border-t border-slate-800 text-center">
                  <p className="text-[10px] text-slate-600 uppercase tracking-wider">
                    Click to investigate
                  </p>
                </div>
              </div>
            ))}
          </div>
        ) : clusters ? (
          <div className="card p-8 text-center text-slate-500 text-sm">
            No address clusters found with {minVendors}+ vendors
          </div>
        ) : null}

        {/* Pagination */}
        {clusters && clusters.total_clusters > 20 && (
          <div className="flex items-center justify-between mt-4 text-sm">
            <p className="text-slate-500">
              Page {clusterPage} of {Math.ceil(clusters.total_clusters / 20)}
              {" "}({formatNumber(clusters.total_clusters)} clusters)
            </p>
            <div className="flex gap-2">
              <button
                disabled={clusterPage <= 1}
                onClick={() => setClusterPage((p) => p - 1)}
                className="px-3 py-1.5 rounded-md bg-slate-800 text-slate-400 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Prev
              </button>
              <button
                disabled={clusterPage >= Math.ceil(clusters.total_clusters / 20)}
                onClick={() => setClusterPage((p) => p + 1)}
                className="px-3 py-1.5 rounded-md bg-slate-800 text-slate-400 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Vendor Aliases Section */}
      <div className="mb-8">
        <button
          onClick={() => setShowAliases(!showAliases)}
          className="flex items-center gap-3 w-full text-left mb-4"
        >
          <div className="flex-1">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <svg className="w-5 h-5 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
              </svg>
              Vendor Aliases
              {aliases && (
                <span className="text-sm font-normal text-slate-500 ml-2">
                  ({formatNumber(aliases.total_alias_groups)} groups detected)
                </span>
              )}
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Same vendor ID mapped to multiple names - potential data quality issues or intentional obfuscation
            </p>
          </div>
          <svg
            className={`w-5 h-5 text-slate-500 transition-transform ${showAliases ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
          </svg>
        </button>

        {showAliases && aliases && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {aliases.aliases.map((alias, i) => {
              const isHighValue = alias.total_awards > 100_000_000;
              return (
                <div
                  key={i}
                  className={`bg-dashboard-card border rounded-lg p-4 ${
                    isHighValue
                      ? "border-red-500/30 bg-red-500/5"
                      : "border-dashboard-border"
                  }`}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <p className="text-[10px] text-slate-600 font-mono mb-1">
                        ID: {alias.vendor_id}
                      </p>
                      {isHighValue && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 border border-red-500/30 font-semibold">
                          HIGH VALUE
                        </span>
                      )}
                    </div>
                    <div className="text-right">
                      <p className="text-emerald-400 font-bold">
                        {formatCompactCurrency(alias.total_awards)}
                      </p>
                      <p className="text-[10px] text-slate-500">
                        {alias.contract_count} contracts
                      </p>
                    </div>
                  </div>

                  {/* Name variants */}
                  <div className="space-y-1.5">
                    {alias.names.map((name, j) => (
                      <div
                        key={j}
                        className="flex items-center gap-2 bg-slate-800/50 rounded px-3 py-1.5"
                      >
                        <span className="text-yellow-400 text-[10px] font-mono flex-shrink-0">
                          v{j + 1}
                        </span>
                        <span className="text-sm text-slate-300 truncate">{name}</span>
                      </div>
                    ))}
                  </div>

                  {/* Departments */}
                  {alias.departments.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {alias.departments.map((d, j) => (
                        <span
                          key={j}
                          className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400"
                        >
                          {d}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Cluster Detail Modal */}
      {(selectedCluster || clusterDetailLoading) && (
        <ClusterDetailModal
          detail={selectedCluster}
          loading={clusterDetailLoading}
          onClose={() => {
            setSelectedCluster(null);
            setClusterDetailLoading(false);
          }}
        />
      )}
    </div>
  );
}
