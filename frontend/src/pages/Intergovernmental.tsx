import { useEffect, useState } from "react";
import {
  getIntergovernmentalSummary,
  getIntergovernmentalDetail,
} from "../lib/api";
import type {
  IntergovernmentalSummary,
  IntergovernmentalDetail,
} from "../lib/api";
import { formatCurrency, formatCompactCurrency, formatNumber } from "../lib/formatters";
import { useDateFilter } from "../lib/DateFilterContext";

export default function Intergovernmental() {
  const { applyToParams, hasFilter } = useDateFilter();
  const [summary, setSummary] = useState<IntergovernmentalSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Detail drill-down
  const [expandedEntity, setExpandedEntity] = useState<string | null>(null);
  const [detail, setDetail] = useState<IntergovernmentalDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getIntergovernmentalSummary(applyToParams({}))
      .then(setSummary)
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load data");
      })
      .finally(() => setLoading(false));
  }, [applyToParams]);

  const handleEntityExpand = async (vendorName: string) => {
    if (expandedEntity === vendorName) {
      setExpandedEntity(null);
      setDetail(null);
      return;
    }
    setExpandedEntity(vendorName);
    setDetailLoading(true);
    try {
      const d = await getIntergovernmentalDetail(vendorName, applyToParams({}));
      setDetail(d);
    } catch {
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading intergovernmental data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400">
          {error}
        </div>
      </div>
    );
  }

  if (!summary) return null;

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      <div>
        <h2 className="text-2xl font-bold text-white">Government Transfers</h2>
        <p className="text-sm text-slate-400 mt-1">
          Payments to other government entities — county treasurers, state agencies, transit authorities, and boards.
          {hasFilter && " (date filter applied)"}
        </p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-dashboard-card border border-dashboard-border rounded-lg p-5">
          <p className="text-xs text-slate-500 uppercase tracking-wide">Total Transfers</p>
          <p className="text-2xl font-bold text-white mt-1">
            {formatCompactCurrency(summary.total_spending)}
          </p>
        </div>
        <div className="bg-dashboard-card border border-dashboard-border rounded-lg p-5">
          <p className="text-xs text-slate-500 uppercase tracking-wide">Payments</p>
          <p className="text-2xl font-bold text-white mt-1">
            {formatNumber(summary.payment_count)}
          </p>
        </div>
        <div className="bg-dashboard-card border border-dashboard-border rounded-lg p-5">
          <p className="text-xs text-slate-500 uppercase tracking-wide">Entities</p>
          <p className="text-2xl font-bold text-white mt-1">
            {formatNumber(summary.top_recipients.length)}
          </p>
        </div>
      </div>

      {/* Top Recipients */}
      <div className="bg-dashboard-card border border-dashboard-border rounded-lg">
        <div className="p-4 border-b border-dashboard-border">
          <h3 className="text-sm font-semibold text-white">Top Recipients</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500 uppercase tracking-wide border-b border-dashboard-border">
                <th className="px-4 py-3">Entity</th>
                <th className="px-4 py-3 text-right">Total Paid</th>
                <th className="px-4 py-3 text-right">Payments</th>
                <th className="px-4 py-3 text-right">Avg Payment</th>
              </tr>
            </thead>
            <tbody>
              {summary.top_recipients.map((r) => (
                <>
                  <tr
                    key={r.vendor_name}
                    className="border-b border-dashboard-border hover:bg-dashboard-hover cursor-pointer transition-colors"
                    onClick={() => handleEntityExpand(r.vendor_name)}
                  >
                    <td className="px-4 py-3">
                      <span className="text-blue-400 hover:text-blue-300">
                        {expandedEntity === r.vendor_name ? "\u25BC" : "\u25B6"}{" "}
                        {r.vendor_name}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-white font-medium">
                      {formatCurrency(r.total_paid)}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-300">
                      {formatNumber(r.payment_count)}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-300">
                      {formatCurrency(r.total_paid / r.payment_count)}
                    </td>
                  </tr>
                  {expandedEntity === r.vendor_name && (
                    <tr key={`${r.vendor_name}-detail`} className="bg-dashboard-hover/50">
                      <td colSpan={4} className="px-6 py-4">
                        {detailLoading ? (
                          <p className="text-slate-400 text-sm">Loading details...</p>
                        ) : detail ? (
                          <div className="space-y-4">
                            {/* Department breakdown */}
                            <div>
                              <h4 className="text-xs text-slate-500 uppercase tracking-wide mb-2">
                                Paying Departments
                              </h4>
                              <div className="space-y-1">
                                {detail.departments.map((d) => {
                                  const pct = (d.total_paid / detail.total_paid) * 100;
                                  return (
                                    <div key={d.department_name} className="flex items-center gap-3">
                                      <span className="text-slate-300 text-sm w-48 truncate">
                                        {d.department_name || "Unassigned"}
                                      </span>
                                      <div className="flex-1 bg-slate-700 rounded-full h-2">
                                        <div
                                          className="bg-blue-500 rounded-full h-2"
                                          style={{ width: `${Math.min(pct, 100)}%` }}
                                        />
                                      </div>
                                      <span className="text-slate-400 text-xs w-24 text-right">
                                        {formatCompactCurrency(d.total_paid)}
                                      </span>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                            {/* Yearly breakdown */}
                            {detail.payment_history.length > 0 && (
                              <div>
                                <h4 className="text-xs text-slate-500 uppercase tracking-wide mb-2">
                                  Payment History
                                </h4>
                                <div className="flex flex-wrap gap-2">
                                  {Object.entries(
                                    detail.payment_history.reduce<Record<number, number>>((acc, ph) => {
                                      acc[ph.year] = (acc[ph.year] || 0) + ph.total;
                                      return acc;
                                    }, {})
                                  ).map(([year, total]) => (
                                    <span
                                      key={year}
                                      className="bg-slate-700 text-slate-300 text-xs px-3 py-1.5 rounded"
                                    >
                                      {year}: {formatCompactCurrency(total)}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        ) : (
                          <p className="text-slate-500 text-sm">No detail available</p>
                        )}
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Spending by Year */}
      {summary.spending_by_year.length > 0 && (
        <div className="bg-dashboard-card border border-dashboard-border rounded-lg">
          <div className="p-4 border-b border-dashboard-border">
            <h3 className="text-sm font-semibold text-white">Spending by Year</h3>
          </div>
          <div className="p-4">
            <div className="space-y-2">
              {summary.spending_by_year.map((y) => {
                const maxSpending = Math.max(...summary.spending_by_year.map((s) => s.total_spending));
                const pct = (y.total_spending / maxSpending) * 100;
                return (
                  <div key={y.year} className="flex items-center gap-3">
                    <span className="text-slate-300 text-sm w-12">{y.year}</span>
                    <div className="flex-1 bg-slate-700 rounded-full h-3">
                      <div
                        className="bg-emerald-500 rounded-full h-3"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="text-white text-sm w-20 text-right font-medium">
                      {formatCompactCurrency(y.total_spending)}
                    </span>
                    <span className="text-slate-500 text-xs w-16 text-right">
                      {formatNumber(y.payment_count)} pmts
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Spending by Department */}
      {summary.spending_by_department.length > 0 && (
        <div className="bg-dashboard-card border border-dashboard-border rounded-lg">
          <div className="p-4 border-b border-dashboard-border">
            <h3 className="text-sm font-semibold text-white">Sending Departments</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Which city departments are making these intergovernmental payments
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-500 uppercase tracking-wide border-b border-dashboard-border">
                  <th className="px-4 py-3">Department</th>
                  <th className="px-4 py-3 text-right">Total Sent</th>
                  <th className="px-4 py-3 text-right">Payments</th>
                </tr>
              </thead>
              <tbody>
                {summary.spending_by_department.map((d) => (
                  <tr
                    key={d.department_name}
                    className="border-b border-dashboard-border hover:bg-dashboard-hover"
                  >
                    <td className="px-4 py-3 text-slate-300">
                      {d.department_name || "Unassigned"}
                    </td>
                    <td className="px-4 py-3 text-right text-white font-medium">
                      {formatCurrency(d.total_spending)}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-300">
                      {formatNumber(d.payment_count)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
