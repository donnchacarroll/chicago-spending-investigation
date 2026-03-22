import { useEffect, useState, useCallback } from "react";
import { getVendors, getVendorDetail } from "../lib/api";
import { useDateFilter } from "../lib/DateFilterContext";
import type { Vendor, VendorsResponse, VendorDetail } from "../lib/api";
import {
  formatCurrency,
  formatCompactCurrency,
  formatNumber,
} from "../lib/formatters";
import DataTable from "../components/DataTable";
import type { Column } from "../components/DataTable";
import RiskBadge from "../components/RiskBadge";
import Pagination from "../components/Pagination";

export default function Vendors() {
  const { applyToParams, dateFilter } = useDateFilter();
  const [data, setData] = useState<VendorsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  // Vendor detail
  const [selectedVendor, setSelectedVendor] = useState<VendorDetail | null>(
    null
  );
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {
        page: String(page),
        per_page: "50",
      };
      if (search) params.search = search;
      const result = await getVendors(applyToParams(params));
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [page, search, dateFilter.startDate, dateFilter.endDate]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleRowClick = async (row: Vendor) => {
    setDetailLoading(true);
    try {
      const detail = await getVendorDetail(row.vendor_name);
      setSelectedVendor(detail as unknown as VendorDetail);
    } catch {
      setSelectedVendor(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleSearch = () => {
    setPage(1);
    fetchData();
  };

  const columns: Column<Vendor>[] = [
    {
      key: "vendor_name",
      header: "Vendor",
      render: (row) => (
        <span className="text-white font-medium">{row.vendor_name}</span>
      ),
    },
    {
      key: "total_paid",
      header: "Total Paid",
      render: (row) => (
        <span className="text-emerald-400 font-medium">
          {formatCurrency(row.total_paid)}
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
      key: "department_count",
      header: "Depts",
      render: (row) => (
        <span className="text-slate-400 text-xs">
          {row.department_count}
        </span>
      ),
    },
    {
      key: "risk_score",
      header: "Risk",
      render: (row) => <RiskBadge score={row.risk_score} />,
    },
  ];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Vendors</h1>
        <p className="text-slate-500 text-sm mt-1">
          Investigate vendor payment patterns and risk profiles
        </p>
      </div>

      {/* Search */}
      <div className="card p-4 mb-4">
        <div className="flex gap-3">
          <input
            type="text"
            placeholder="Search vendors by name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="input-field px-3 py-2 flex-1"
          />
          <button onClick={handleSearch} className="btn-primary">
            Search
          </button>
          {search && (
            <button
              onClick={() => {
                setSearch("");
                setPage(1);
              }}
              className="btn-secondary"
            >
              Clear
            </button>
          )}
        </div>
        {data && (
          <p className="text-xs text-slate-500 mt-2">
            {data.total.toLocaleString()} vendors found
          </p>
        )}
      </div>

      {/* Results */}
      {loading ? (
        <div className="card p-8 text-center">
          <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          <p className="text-slate-500 text-sm">Loading vendors...</p>
        </div>
      ) : error ? (
        <div className="card p-8 text-center text-red-400">{error}</div>
      ) : data ? (
        <>
          <DataTable
            columns={columns}
            data={data.vendors}
            keyField="vendor_name"
            onRowClick={(row) => handleRowClick(row as unknown as Vendor)}
            emptyMessage="No vendors found"
          />
          <Pagination
            page={data.page}
            pages={data.pages}
            total={data.total}
            perPage={data.per_page}
            onPageChange={setPage}
          />
        </>
      ) : null}

      {/* Vendor Detail Panel */}
      {selectedVendor && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedVendor(null)}
        >
          <div
            className="card p-6 max-w-3xl w-full max-h-[85vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {detailLoading ? (
              <div className="text-center py-8">
                <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
              </div>
            ) : (
              <>
                <div className="flex items-start justify-between mb-5">
                  <div>
                    <h2 className="text-xl font-bold text-white">
                      {selectedVendor.summary.vendor_name}
                    </h2>
                    <div className="mt-1">
                      <RiskBadge score={selectedVendor.summary.risk_score} />
                    </div>
                  </div>
                  <button
                    onClick={() => setSelectedVendor(null)}
                    className="text-slate-500 hover:text-white text-xl leading-none"
                  >
                    &times;
                  </button>
                </div>

                {/* Summary stats */}
                <div className="grid grid-cols-3 gap-4 mb-6">
                  <div className="bg-slate-800/50 rounded-lg p-3">
                    <p className="text-lg font-bold text-emerald-400">
                      {formatCompactCurrency(selectedVendor.summary.total_paid)}
                    </p>
                    <p className="text-xs text-slate-500">Total Paid</p>
                  </div>
                  <div className="bg-slate-800/50 rounded-lg p-3">
                    <p className="text-lg font-bold text-blue-400">
                      {formatNumber(selectedVendor.summary.payment_count)}
                    </p>
                    <p className="text-xs text-slate-500">Payments</p>
                  </div>
                  <div className="bg-slate-800/50 rounded-lg p-3">
                    <p className="text-lg font-bold text-slate-200">
                      {formatCurrency(selectedVendor.summary.avg_payment)}
                    </p>
                    <p className="text-xs text-slate-500">Avg Payment</p>
                  </div>
                </div>

                {/* Departments */}
                {selectedVendor.departments.length > 0 && (
                  <div className="mb-5">
                    <h3 className="text-sm font-semibold text-white mb-3">
                      Department Breakdown
                    </h3>
                    <div className="space-y-2">
                      {selectedVendor.departments.map((dept) => {
                        const maxDept = Math.max(
                          ...selectedVendor.departments.map((d) => d.total_paid)
                        );
                        return (
                          <div key={dept.department_name}>
                            <div className="flex justify-between text-xs mb-1">
                              <span className="text-slate-400">
                                {dept.department_name || "Unassigned"}
                              </span>
                              <span className="text-slate-300">
                                {formatCompactCurrency(dept.total_paid)} ({dept.payment_count} payments)
                              </span>
                            </div>
                            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-blue-500 rounded-full"
                                style={{
                                  width: `${(dept.total_paid / maxDept) * 100}%`,
                                }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Contracts */}
                {selectedVendor.contracts.length > 0 && (
                  <div className="mb-5">
                    <h3 className="text-sm font-semibold text-white mb-3">
                      Contracts
                    </h3>
                    <div className="space-y-1.5">
                      {selectedVendor.contracts.map((c, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between bg-slate-800/50 rounded px-3 py-2 text-sm"
                        >
                          <span className="text-slate-300 font-medium">
                            #{c.contract_number}
                          </span>
                          <span className="text-emerald-400">
                            {formatCurrency(c.award_amount)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Flags */}
                {selectedVendor.flags.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-white mb-3">
                      Alerts ({selectedVendor.flags.length})
                    </h3>
                    <div className="space-y-2 max-h-60 overflow-auto">
                      {selectedVendor.flags.slice(0, 20).map((flag, i) => (
                        <div
                          key={i}
                          className="bg-slate-800/50 rounded-lg p-3 border border-slate-700"
                        >
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs font-medium text-orange-400 uppercase">
                              {flag.flag_type}
                            </span>
                            <RiskBadge score={flag.risk_score} />
                          </div>
                          <p className="text-sm text-slate-400">
                            {flag.description}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
