import { useEffect, useState } from "react";
import { getDepartments, getDepartmentDetail } from "../lib/api";
import { useDateFilter } from "../lib/DateFilterContext";
import type { Department } from "../lib/api";
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

export default function Departments() {
  const { applyToParams, dateFilter } = useDateFilter();
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDept, setSelectedDept] = useState<DeptDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    getDepartments(applyToParams({}))
      .then((res) => setDepartments(res.departments.filter(d => d.department_name)))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [dateFilter.startDate, dateFilter.endDate]);

  const handleRowClick = async (row: Department) => {
    if (!row.department_name) return;
    setDetailLoading(true);
    try {
      const detail = await getDepartmentDetail(row.department_name);
      setSelectedDept(detail as unknown as DeptDetail);
    } catch {
      setSelectedDept(null);
    } finally {
      setDetailLoading(false);
    }
  };

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
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Departments</h1>
        <p className="text-slate-500 text-sm mt-1">
          City department spending analysis
        </p>
      </div>

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
          data={departments as unknown as Record<string, unknown>[]}
          keyField="department_name"
          onRowClick={(row) => handleRowClick(row as unknown as Department)}
          emptyMessage="No departments found"
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
