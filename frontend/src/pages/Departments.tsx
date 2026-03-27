import { useEffect, useState } from "react";
import { getDepartments, getDepartmentDetail, getDepartmentTrueCost } from "../lib/api";
import { useDateFilter } from "../lib/DateFilterContext";
import type { Department, TrueCostDepartment, TrueCostResponse } from "../lib/api";
import {
  formatCurrency,
  formatCompactCurrency,
  formatNumber,
} from "../lib/formatters";
import DataTable from "../components/DataTable";
import type { Column } from "../components/DataTable";
import RiskBadge from "../components/RiskBadge";

interface DeptDetail {
  summary: {
    department_name: string;
    total_spending: number;
    payment_count: number;
    vendor_count: number;
    avg_payment: number;
    risk_score: number;
    flag_count: number;
  };
  top_vendors: Array<{ vendor_name: string; total_paid: number; payment_count: number }>;
  monthly_trend: Array<{ year: number; month: number; total: number; count: number }>;
  concentration: { total_vendors: number; top_vendor_share: number; hhi: number };
  flags: Array<{ flag_type: string; description: string; risk_score: number; vendor_name: string; amount: number }>;
}

type ViewMode = "payment" | "truecost";

function TierBadge({ tier }: { tier: string }) {
  if (tier === "confirmed") {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
        Confirmed
      </span>
    );
  }
  if (tier === "attributed") {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-500/20 text-blue-400 border border-blue-500/30">
        Attributed
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/20 text-amber-400 border border-amber-500/30 border-dashed">
      Estimated
    </span>
  );
}

function StackedBar({ dept, maxCost }: { dept: TrueCostDepartment; maxCost: number }) {
  const confirmed = dept.total_salary + dept.confirmed_payments + dept.confirmed_contracts;
  const total = dept.total_true_cost || 1;
  const barWidth = maxCost > 0 ? (total / maxCost) * 100 : 0;

  const confirmedPct = (confirmed / total) * 100;
  const attributedPct = (dept.attributed_total / total) * 100;
  const estimatedPct = (dept.estimated_total / total) * 100;

  return (
    <div className="w-full">
      <div
        className="h-5 rounded-md overflow-hidden flex"
        style={{ width: `${Math.max(barWidth, 2)}%` }}
        title={`Confirmed: ${formatCompactCurrency(confirmed)} | Attributed: ${formatCompactCurrency(dept.attributed_total)} | Estimated: ${formatCompactCurrency(dept.estimated_total)}`}
      >
        {confirmedPct > 0 && (
          <div
            className="bg-emerald-500 h-full transition-all"
            style={{ width: `${confirmedPct}%` }}
          />
        )}
        {attributedPct > 0 && (
          <div
            className="bg-blue-500 h-full transition-all"
            style={{ width: `${attributedPct}%` }}
          />
        )}
        {estimatedPct > 0 && (
          <div
            className="bg-amber-500/70 h-full transition-all"
            style={{ width: `${estimatedPct}%`, borderRight: "2px dashed rgba(245,158,11,0.5)" }}
          />
        )}
      </div>
    </div>
  );
}

