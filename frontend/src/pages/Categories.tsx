import { useEffect, useState } from "react";
import { getCategories, getCategoryDetail, getDVBreakdown, getDVTrends } from "../lib/api";
import { useDateFilter } from "../lib/DateFilterContext";
import type { CategoriesData, CategoryDetail, DVBreakdown, DVTrends } from "../lib/api";
import {
  formatCurrency,
  formatCompactCurrency,
  formatNumber,
} from "../lib/formatters";

const CATEGORY_COLORS: Record<string, string> = {
  Construction: "bg-blue-500",
  "Social Services": "bg-purple-500",
  "Professional Services": "bg-teal-500",
  Technology: "bg-cyan-500",
  Commodities: "bg-amber-500",
  Transportation: "bg-indigo-500",
  "Public Safety": "bg-rose-500",
  Healthcare: "bg-emerald-500",
  Utilities: "bg-sky-500",
  Education: "bg-violet-500",
};

const CATEGORY_TEXT_COLORS: Record<string, string> = {
  Construction: "text-blue-400",
  "Social Services": "text-purple-400",
  "Professional Services": "text-teal-400",
  Technology: "text-cyan-400",
  Commodities: "text-amber-400",
  Transportation: "text-indigo-400",
  "Public Safety": "text-rose-400",
  Healthcare: "text-emerald-400",
  Utilities: "text-sky-400",
  Education: "text-violet-400",
};

function getCategoryColor(cat: string): string {
  return CATEGORY_COLORS[cat] || "bg-slate-500";
}

function getCategoryTextColor(cat: string): string {
  return CATEGORY_TEXT_COLORS[cat] || "text-slate-400";
}

function getProcurementStyle(type: string): { bar: string; text: string } {
  const upper = type?.toUpperCase() || "";
  if (upper.includes("SOLE SOURCE")) return { bar: "bg-orange-500", text: "text-orange-400" };
  if (upper.includes("EMERGENCY")) return { bar: "bg-red-500", text: "text-red-400" };
  if (upper.includes("BID")) return { bar: "bg-blue-500", text: "text-blue-400" };
  if (upper.includes("RFP")) return { bar: "bg-emerald-500", text: "text-emerald-400" };
  return { bar: "bg-slate-500", text: "text-slate-400" };
}