function TrueCostView({
  data,
  loading,
  error,
  selectedYear,
  onYearChange,
}: {
  data: TrueCostResponse | null;
  loading: boolean;
  error: string | null;
  selectedYear: string;
  onYearChange: (year: string) => void;
}) {
  const [expandedDept, setExpandedDept] = useState<string | null>(null);
  const [showMethodology, setShowMethodology] = useState(false);

  if (loading) {
    return (
      <div className="card p-8 text-center">
        <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
        <p className="text-slate-500 text-sm">Loading true cost data...</p>
      </div>
    );
  }

  if (error) {
    return <div className="card p-8 text-center text-red-400">{error}</div>;
  }

  if (!data || data.departments.length === 0) {
    return <div className="card p-8 text-center text-slate-500">No true cost data available.</div>;
  }

  const sorted = [...data.departments].sort((a, b) => b.total_true_cost - a.total_true_cost);
  const grandTotal = sorted.reduce((s, d) => s + d.total_true_cost, 0);
  const totalPayroll = sorted.reduce((s, d) => s + d.total_salary, 0);
  const maxCost = sorted[0]?.total_true_cost || 1;

  const availableYears = data.available_years || [];

  return (
    <div className="space-y-6">
      {/* Year selector */}
      {availableYears.length > 0 && (
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-400">Year:</span>
          <div className="inline-flex rounded-lg border border-slate-700 overflow-hidden">
            <button
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                selectedYear === ""
                  ? "bg-slate-700 text-white"
                  : "bg-slate-800/50 text-slate-400 hover:text-white"
              }`}
              onClick={() => onYearChange("")}
            >
              All Years
            </button>
            {availableYears.map((y) => (
              <button
                key={y}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  selectedYear === String(y)
                    ? "bg-slate-700 text-white"
                    : "bg-slate-800/50 text-slate-400 hover:text-white"
                }`}
                onClick={() => onYearChange(String(y))}
              >
                {y}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card p-4">
          <p className="text-2xl font-bold text-white">{formatCompactCurrency(grandTotal)}</p>
          <p className="text-xs text-slate-500 mt-1">Total True Cost{selectedYear ? ` (${selectedYear})` : " (2023–present)"}</p>
        </div>
        <div className="card p-4">
          <p className="text-2xl font-bold text-emerald-400">{formatCompactCurrency(totalPayroll)}</p>
          <p className="text-xs text-slate-500 mt-1">Budgeted Payroll{selectedYear ? ` (${selectedYear})` : ""}</p>
        </div>
        <div className="card p-4">
          <p className="text-2xl font-bold text-blue-400">{formatNumber(data.totals?.total_employees || 0)}</p>
          <p className="text-xs text-slate-500 mt-1">Budgeted Positions</p>
        </div>
        <div className="card p-4">
          <p className="text-2xl font-bold text-slate-200">{sorted.length}</p>
          <p className="text-xs text-slate-500 mt-1">Departments with cost data</p>
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 text-xs text-slate-400">
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-emerald-500 inline-block" /> Confirmed
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-blue-500 inline-block" /> Attributed
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-amber-500/70 inline-block border border-dashed border-amber-500/50" /> Estimated
        </span>
      </div>

      {/* Department list */}
      <div className="space-y-2">
        {sorted.map((dept) => {
          const isExpanded = expandedDept === dept.department_name;
          const pctOfTotal = grandTotal > 0 ? ((dept.total_true_cost / grandTotal) * 100).toFixed(1) : "0.0";
          const confirmed = dept.total_salary + dept.confirmed_payments + dept.confirmed_contracts;

          return (
            <div key={dept.department_name} className="card overflow-hidden">
              <button
                className="w-full text-left p-4 hover:bg-slate-800/50 transition-colors"
                onClick={() => setExpandedDept(isExpanded ? null : dept.department_name)}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <svg
                      className={`w-4 h-4 text-slate-500 transition-transform ${isExpanded ? "rotate-90" : ""}`}
                      fill="none" viewBox="0 0 24 24" stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                    <span className="text-white font-medium">{dept.department_name}</span>
                  </div>
                  <div className="flex items-center gap-4 text-sm">
                    <span className="text-slate-400">{formatNumber(dept.employee_count)} employees</span>
                    <span className="text-white font-semibold">{formatCompactCurrency(dept.total_true_cost)}</span>
                    <span className="text-slate-500 text-xs w-12 text-right">{pctOfTotal}%</span>
                  </div>
                </div>
                <StackedBar dept={dept} maxCost={maxCost} />
              </button>

              {/* Expanded detail */}
              {isExpanded && (
                <div className="border-t border-slate-700/50 p-4 bg-slate-800/30">
                  {/* Cost breakdown */}
                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-5">
                    <div className="bg-slate-800/60 rounded-lg p-3">
                      <p className="text-sm font-bold text-emerald-400">{formatCompactCurrency(dept.total_salary)}</p>
                      <p className="text-[10px] text-slate-500">Salary</p>
                    </div>
                    <div className="bg-slate-800/60 rounded-lg p-3">
                      <p className="text-sm font-bold text-emerald-400">{formatCompactCurrency(dept.confirmed_payments)}</p>
                      <p className="text-[10px] text-slate-500">Confirmed Payments</p>
                    </div>
                    <div className="bg-slate-800/60 rounded-lg p-3">
                      <p className="text-sm font-bold text-emerald-400">{formatCompactCurrency(dept.confirmed_contracts)}</p>
                      <p className="text-[10px] text-slate-500">Contracts</p>
                    </div>
                    <div className="bg-slate-800/60 rounded-lg p-3">
                      <p className="text-sm font-bold text-blue-400">{formatCompactCurrency(dept.attributed_total)}</p>
                      <p className="text-[10px] text-slate-500">Attributed</p>
                    </div>
                    <div className="bg-slate-800/60 rounded-lg p-3">
                      <p className="text-sm font-bold text-amber-400">{formatCompactCurrency(dept.estimated_total)}</p>
                      <p className="text-[10px] text-slate-500">Estimated</p>
                    </div>
                  </div>

                  <div className="text-xs text-slate-400 mb-3">
                    Confirmed total: {formatCurrency(confirmed)}
                  </div>

                  {/* Detail table */}
                  {dept.detail && dept.detail.length > 0 && (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-slate-500 text-xs border-b border-slate-700/50">
                            <th className="text-left py-2 pr-3 font-medium">Source Vendor</th>
                            <th className="text-right py-2 px-3 font-medium">Amount</th>
                            <th className="text-center py-2 px-3 font-medium">Tier</th>
                            <th className="text-left py-2 pl-3 font-medium">Reason</th>
                          </tr>
                        </thead>
                        <tbody>
                          {dept.detail.map((item, idx) => (
                            <tr key={idx} className="border-b border-slate-800/50">
                              <td className="py-2 pr-3 text-slate-300">{item.source_vendor}</td>
                              <td className="py-2 px-3 text-right text-slate-200 font-medium">
                                {formatCompactCurrency(item.amount)}
                              </td>
                              <td className="py-2 px-3 text-center">
                                <TierBadge tier={item.tier} />
                              </td>
                              <td className="py-2 pl-3 text-slate-400 text-xs">{item.reason}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Disclaimer */}
      <div className="card p-4 border border-amber-500/20 bg-amber-500/5">
        <p className="text-xs text-amber-400/80">
          True cost figures combine confirmed payments with attributed and estimated allocations, computed annually.
          Salary data from Chicago Budget Ordinance (budgeted positions); 2026 uses current salary snapshot.
          Use the year selector above to view individual years. Global date filters do not apply to this view.
        </p>
      </div>

      {/* Methodology panel */}
      <div className="card overflow-hidden">
        <button
          className="w-full text-left p-4 flex items-center justify-between hover:bg-slate-800/50 transition-colors"
          onClick={() => setShowMethodology(!showMethodology)}
        >
          <span className="text-sm font-semibold text-white">Methodology</span>
          <svg
            className={`w-4 h-4 text-slate-500 transition-transform ${showMethodology ? "rotate-180" : ""}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        {showMethodology && (
          <div className="border-t border-slate-700/50 p-4 text-sm text-slate-400 space-y-3">
            <div>
              <span className="inline-block w-3 h-3 rounded-sm bg-emerald-500 mr-2 align-middle" />
              <strong className="text-emerald-400">Confirmed</strong> -- Definitive costs: employee salaries, payments tagged to the department, and department-specific contracts. This is trustworthy data.
            </div>
            <div>
              <span className="inline-block w-3 h-3 rounded-sm bg-blue-500 mr-2 align-middle" />
              <strong className="text-blue-400">Attributed</strong> -- High-confidence allocations: pension funds, single-department vendors, and other costs strongly linked to a specific department.
            </div>
            <div>
              <span className="inline-block w-3 h-3 rounded-sm bg-amber-500/70 mr-2 align-middle border border-dashed border-amber-500/50" />
              <strong className="text-amber-400">Estimated</strong> -- Proportional allocations of shared costs (e.g., health insurance, utilities) distributed by headcount or other heuristics.
            </div>
            <div className="text-xs text-slate-500 pt-2 border-t border-slate-700/50">
              Note: Salary data from Chicago Budget Ordinance (budgeted positions per year). 2026 uses current employee salary snapshot.
              All payment data is scoped to 2023 and later. Estimated figures are approximations and should be interpreted with appropriate caution.
            </div>
            {data.methodology && (
              <div className="text-xs text-slate-500 whitespace-pre-wrap">{data.methodology}</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function Departments() {
  const { applyToParams, dateFilter } = useDateFilter();
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDept, setSelectedDept] = useState<DeptDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [viewMode, setViewMode] = useState<ViewMode>("payment");
  const [trueCostData, setTrueCostData] = useState<TrueCostResponse | null>(null);
  const [trueCostLoading, setTrueCostLoading] = useState(false);
  const [trueCostError, setTrueCostError] = useState<string | null>(null);
  const [trueCostYear, setTrueCostYear] = useState<string>("");

  useEffect(() => {
    setLoading(true);
    getDepartments(applyToParams({}))
      .then((res) => setDepartments(res.departments.filter(d => d.department_name)))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [dateFilter.startDate, dateFilter.endDate]);

  const fetchTrueCost = (year: string) => {
    setTrueCostLoading(true);
    setTrueCostError(null);
    const params: Record<string, string> = {};
    if (year) params.year = year;
    getDepartmentTrueCost(params)
      .then((res) => setTrueCostData(res))
      .catch((err) => setTrueCostError(err.message))
      .finally(() => setTrueCostLoading(false));
  };

  const handleToggleTrueCost = () => {
    if (viewMode === "truecost") {
      setViewMode("payment");
      return;
    }
    setViewMode("truecost");
    if (!trueCostData) {
      fetchTrueCost(trueCostYear);
    }
  };

  const handleTrueCostYearChange = (year: string) => {
    setTrueCostYear(year);
    fetchTrueCost(year);
  };

  const handleRowClick = async (row: Department) => {
    if (!row.department_name) return;
    setDetailLoading(true);
    try {
      const detail = await getDepartmentDetail(row.department_name, applyToParams({}));
      setSelectedDept(detail as unknown as DeptDetail);
    } catch {
      setSelectedDept(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const totalSpending = departments.reduce((sum, d) => sum + d.total_spending, 0);

  const columns: Column<Department>[] = [
    {
      key: "department_name",
      header: "Department",
      render: (row) => (
        <span className="text-white font-medium">{row.department_name}</span>
      ),
    },
    {
      key: "total_spending",
      header: "Total Spending",
      render: (row) => (
        <span className="text-emerald-400 font-medium">
          {formatCurrency(row.total_spending)}
        </span>
      ),
      className: "text-right",
    },
    {
      key: "pct",
      header: "% of Total",
      render: (row) => (
        <span className="text-slate-400">
          {totalSpending > 0 ? ((row.total_spending / totalSpending) * 100).toFixed(1) : 0}%
        </span>
      ),
      className: "text-right",
    },
    {
      key: "payment_count",
      header: "Payments",
      render: (row) => (
        <span className="text-slate-400">{formatNumber(row.payment_count)}</span>
      ),
      className: "text-right",
    },
    {
      key: "vendor_count",
      header: "Vendors",
      render: (row) => (
        <span className="text-slate-400">{formatNumber(row.vendor_count)}</span>
      ),
      className: "text-right",
    },
    {
      key: "risk_score",
      header: "Risk",
      render: (row) => <RiskBadge score={row.risk_score} />,
      className: "text-right",
    },
  ];

  return (
    <div>
      <div className="flex items-end justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Departments</h1>
          <p className="text-slate-500 text-sm mt-1">
            City department spending analysis
          </p>
        </div>
        <div className="flex items-center gap-4">
          {/* View toggle */}
          <div className="inline-flex rounded-lg border border-slate-700 overflow-hidden">
            <button
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                viewMode === "payment"
                  ? "bg-slate-700 text-white"
                  : "bg-slate-800/50 text-slate-400 hover:text-white"
              }`}
              onClick={() => setViewMode("payment")}
            >
              Payment View
            </button>
            <button
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                viewMode === "truecost"
                  ? "bg-slate-700 text-white"
                  : "bg-slate-800/50 text-slate-400 hover:text-white"
              }`}
              onClick={handleToggleTrueCost}
            >
              True Cost View
            </button>
          </div>
          {viewMode === "payment" && !loading && departments.length > 0 && (
            <div className="text-right">
              <p className="text-2xl font-bold text-white">{formatCompactCurrency(totalSpending)}</p>
              <p className="text-xs text-slate-500">Total Spending ({departments.length} departments)</p>
            </div>
          )}
        </div>
      </div>

      {viewMode === "payment" ? (
        <>
          {loading ? (
            <div className="card p-8 text-center">
              <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
              <p className="text-slate-500 text-sm">Loading departments...</p>
            </div>
          ) : error ? (
            <div className="card p-8 text-center text-red-400">{error}</div>
          ) : (
            <DataTable
              columns={columns}
              data={departments}
              keyField="department_name"
              onRowClick={(row) => handleRowClick(row as unknown as Department)}
              emptyMessage="No departments found"
            />
          )}
        </>
      ) : (
        <TrueCostView
          data={trueCostData}
          loading={trueCostLoading}
          error={trueCostError}
          selectedYear={trueCostYear}
          onYearChange={handleTrueCostYearChange}
        />
      )}

      {/* Department Detail Modal */}
      {(selectedDept || detailLoading) && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedDept(null)}
        >
          <div
            className="card p-6 max-w-3xl w-full max-h-[85vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {detailLoading ? (
              <div className="text-center py-8">
                <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
              </div>
            ) : selectedDept ? (
              <>
                <div className="flex items-start justify-between mb-5">
                  <h2 className="text-xl font-bold text-white">
                    {selectedDept.summary.department_name}
                  </h2>
                  <button
                    onClick={() => setSelectedDept(null)}
                    className="text-slate-500 hover:text-white text-xl leading-none"
                  >
                    &times;
                  </button>
                </div>

                {/* Summary */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
                  <div className="bg-slate-800/50 rounded-lg p-3">
                    <p className="text-lg font-bold text-emerald-400">
                      {formatCompactCurrency(selectedDept.summary.total_spending)}
                    </p>
                    <p className="text-xs text-slate-500">Total Spending</p>
                  </div>
                  <div className="bg-slate-800/50 rounded-lg p-3">
                    <p className="text-lg font-bold text-blue-400">
                      {formatNumber(selectedDept.summary.payment_count)}
                    </p>
                    <p className="text-xs text-slate-500">Payments</p>
                  </div>
                  <div className="bg-slate-800/50 rounded-lg p-3">
                    <p className="text-lg font-bold text-slate-200">
                      {formatNumber(selectedDept.summary.vendor_count)}
                    </p>
                    <p className="text-xs text-slate-500">Vendors</p>
                  </div>
                  <div className="bg-slate-800/50 rounded-lg p-3">
                    <p className="text-lg font-bold text-slate-200">
                      {formatCurrency(selectedDept.summary.avg_payment)}
                    </p>
                    <p className="text-xs text-slate-500">Avg Payment</p>
                  </div>
                </div>

                {/* Concentration */}
                {selectedDept.concentration && selectedDept.concentration.hhi > 0 && (
                  <div className="mb-5 bg-slate-800/50 rounded-lg p-3">
                    <h3 className="text-sm font-semibold text-white mb-2">Vendor Concentration</h3>
                    <div className="flex gap-4 text-xs">
                      <span className="text-slate-400">
                        HHI: <span className="text-white font-medium">{(selectedDept.concentration.hhi * 10000).toFixed(0)}</span>
                      </span>
                      <span className="text-slate-400">
                        Top vendor share: <span className="text-white font-medium">{((selectedDept.concentration.top_vendor_share || 0) * 100).toFixed(1)}%</span>
                      </span>
                      <span className="text-slate-400">
                        Vendors: <span className="text-white font-medium">{selectedDept.concentration.total_vendors}</span>
                      </span>
                    </div>
                  </div>
                )}

                {/* Top Vendors */}
                {selectedDept.top_vendors && selectedDept.top_vendors.length > 0 && (
                  <div className="mb-5">
                    <h3 className="text-sm font-semibold text-white mb-3">
                      Top Vendors
                    </h3>
                    <div className="space-y-2">
                      {selectedDept.top_vendors.slice(0, 10).map((v) => {
                        const maxV = Math.max(
                          ...selectedDept.top_vendors.map((tv) => tv.total_paid)
                        );
                        return (
                          <div key={v.vendor_name}>
                            <div className="flex justify-between text-xs mb-1">
                              <span className="text-slate-400 truncate mr-2">
                                {v.vendor_name}
                              </span>
                              <span className="text-slate-300 whitespace-nowrap">
                                {formatCompactCurrency(v.total_paid)} ({v.payment_count})
                              </span>
                            </div>
                            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-emerald-500 rounded-full"
                                style={{
                                  width: `${(v.total_paid / maxV) * 100}%`,
                                }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Flags */}
                {selectedDept.flags && selectedDept.flags.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-white mb-3">
                      Alerts ({selectedDept.flags.length})
                    </h3>
                    <div className="space-y-2 max-h-60 overflow-auto">
                      {selectedDept.flags.slice(0, 20).map((f, i) => (
                        <div
                          key={i}
                          className="bg-slate-800/50 rounded p-2 text-xs"
                        >
                          <div className="flex items-center gap-2 mb-1">
                            <span className="bg-slate-700 text-slate-300 px-2 py-0.5 rounded text-[10px] font-medium">
                              {f.flag_type}
                            </span>
                            <RiskBadge score={f.risk_score} />
                          </div>
                          <p className="text-slate-400">{f.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