export default function Categories() {
  const { applyToParams, dateFilter } = useDateFilter();
  const [data, setData] = useState<CategoriesData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<CategoryDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [dvData, setDvData] = useState<DVBreakdown | null>(null);
  const [dvTrends, setDvTrends] = useState<DVTrends | null>(null);
  const [dvSubcategory, setDvSubcategory] = useState<string>("");
  const [showDvDeepDive, setShowDvDeepDive] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getCategories(applyToParams({}))
      .then((res) => setData(res))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [dateFilter.startDate, dateFilter.endDate]);

  const loadDvBreakdown = async (subcategory?: string) => {
    const params = applyToParams({});
    if (subcategory) params.subcategory = subcategory;
    try {
      const [result, trends] = await Promise.all([
        getDVBreakdown(params),
        dvTrends ? Promise.resolve(dvTrends) : getDVTrends(applyToParams({})),
      ]);
      setDvData(result);
      setDvTrends(trends);
      setShowDvDeepDive(true);
    } catch {
      // ignore
    }
  };

  const handleCategoryClick = async (category: string) => {
    setDetailLoading(true);
    try {
      const detail = await getCategoryDetail(category, applyToParams({}));
      setSelectedCategory(detail);
    } catch {
      setSelectedCategory(null);
    } finally {
      setDetailLoading(false);
    }
  };

  if (loading) {
    return (
      <div>
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white">Spending Categories</h1>
          <p className="text-slate-500 text-sm mt-1">Spending breakdown by category, procurement method, and contract type</p>
        </div>
        <div className="card p-8 text-center">
          <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          <p className="text-slate-500 text-sm">Loading category data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white">Spending Categories</h1>
        </div>
        <div className="card p-8 text-center text-red-400">{error}</div>
      </div>
    );
  }

  if (!data) return null;

  const totalContracted = data.by_category.reduce((sum, c) => sum + c.total_spending, 0);
  const totalDirect = data.no_contract_spending?.total || 0;
  const grandTotal = totalContracted + totalDirect;
  const contractedPct = grandTotal > 0 ? (totalContracted / grandTotal) * 100 : 0;
  const directPct = grandTotal > 0 ? (totalDirect / grandTotal) * 100 : 0;

  const maxCategorySpending = Math.max(...data.by_category.map((c) => c.total_spending), 1);
  const maxProcSpending = Math.max(...data.by_procurement.map((p) => p.total_spending), 1);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Spending Categories</h1>
        <p className="text-slate-500 text-sm mt-1">
          Spending breakdown by category, procurement method, and contract type
        </p>
      </div>

      {/* Top stat cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {/* Contracted Spending */}
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-2 h-2 rounded-full bg-emerald-400" />
            <h3 className="text-sm font-semibold text-white">Contracted Spending</h3>
          </div>
          <p className="text-2xl font-bold text-emerald-400 mb-1">
            {formatCompactCurrency(totalContracted)}
          </p>
          <p className="text-xs text-slate-500 mb-3">
            {contractedPct.toFixed(1)}% of total spending across {data.by_category.length} categories
          </p>
          {/* Mini category breakdown */}
          <div className="space-y-1.5">
            {data.by_category.slice(0, 5).map((cat) => (
              <div key={cat.category} className="flex items-center gap-2 text-xs">
                <div className={`w-1.5 h-1.5 rounded-full ${getCategoryColor(cat.category)}`} />
                <span className="text-slate-400 truncate flex-1">{cat.category}</span>
                <span className="text-slate-300 font-medium">{formatCompactCurrency(cat.total_spending)}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Direct Voucher / No Contract Spending */}
        <div className="card p-5 border-l-2 border-l-orange-500/50">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-2 h-2 rounded-full bg-orange-400" />
            <h3 className="text-sm font-semibold text-white">Direct Voucher Spending</h3>
            <span className="text-[10px] bg-orange-500/20 text-orange-400 border border-orange-500/30 px-1.5 py-0.5 rounded font-medium">
              NO CONTRACT
            </span>
          </div>
          <p className="text-2xl font-bold text-orange-400 mb-1">
            {formatCompactCurrency(totalDirect)}
          </p>
          <p className="text-xs text-slate-500 mb-3">
            {directPct.toFixed(1)}% of total spending -- {formatNumber(data.no_contract_spending?.count || 0)} payments
          </p>
          <button
            onClick={() => loadDvBreakdown()}
            className="w-full bg-orange-500/10 border border-orange-500/20 rounded-lg p-3 hover:bg-orange-500/20 transition-colors text-left"
          >
            <p className="text-xs text-orange-300">
              These payments bypass standard procurement controls.{" "}
              <span className="text-orange-400 font-medium underline">Click to investigate breakdown &rarr;</span>
            </p>
          </button>
        </div>
      </div>

      {/* Proportion bar */}
      <div className="card p-4 mb-6">
        <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
          <span>Spending Proportion</span>
          <span>{formatCompactCurrency(grandTotal)} total</span>
        </div>
        <div className="h-3 bg-slate-800 rounded-full overflow-hidden flex">
          <div
            className="h-full bg-emerald-500 transition-all"
            style={{ width: `${contractedPct}%` }}
            title={`Contracted: ${contractedPct.toFixed(1)}%`}
          />
          <div
            className="h-full bg-orange-500 transition-all"
            style={{ width: `${directPct}%` }}
            title={`Direct Voucher: ${directPct.toFixed(1)}%`}
          />
        </div>
        <div className="flex gap-4 mt-2 text-xs">
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded bg-emerald-500" />
            <span className="text-slate-400">Contracted ({contractedPct.toFixed(1)}%)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded bg-orange-500" />
            <span className="text-slate-400">Direct Voucher ({directPct.toFixed(1)}%)</span>
          </div>
        </div>
      </div>

      {/* Direct Voucher Deep Dive */}
      {showDvDeepDive && dvData && (
        <div className="card p-5 mb-6 border-l-2 border-l-orange-500/50">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-orange-400" />
              <h2 className="text-base font-semibold text-white">Direct Voucher Deep Dive</h2>
              <span className="text-[10px] bg-orange-500/20 text-orange-400 border border-orange-500/30 px-1.5 py-0.5 rounded font-medium">
                {formatCompactCurrency(totalDirect)}
              </span>
            </div>
            <button
              onClick={() => setShowDvDeepDive(false)}
              className="text-slate-500 hover:text-white text-sm"
            >
              &times; Close
            </button>
          </div>

          {/* Subcategory breakdown */}
          <div className="mb-5">
            <h3 className="text-sm font-semibold text-slate-300 mb-3">What are direct vouchers paying for?</h3>
            <div className="space-y-2.5">
              {dvData.by_subcategory.map((sub) => {
                const maxSub = Math.max(...dvData.by_subcategory.map((s) => s.total_spending), 1);
                const isInvestigation = ["Legal Settlements & Fees", "Individual Payments", "Other Direct Voucher"].includes(sub.subcategory);
                return (
                  <button
                    key={sub.subcategory}
                    className="w-full text-left group"
                    onClick={() => {
                      setDvSubcategory(sub.subcategory);
                      loadDvBreakdown(sub.subcategory);
                    }}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className={`text-sm font-medium group-hover:underline ${
                          isInvestigation ? "text-orange-400" : "text-slate-300"
                        }`}>
                          {sub.subcategory}
                        </span>
                        {isInvestigation && (
                          <span className="text-[9px] bg-orange-500/20 text-orange-400 border border-orange-500/30 px-1 py-0.5 rounded">
                            INVESTIGATE
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-4 text-xs">
                        <span className="text-slate-500">{formatNumber(sub.payment_count)} payments</span>
                        <span className="text-slate-500">{formatNumber(sub.vendor_count)} vendors</span>
                        <span className="text-orange-400 font-medium">{formatCompactCurrency(sub.total_spending)}</span>
                      </div>
                    </div>
                    <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${isInvestigation ? "bg-orange-500" : "bg-slate-500"}`}
                        style={{ width: `${(sub.total_spending / maxSub) * 100}%` }}
                      />
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* YoY Growth Analysis */}
          {dvTrends && dvTrends.yoy.length > 0 && (
            <div className="mb-5">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">
                Year-over-Year Change ({dvTrends.yoy_years[0]} vs {dvTrends.yoy_years[1]})
              </h3>
              <div className="space-y-2">
                {dvTrends.yoy
                  .filter((r) => r.change_pct !== null)
                  .sort((a, b) => (b.change_pct ?? 0) - (a.change_pct ?? 0))
                  .map((row) => {
                    const isGrowing = (row.change_pct ?? 0) > 15;
                    const isDeclining = (row.change_pct ?? 0) < -15;
                    return (
                      <div
                        key={row.subcategory}
                        className={`flex items-center justify-between rounded-lg px-3 py-2 text-xs ${
                          isGrowing
                            ? "bg-red-500/10 border border-red-500/20"
                            : isDeclining
                            ? "bg-emerald-500/10 border border-emerald-500/20"
                            : "bg-slate-800/50"
                        }`}
                      >
                        <span className="text-slate-300 flex-1">{row.subcategory}</span>
                        <span className="text-slate-500 mx-4">
                          {formatCompactCurrency(row.prior_year)} &rarr; {formatCompactCurrency(row.latest_year)}
                        </span>
                        <span
                          className={`font-bold min-w-[60px] text-right ${
                            (row.change_pct ?? 0) > 50
                              ? "text-red-400"
                              : (row.change_pct ?? 0) > 15
                              ? "text-orange-400"
                              : (row.change_pct ?? 0) < -15
                              ? "text-emerald-400"
                              : "text-slate-400"
                          }`}
                        >
                          {row.change_pct !== null ? `${row.change_pct > 0 ? "+" : ""}${row.change_pct.toFixed(0)}%` : "—"}
                        </span>
                      </div>
                    );
                  })}
              </div>
              {/* Key callouts */}
              {dvTrends.growing.length > 0 && (
                <div className="mt-3 bg-red-500/5 border border-red-500/20 rounded-lg p-3">
                  <p className="text-xs text-red-400 font-semibold mb-1">Fastest Growing</p>
                  {dvTrends.growing.slice(0, 3).map((g) => (
                    <p key={g.subcategory} className="text-xs text-slate-400">
                      <span className="text-red-400 font-medium">+{g.change_pct.toFixed(0)}%</span>{" "}
                      {g.subcategory}
                    </p>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Unclassified "Other" vendors */}
          {dvTrends && dvTrends.other_dv_top_vendors.length > 0 && (
            <div className="mb-5 bg-yellow-500/5 border border-yellow-500/20 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-yellow-400 mb-1">
                Unclassified Direct Voucher Vendors
              </h3>
              <p className="text-xs text-slate-400 mb-3">
                These vendors in the &quot;Other Direct Voucher&quot; bucket may need reclassification.
                Some may be pensions, payroll, or other identifiable categories.
              </p>
              <div className="space-y-1.5 max-h-48 overflow-auto">
                {dvTrends.other_dv_top_vendors.slice(0, 15).map((v) => {
                  const maxV = dvTrends.other_dv_top_vendors[0].total_paid;
                  return (
                    <div key={v.vendor_name}>
                      <div className="flex justify-between text-xs mb-0.5">
                        <span className="text-slate-400 truncate mr-2">{v.vendor_name}</span>
                        <span className="text-slate-300 whitespace-nowrap">
                          {formatCompactCurrency(v.total_paid)} ({v.payment_count})
                        </span>
                      </div>
                      <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-yellow-500/60 rounded-full"
                          style={{ width: `${(v.total_paid / maxV) * 100}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Drill-down vendors for selected subcategory */}
          {dvSubcategory && dvData.top_vendors && dvData.top_vendors.length > 0 && (
            <div className="mb-5 bg-slate-800/30 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-white mb-3">
                Top Vendors: {dvSubcategory}
              </h3>
              <div className="space-y-2">
                {dvData.top_vendors.slice(0, 15).map((v) => {
                  const maxV = Math.max(...dvData.top_vendors.map((tv) => tv.total_paid), 1);
                  return (
                    <div key={v.vendor_name}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-slate-400 truncate mr-2">{v.vendor_name}</span>
                        <span className="text-slate-300 whitespace-nowrap">
                          {formatCompactCurrency(v.total_paid)} ({v.payment_count} payments, avg {formatCurrency(v.avg_payment)})
                        </span>
                      </div>
                      <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-orange-500 rounded-full"
                          style={{ width: `${(v.total_paid / maxV) * 100}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Individual payments stats */}
          {dvData.individual_stats && dvData.individual_stats.payment_count > 0 && (
            <div className="mb-5 bg-yellow-500/5 border border-yellow-500/20 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-yellow-400 mb-2">Individual Payments</h3>
              <p className="text-xs text-slate-400 mb-3">
                {formatNumber(dvData.individual_stats.payment_count)} payments to individuals totaling{" "}
                {formatCompactCurrency(dvData.individual_stats.total_spending)}.
                Average: {formatCurrency(dvData.individual_stats.avg_payment)}, Median: {formatCurrency(dvData.individual_stats.median_payment)}.
                These may be refunds, settlements, reimbursements, or small claims.
              </p>
            </div>
          )}

          {/* Largest DV payments */}
          <div>
            <h3 className="text-sm font-semibold text-white mb-3">Largest Direct Voucher Payments</h3>
            <div className="space-y-2 max-h-64 overflow-auto">
              {dvData.largest_payments.slice(0, 20).map((p, i) => (
                <div key={i} className="bg-slate-800/50 rounded p-3 text-xs">
                  <div className="flex items-start justify-between mb-1">
                    <div className="flex-1 min-w-0">
                      <span className="text-white font-medium">{p.vendor_name}</span>
                      {p.subcategory && (
                        <span className={`ml-2 text-[10px] px-1.5 py-0.5 rounded ${
                          p.subcategory === "Legal Settlements & Fees"
                            ? "bg-orange-500/20 text-orange-400"
                            : p.subcategory === "Individual Payments"
                            ? "bg-yellow-500/20 text-yellow-400"
                            : "bg-slate-700 text-slate-400"
                        }`}>
                          {p.subcategory}
                        </span>
                      )}
                    </div>
                    <span className="text-emerald-400 font-bold ml-2 whitespace-nowrap">
                      {formatCurrency(p.amount)}
                    </span>
                  </div>
                  <div className="text-slate-500">
                    {p.department_name && <span>{p.department_name} &middot; </span>}
                    {p.check_date}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Spending by Category */}
      <div className="card p-5 mb-6">
        <h2 className="text-base font-semibold text-white mb-4">Spending by Category</h2>
        <div className="space-y-3">
          {data.by_category.map((cat) => (
            <button
              key={cat.category}
              className="w-full text-left group"
              onClick={() => handleCategoryClick(cat.category)}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${getCategoryColor(cat.category)}`} />
                  <span className={`text-sm font-medium group-hover:underline ${getCategoryTextColor(cat.category)}`}>
                    {cat.category}
                  </span>
                </div>
                <div className="flex items-center gap-4 text-xs">
                  <span className="text-slate-500">{formatNumber(cat.payment_count)} payments</span>
                  <span className="text-slate-500">{formatNumber(cat.vendor_count)} vendors</span>
                  <span className="text-emerald-400 font-medium">{formatCompactCurrency(cat.total_spending)}</span>
                </div>
              </div>
              <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all group-hover:opacity-80 ${getCategoryColor(cat.category)}`}
                  style={{ width: `${(cat.total_spending / maxCategorySpending) * 100}%` }}
                />
              </div>
              <div className="text-[10px] text-slate-600 mt-0.5 text-right">
                avg {formatCurrency(cat.avg_payment)} per payment
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Procurement Method */}
      <div className="card p-5 mb-6">
        <h2 className="text-base font-semibold text-white mb-1">Procurement Method</h2>
        <p className="text-xs text-slate-500 mb-4">
          How contracts are awarded. SOLE SOURCE and EMERGENCY skip competitive bidding.
        </p>
        <div className="space-y-3">
          {data.by_procurement.map((proc) => {
            const style = getProcurementStyle(proc.procurement_type);
            const isConcern = proc.procurement_type?.toUpperCase().includes("SOLE SOURCE") ||
              proc.procurement_type?.toUpperCase().includes("EMERGENCY");
            return (
              <div key={proc.procurement_type}>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className={`text-sm font-medium ${style.text}`}>
                      {proc.procurement_type || "Unknown"}
                    </span>
                    {isConcern && (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium border ${
                        proc.procurement_type?.toUpperCase().includes("EMERGENCY")
                          ? "bg-red-500/20 text-red-400 border-red-500/30"
                          : "bg-orange-500/20 text-orange-400 border-orange-500/30"
                      }`}>
                        {proc.procurement_type?.toUpperCase().includes("EMERGENCY") ? "NON-COMPETITIVE" : "NO BID"}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-4 text-xs">
                    <span className="text-slate-500">{formatNumber(proc.payment_count)} payments</span>
                    <span className="text-emerald-400 font-medium">{formatCompactCurrency(proc.total_spending)}</span>
                  </div>
                </div>
                <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${style.bar}`}
                    style={{ width: `${(proc.total_spending / maxProcSpending) * 100}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Contract Types */}
      {data.by_contract_type && data.by_contract_type.length > 0 && (
        <div className="card p-5 mb-6">
          <h2 className="text-base font-semibold text-white mb-4">Contract Types</h2>
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-dashboard-border text-xs text-slate-500">
                  <th className="text-left pb-2 font-medium">Contract Type</th>
                  <th className="text-left pb-2 font-medium">Category</th>
                  <th className="text-right pb-2 font-medium">Spending</th>
                  <th className="text-right pb-2 font-medium">Payments</th>
                </tr>
              </thead>
              <tbody>
                {data.by_contract_type.slice(0, 20).map((ct, i) => (
                  <tr key={i} className="border-b border-dashboard-border/50 hover:bg-dashboard-hover">
                    <td className="py-2 text-slate-300 font-mono text-xs">{ct.contract_type}</td>
                    <td className="py-2">
                      <span className={`text-xs ${getCategoryTextColor(ct.category)}`}>{ct.category}</span>
                    </td>
                    <td className="py-2 text-right text-emerald-400 font-medium">
                      {formatCompactCurrency(ct.total_spending)}
                    </td>
                    <td className="py-2 text-right text-slate-400">
                      {formatNumber(ct.payment_count)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Category Detail Modal */}
      {(selectedCategory || detailLoading) && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedCategory(null)}
        >
          <div
            className="card p-6 max-w-4xl w-full max-h-[85vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {detailLoading ? (
              <div className="text-center py-8">
                <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
              </div>
            ) : selectedCategory ? (
              <CategoryDetailView detail={selectedCategory} onClose={() => setSelectedCategory(null)} />
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}

function CategoryDetailView({ detail, onClose }: { detail: CategoryDetail; onClose: () => void }) {
  const avgPayment = detail.payment_count > 0 ? detail.total_spending / detail.payment_count : 0;
  const maxVendor = Math.max(...(detail.top_vendors || []).map((v) => v.total_paid), 1);
  const maxDept = Math.max(...(detail.top_departments || []).map((d) => d.total_spending), 1);

  return (
    <>
      <div className="flex items-start justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full ${getCategoryColor(detail.category)}`} />
          <h2 className="text-xl font-bold text-white">{detail.category}</h2>
        </div>
        <button
          onClick={onClose}
          className="text-slate-500 hover:text-white text-xl leading-none"
        >
          &times;
        </button>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        <div className="bg-slate-800/50 rounded-lg p-3">
          <p className="text-lg font-bold text-emerald-400">
            {formatCompactCurrency(detail.total_spending)}
          </p>
          <p className="text-xs text-slate-500">Total Spending</p>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-3">
          <p className="text-lg font-bold text-blue-400">
            {formatNumber(detail.payment_count)}
          </p>
          <p className="text-xs text-slate-500">Payments</p>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-3">
          <p className="text-lg font-bold text-slate-200">
            {formatCurrency(avgPayment)}
          </p>
          <p className="text-xs text-slate-500">Avg Payment</p>
        </div>
      </div>

      {/* Monthly Trend */}
      {detail.monthly_trend && detail.monthly_trend.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-white mb-3">Monthly Spending Trend</h3>
          <div className="flex items-end gap-0.5 h-24">
            {(() => {
              const maxMonth = Math.max(...detail.monthly_trend.map((m) => m.total), 1);
              return detail.monthly_trend.map((m, i) => (
                <div
                  key={i}
                  className="flex-1 group relative"
                  title={`${m.year}-${String(m.month).padStart(2, "0")}: ${formatCompactCurrency(m.total)}`}
                >
                  <div
                    className={`w-full rounded-t ${getCategoryColor(detail.category)} opacity-70 group-hover:opacity-100 transition-opacity`}
                    style={{ height: `${(m.total / maxMonth) * 100}%` }}
                  />
                </div>
              ));
            })()}
          </div>
          <div className="flex justify-between text-[10px] text-slate-600 mt-1">
            {detail.monthly_trend.length > 0 && (
              <>
                <span>{detail.monthly_trend[0].year}-{String(detail.monthly_trend[0].month).padStart(2, "0")}</span>
                <span>{detail.monthly_trend[detail.monthly_trend.length - 1].year}-{String(detail.monthly_trend[detail.monthly_trend.length - 1].month).padStart(2, "0")}</span>
              </>
            )}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        {/* Top Vendors */}
        {detail.top_vendors && detail.top_vendors.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-white mb-3">Top 10 Vendors</h3>
            <div className="space-y-2">
              {detail.top_vendors.slice(0, 10).map((v) => (
                <div key={v.vendor_name}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-400 truncate mr-2">{v.vendor_name}</span>
                    <span className="text-slate-300 whitespace-nowrap">
                      {formatCompactCurrency(v.total_paid)} ({v.payment_count})
                    </span>
                  </div>
                  <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${getCategoryColor(detail.category)}`}
                      style={{ width: `${(v.total_paid / maxVendor) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Top Departments */}
        {detail.top_departments && detail.top_departments.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-white mb-3">Top Departments</h3>
            <div className="space-y-2">
              {detail.top_departments.slice(0, 10).map((d) => (
                <div key={d.department_name}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-400 truncate mr-2">{d.department_name}</span>
                    <span className="text-slate-300 whitespace-nowrap">
                      {formatCompactCurrency(d.total_spending)} ({d.payment_count})
                    </span>
                  </div>
                  <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-indigo-500 rounded-full"
                      style={{ width: `${(d.total_spending / maxDept) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Largest Payments */}
      {detail.largest_payments && detail.largest_payments.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-white mb-3">Largest Individual Payments</h3>
          <div className="space-y-2 max-h-64 overflow-auto">
            {detail.largest_payments.slice(0, 15).map((p, i) => (
              <div key={i} className="bg-slate-800/50 rounded-lg p-3 text-xs">
                <div className="flex items-start justify-between mb-1">
                  <span className="text-white font-medium">{p.vendor_name}</span>
                  <span className="text-emerald-400 font-bold ml-2 whitespace-nowrap">
                    {formatCurrency(p.amount)}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-slate-500">
                  <span>{p.department_name}</span>
                  <span>{p.check_date}</span>
                </div>
                {p.purchase_order_description && (
                  <p className="text-slate-400 mt-1 italic">
                    {p.purchase_order_description}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
