import { useEffect, useState, useCallback } from "react";
import {
  getContracts,
  getContractDetail,
  getContractsSummary,
} from "../lib/api";
import { useDateFilter } from "../lib/DateFilterContext";
import type {
  ContractListItem,
  ContractsResponse,
  ContractDetail,
  ContractSummary,
} from "../lib/api";
import {
  formatCurrency,
  formatCompactCurrency,
  formatDate,
  formatNumber,
} from "../lib/formatters";
import Pagination from "../components/Pagination";

const CONTRACT_TYPES = [
  "DELEGATE AGENCY",
  "CONSTRUCTION",
  "COMMODITIES",
  "PROFESSIONAL SERVICES",
  "SERVICE",
  "SUPPLY",
  "EQUIPMENT",
  "LEASE",
];

const PROCUREMENT_TYPES = ["BID", "RFP", "SOLE SOURCE", "EMERGENCY"];

const SORT_OPTIONS = [
  { value: "award_amount", label: "Award Amount" },
  { value: "total_paid", label: "Total Paid" },
  { value: "overspend_ratio", label: "Overspend Ratio" },
  { value: "payment_count", label: "Payment Count" },
  { value: "start_date", label: "Start Date" },
  { value: "end_date", label: "End Date" },
];

function overspendColor(ratio: number): string {
  if (ratio <= 1.0) return "text-green-400";
  if (ratio <= 1.5) return "text-orange-400";
  return "text-red-400";
}

function overspendBg(ratio: number): string {
  if (ratio <= 1.0) return "bg-green-500/20 text-green-400 border-green-500/30";
  if (ratio <= 1.5) return "bg-orange-500/20 text-orange-400 border-orange-500/30";
  return "bg-red-500/20 text-red-400 border-red-500/30";
}

export default function Contracts() {
  const { applyToParams, dateFilter } = useDateFilter();

  const [data, setData] = useState<ContractsResponse | null>(null);
  const [summary, setSummary] = useState<ContractSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [department, setDepartment] = useState("");
  const [contractType, setContractType] = useState("");
  const [procurementType, setProcurementType] = useState("");
  const [minAward, setMinAward] = useState("");
  const [maxAward, setMaxAward] = useState("");
  const [overspendOnly, setOverspendOnly] = useState(false);
  const [sort, setSort] = useState("award_amount");
  const [sortDir, setSortDir] = useState<"desc" | "asc">("desc");

  // Detail modal
  const [selectedContract, setSelectedContract] = useState<string | null>(null);
  const [detail, setDetail] = useState<ContractDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Debounced search
  const [debouncedSearch, setDebouncedSearch] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Fetch summary once
  useEffect(() => {
    getContractsSummary()
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
        sort,
        sort_dir: sortDir,
      };
      if (debouncedSearch) params.search = debouncedSearch;
      if (department) params.department = department;
      if (contractType) params.contract_type = contractType;
      if (procurementType) params.procurement_type = procurementType;
      if (minAward) params.min_award = minAward;
      if (maxAward) params.max_award = maxAward;
      if (overspendOnly) params.overspend_only = "true";

      const contracts = await getContracts(applyToParams(params));
      setData(contracts);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [
    page,
    debouncedSearch,
    department,
    contractType,
    procurementType,
    minAward,
    maxAward,
    overspendOnly,
    sort,
    sortDir,
    dateFilter.startDate,
    dateFilter.endDate,
  ]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const openDetail = async (contractNumber: string) => {
    setSelectedContract(contractNumber);
    setDetailLoading(true);
    setDetail(null);
    try {
      const d = await getContractDetail(contractNumber);
      setDetail(d);
    } catch {
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const closeDetail = () => {
    setSelectedContract(null);
    setDetail(null);
  };

  const resetFilters = () => {
    setSearch("");
    setDepartment("");
    setContractType("");
    setProcurementType("");
    setMinAward("");
    setMaxAward("");
    setOverspendOnly(false);
    setSort("award_amount");
    setSortDir("desc");
    setPage(1);
  };

  const hasActiveFilters =
    search ||
    department ||
    contractType ||
    procurementType ||
    minAward ||
    maxAward ||
    overspendOnly;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Contracts</h1>
        <p className="text-slate-500 text-sm mt-1">
          Explore contracts, identify overspending, and investigate procurement
        </p>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          <div className="card p-4">
            <p className="text-2xl font-bold text-white">
              {formatNumber(summary.total_contracts)}
            </p>
            <p className="text-xs text-slate-500">Total Contracts</p>
          </div>
          <div className="card p-4">
            <p className="text-2xl font-bold text-blue-400">
              {formatCompactCurrency(summary.total_award_value)}
            </p>
            <p className="text-xs text-slate-500">Total Award Value</p>
          </div>
          <div className="card p-4">
            <p className="text-2xl font-bold text-emerald-400">
              {formatCompactCurrency(summary.total_paid)}
            </p>
            <p className="text-xs text-slate-500">Total Paid</p>
          </div>
          <button
            className={`card p-4 text-left transition-colors ${
              overspendOnly
                ? "border-red-500/60 bg-red-500/10"
                : "border-red-500/30 hover:bg-red-500/5 hover:border-red-500/50"
            }`}
            onClick={() => {
              setOverspendOnly(!overspendOnly);
              setPage(1);
            }}
          >
            <p className="text-2xl font-bold text-red-400">
              {formatNumber(summary.overspent_count)}
            </p>
            <p className="text-xs text-slate-500">
              Overspent Contracts
            </p>
            {summary.overspent_total_excess > 0 && (
              <p className="text-[10px] text-red-400/70 mt-0.5">
                {formatCompactCurrency(summary.overspent_total_excess)} excess
              </p>
            )}
            <p className="text-[10px] text-red-400/50 mt-1">
              {overspendOnly ? "Showing overspent — click to clear" : "Click to filter"}
            </p>
          </button>
        </div>
      )}

      {/* Filter bar */}
      <div className={`card p-4 mb-4 ${overspendOnly ? "border-red-500/40 bg-red-500/5" : ""}`}>
        <div className="flex flex-wrap gap-3 items-end">
          {/* Search */}
          <div className="flex-1 min-w-[200px]">
            <label className="text-[10px] text-slate-500 block mb-0.5">Search</label>
            <input
              type="text"
              placeholder="Contract #, vendor, description..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input-field w-full px-3 py-2"
            />
          </div>

          {/* Department */}
          <div>
            <label className="text-[10px] text-slate-500 block mb-0.5">Department</label>
            <input
              type="text"
              placeholder="Any department"
              value={department}
              onChange={(e) => {
                setDepartment(e.target.value);
                setPage(1);
              }}
              className="input-field px-3 py-2 w-44"
            />
          </div>

          {/* Contract type */}
          <div>
            <label className="text-[10px] text-slate-500 block mb-0.5">Contract Type</label>
            <select
              value={contractType}
              onChange={(e) => {
                setContractType(e.target.value);
                setPage(1);
              }}
              className="input-field"
            >
              <option value="">All Types</option>
              {CONTRACT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          {/* Procurement type */}
          <div>
            <label className="text-[10px] text-slate-500 block mb-0.5">Procurement</label>
            <select
              value={procurementType}
              onChange={(e) => {
                setProcurementType(e.target.value);
                setPage(1);
              }}
              className="input-field"
            >
              <option value="">All Procurement</option>
              {PROCUREMENT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          {/* Award range */}
          <div>
            <label className="text-[10px] text-slate-500 block mb-0.5">Award Range</label>
            <div className="flex items-center gap-1">
              <input
                type="number"
                placeholder="Min $"
                value={minAward}
                onChange={(e) => {
                  setMinAward(e.target.value);
                  setPage(1);
                }}
                className="input-field px-2 py-2 w-24"
              />
              <span className="text-slate-600">-</span>
              <input
                type="number"
                placeholder="Max $"
                value={maxAward}
                onChange={(e) => {
                  setMaxAward(e.target.value);
                  setPage(1);
                }}
                className="input-field px-2 py-2 w-24"
              />
            </div>
          </div>

          {/* Overspend only */}
          <label className="flex items-center gap-2 cursor-pointer py-2">
            <input
              type="checkbox"
              checked={overspendOnly}
              onChange={(e) => {
                setOverspendOnly(e.target.checked);
                setPage(1);
              }}
              className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-red-500 focus:ring-red-500/50"
            />
            <span className={`text-xs font-medium ${overspendOnly ? "text-red-400" : "text-slate-400"}`}>
              Overspent only
            </span>
          </label>

          {/* Sort */}
          <div>
            <label className="text-[10px] text-slate-500 block mb-0.5">Sort by</label>
            <div className="flex items-center gap-1">
              <select
                value={sort}
                onChange={(e) => {
                  setSort(e.target.value);
                  setPage(1);
                }}
                className="input-field"
              >
                {SORT_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <button
                onClick={() => setSortDir(sortDir === "desc" ? "asc" : "desc")}
                className="btn-secondary px-2 py-2 text-xs"
                title={sortDir === "desc" ? "Descending" : "Ascending"}
              >
                {sortDir === "desc" ? "\u2193" : "\u2191"}
              </button>
            </div>
          </div>

          {hasActiveFilters && (
            <button onClick={resetFilters} className="btn-secondary">
              Reset
            </button>
          )}
        </div>
        {overspendOnly && (
          <div className="mt-3 bg-red-500/10 border border-red-500/20 rounded px-3 py-2">
            <p className="text-xs text-red-400 font-medium">
              Investigation mode: showing only contracts where total paid exceeds award amount
            </p>
          </div>
        )}
      </div>

      {/* Results table */}
      {loading ? (
        <div className="card p-8 text-center">
          <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          <p className="text-slate-500 text-sm">Loading contracts...</p>
        </div>
      ) : error ? (
        <div className="card p-8 text-center text-red-400">{error}</div>
      ) : data && data.contracts.length > 0 ? (
        <>
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-slate-500 border-b border-slate-700 bg-slate-800/50">
                    <th className="text-left px-3 py-2.5">Contract #</th>
                    <th className="text-left px-3 py-2.5">Description</th>
                    <th className="text-left px-3 py-2.5">Vendor</th>
                    <th className="text-left px-3 py-2.5">Department</th>
                    <th className="text-right px-3 py-2.5">Award</th>
                    <th className="text-right px-3 py-2.5">Paid</th>
                    <th className="text-center px-3 py-2.5">Award vs Paid</th>
                    <th className="text-right px-3 py-2.5">Overspend %</th>
                    <th className="text-right px-3 py-2.5">Payments</th>
                    <th className="text-left px-3 py-2.5">Type</th>
                    <th className="text-left px-3 py-2.5">Procurement</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {data.contracts.map((c) => {
                    const overspendPct =
                      c.overspend_ratio != null
                        ? (c.overspend_ratio - 1) * 100
                        : c.award_amount > 0
                        ? ((c.total_paid - c.award_amount) / c.award_amount) * 100
                        : 0;
                    const ratio = c.overspend_ratio ?? (c.award_amount > 0 ? c.total_paid / c.award_amount : 0);

                    return (
                      <tr
                        key={c.contract_number}
                        className="hover:bg-slate-800/60 cursor-pointer transition-colors"
                        onClick={() => openDetail(c.contract_number)}
                      >
                        <td className="px-3 py-2.5 text-blue-400 font-medium whitespace-nowrap">
                          {c.contract_number}
                        </td>
                        <td className="px-3 py-2.5 text-slate-300 max-w-[200px] truncate">
                          {c.description || "—"}
                        </td>
                        <td className="px-3 py-2.5 text-slate-300 max-w-[150px] truncate">
                          {c.vendor_name || "—"}
                        </td>
                        <td className="px-3 py-2.5 text-slate-400 max-w-[120px] truncate">
                          {c.department || "—"}
                        </td>
                        <td className="px-3 py-2.5 text-right text-slate-300 whitespace-nowrap">
                          {formatCompactCurrency(c.award_amount)}
                        </td>
                        <td className="px-3 py-2.5 text-right text-slate-300 whitespace-nowrap">
                          {formatCompactCurrency(c.total_paid)}
                        </td>
                        <td className="px-3 py-2.5">
                          <AwardVsPaidBar
                            award={c.award_amount}
                            paid={c.total_paid}
                          />
                        </td>
                        <td className={`px-3 py-2.5 text-right font-medium whitespace-nowrap ${overspendColor(ratio)}`}>
                          {overspendPct > 0 ? "+" : ""}
                          {overspendPct.toFixed(0)}%
                        </td>
                        <td className="px-3 py-2.5 text-right text-slate-400">
                          {c.payment_count}
                        </td>
                        <td className="px-3 py-2.5 text-slate-500 whitespace-nowrap">
                          {c.contract_type || "—"}
                        </td>
                        <td className="px-3 py-2.5 text-slate-500 whitespace-nowrap">
                          {c.procurement_type || "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
          <Pagination
            page={data.page}
            pages={data.total_pages}
            total={data.total}
            perPage={data.per_page}
            onPageChange={setPage}
          />
        </>
      ) : (
        <div className="card p-8 text-center text-slate-500">
          No contracts match your filters
        </div>
      )}

      {/* Detail Modal */}
      {selectedContract && (
        <ContractDetailModal
          contractNumber={selectedContract}
          detail={detail}
          loading={detailLoading}
          onClose={closeDetail}
        />
      )}
    </div>
  );
}

/* ---- Award vs Paid mini bar ---- */

function AwardVsPaidBar({ award, paid }: { award: number; paid: number }) {
  if (award <= 0 && paid <= 0) return <span className="text-slate-600">—</span>;

  const max = Math.max(award, paid);
  const awardPct = max > 0 ? (award / max) * 100 : 0;
  const paidPct = max > 0 ? (paid / max) * 100 : 0;
  const isOver = paid > award;

  return (
    <div className="w-24 mx-auto">
      <div className="relative h-3 bg-slate-800 rounded-sm overflow-hidden">
        {/* Award base (blue) */}
        <div
          className="absolute inset-y-0 left-0 bg-blue-500/60 rounded-sm"
          style={{ width: `${awardPct}%` }}
        />
        {/* Paid overlay */}
        {isOver ? (
          <>
            <div
              className="absolute inset-y-0 left-0 bg-blue-500/40 rounded-sm"
              style={{ width: `${awardPct}%` }}
            />
            <div
              className="absolute inset-y-0 bg-red-500/70 rounded-r-sm"
              style={{ left: `${awardPct}%`, width: `${paidPct - awardPct}%` }}
            />
          </>
        ) : (
          <div
            className="absolute inset-y-0 left-0 bg-blue-400/50 rounded-sm"
            style={{ width: `${paidPct}%` }}
          />
        )}
      </div>
    </div>
  );
}

/* ---- Contract Detail Modal ---- */

function ContractDetailModal({
  contractNumber,
  detail,
  loading,
  onClose,
}: {
  contractNumber: string;
  detail: ContractDetail | null;
  loading: boolean;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-8 pb-8">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-4xl max-h-[90vh] overflow-y-auto bg-dashboard-card border border-dashboard-border rounded-lg shadow-2xl mx-4">
        {/* Header */}
        <div className="sticky top-0 bg-dashboard-card border-b border-dashboard-border px-6 py-4 flex items-center justify-between z-10">
          <div>
            <h2 className="text-lg font-bold text-white">
              Contract {contractNumber}
            </h2>
            {detail && (
              <p className="text-sm text-slate-400 mt-0.5 max-w-xl truncate">
                {detail.contract.description}
              </p>
            )}
          </div>
          <div className="flex items-center gap-3">
            {detail?.contract.pdf_url && (
              <a
                href={detail.contract.pdf_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-md transition-colors"
              >
                <PdfIcon />
                View PDF
              </a>
            )}
            <button
              onClick={onClose}
              className="p-2 text-slate-400 hover:text-white rounded-md hover:bg-slate-700 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="p-6">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mr-3" />
              <span className="text-slate-500">Loading contract details...</span>
            </div>
          ) : detail ? (
            <ContractDetailContent detail={detail} />
          ) : (
            <p className="text-slate-500 text-center py-12">
              Failed to load contract details
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function ContractDetailContent({ detail }: { detail: ContractDetail }) {
  const { contract, payments, monthly_spending } = detail;
  const ratio = contract.overspend_ratio ?? (contract.award_amount > 0 ? contract.total_paid / contract.award_amount : 0);
  const overspendPct = (ratio - 1) * 100;
  const isExpired = contract.end_date && new Date(contract.end_date) < new Date();
  const hasPaymentsAfterEnd =
    isExpired &&
    payments.some((p) => p.check_date && new Date(p.check_date) > new Date(contract.end_date));

  return (
    <div className="space-y-6">
      {/* Vendor info + Financial summary row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Vendor info */}
        <div className="bg-slate-800/50 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-white mb-3">Vendor Information</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-500">Vendor</span>
              <span className="text-slate-200 font-medium">{contract.vendor_name}</span>
            </div>
            {contract.vendor_id && (
              <div className="flex justify-between">
                <span className="text-slate-500">Vendor ID</span>
                <span className="text-slate-400">{contract.vendor_id}</span>
              </div>
            )}
            {(contract.address || contract.city) && (
              <div className="flex justify-between">
                <span className="text-slate-500">Address</span>
                <span className="text-slate-400 text-right">
                  {[contract.address, contract.city, contract.state, contract.zip]
                    .filter(Boolean)
                    .join(", ")}
                </span>
              </div>
            )}
            {contract.specification_number && (
              <div className="flex justify-between">
                <span className="text-slate-500">Spec #</span>
                <span className="text-slate-400">{contract.specification_number}</span>
              </div>
            )}
          </div>
        </div>

        {/* Financial summary */}
        <div className="bg-slate-800/50 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-white mb-3">Financial Summary</h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-slate-500 text-sm">Award Amount</span>
              <span className="text-blue-400 font-bold text-lg">
                {formatCurrency(contract.award_amount)}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-500 text-sm">Total Paid</span>
              <span className={`font-bold text-lg ${ratio > 1 ? "text-red-400" : "text-emerald-400"}`}>
                {formatCurrency(contract.total_paid)}
              </span>
            </div>

            {/* Overspend bar */}
            <div>
              <div className="flex justify-between items-center mb-1">
                <span className="text-slate-500 text-xs">Budget Usage</span>
                <span className={`text-xs font-medium px-2 py-0.5 rounded border ${overspendBg(ratio)}`}>
                  {overspendPct > 0 ? "+" : ""}
                  {overspendPct.toFixed(1)}%
                </span>
              </div>
              <OverspendBar award={contract.award_amount} paid={contract.total_paid} />
            </div>

            <div className="flex justify-between text-sm">
              <span className="text-slate-500">Payments</span>
              <span className="text-slate-300">{contract.payment_count}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Contract dates */}
      <div className="bg-slate-800/50 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-white mb-3">Contract Dates</h3>
        <div className="flex flex-wrap gap-6 text-sm">
          <div>
            <span className="text-slate-500">Start Date: </span>
            <span className="text-slate-300">{formatDate(contract.start_date)}</span>
          </div>
          <div>
            <span className="text-slate-500">End Date: </span>
            <span className={isExpired ? "text-orange-400 font-medium" : "text-slate-300"}>
              {formatDate(contract.end_date)}
              {isExpired && " (Expired)"}
            </span>
          </div>
          {contract.approval_date && (
            <div>
              <span className="text-slate-500">Approval Date: </span>
              <span className="text-slate-300">{formatDate(contract.approval_date)}</span>
            </div>
          )}
          <div>
            <span className="text-slate-500">Type: </span>
            <span className="text-slate-300">{contract.contract_type || "—"}</span>
          </div>
          <div>
            <span className="text-slate-500">Procurement: </span>
            <span className="text-slate-300">{contract.procurement_type || "—"}</span>
          </div>
        </div>
        {hasPaymentsAfterEnd && (
          <div className="mt-3 bg-orange-500/10 border border-orange-500/20 rounded px-3 py-2">
            <p className="text-xs text-orange-400 font-medium">
              Warning: This contract has expired but is still receiving payments
            </p>
          </div>
        )}
      </div>

      {/* Monthly spending chart */}
      {monthly_spending && monthly_spending.length > 0 && (
        <div className="bg-slate-800/50 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-white mb-3">Monthly Spending</h3>
          <MonthlyBarChart data={monthly_spending} />
        </div>
      )}

      {/* Payment list */}
      {payments && payments.length > 0 && (
        <div className="bg-slate-800/50 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-white mb-3">
            Payment History ({payments.length})
          </h3>
          <div className="max-h-64 overflow-auto rounded border border-slate-700">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-slate-500 border-b border-slate-700 bg-slate-800/50 sticky top-0">
                  <th className="text-left px-3 py-2">Voucher #</th>
                  <th className="text-left px-3 py-2">Date</th>
                  <th className="text-right px-3 py-2">Amount</th>
                  <th className="text-left px-3 py-2">Department</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {payments.map((p, i) => (
                  <tr key={`${p.voucher_number}-${i}`} className="hover:bg-slate-700/30">
                    <td className="px-3 py-1.5 text-slate-400 font-mono">
                      {p.voucher_number}
                    </td>
                    <td className="px-3 py-1.5 text-slate-400">
                      {formatDate(p.check_date)}
                    </td>
                    <td className="px-3 py-1.5 text-right text-emerald-400 font-medium">
                      {formatCurrency(p.amount)}
                    </td>
                    <td className="px-3 py-1.5 text-slate-500">
                      {p.department_name || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* PDF link at bottom too */}
      {contract.pdf_url && (
        <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-4 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-blue-400">Contract Document</p>
            <p className="text-xs text-slate-500 mt-0.5">
              View the full contract PDF for detailed terms and conditions
            </p>
          </div>
          <a
            href={contract.pdf_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-md transition-colors flex-shrink-0"
          >
            <PdfIcon />
            Open PDF
          </a>
        </div>
      )}
    </div>
  );
}

/* ---- Overspend Bar (large) ---- */

function OverspendBar({ award, paid }: { award: number; paid: number }) {
  if (award <= 0 && paid <= 0) return null;

  const max = Math.max(award, paid);
  const awardPct = max > 0 ? (Math.min(award, max) / max) * 100 : 0;
  const isOver = paid > award;
  const overPct = isOver && max > 0 ? ((paid - award) / max) * 100 : 0;

  return (
    <div>
      <div className="relative h-5 bg-slate-900 rounded overflow-hidden">
        {/* Award portion (blue) */}
        <div
          className="absolute inset-y-0 left-0 bg-blue-500/60 rounded-l"
          style={{ width: `${awardPct}%` }}
        />
        {/* Overspend portion (red) */}
        {isOver && (
          <div
            className="absolute inset-y-0 bg-red-500/70 rounded-r"
            style={{ left: `${awardPct}%`, width: `${overPct}%` }}
          />
        )}
        {/* Paid line when under budget */}
        {!isOver && paid > 0 && (
          <div
            className="absolute inset-y-0 left-0 bg-emerald-500/50"
            style={{ width: `${(paid / max) * 100}%` }}
          />
        )}
      </div>
      <div className="flex items-center gap-4 mt-1.5 text-[10px]">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 bg-blue-500/60 rounded-full inline-block" />
          <span className="text-slate-500">Award</span>
        </span>
        {isOver ? (
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 bg-red-500/70 rounded-full inline-block" />
            <span className="text-slate-500">Overspend</span>
          </span>
        ) : (
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 bg-emerald-500/50 rounded-full inline-block" />
            <span className="text-slate-500">Paid</span>
          </span>
        )}
      </div>
    </div>
  );
}

/* ---- Monthly Bar Chart ---- */

function MonthlyBarChart({
  data,
}: {
  data: Array<{ year: number; month: number; amount: number; count: number }>;
}) {
  const maxAmount = Math.max(...data.map((d) => d.amount), 1);

  return (
    <div className="flex items-end gap-px h-32 overflow-x-auto">
      {data.map((d, i) => {
        const heightPct = (d.amount / maxAmount) * 100;
        const label = `${d.year}-${String(d.month).padStart(2, "0")}`;
        return (
          <div
            key={`${d.year}-${d.month}-${i}`}
            className="flex flex-col items-center flex-shrink-0 group"
            style={{ minWidth: data.length > 24 ? 16 : 28 }}
          >
            <div className="relative w-full flex items-end justify-center h-24">
              <div
                className="w-full max-w-[20px] bg-blue-500/60 hover:bg-blue-500/80 rounded-t-sm transition-colors cursor-default"
                style={{ height: `${Math.max(heightPct, 2)}%` }}
                title={`${label}: ${formatCurrency(d.amount)} (${d.count} payments)`}
              />
            </div>
            {data.length <= 24 && (
              <span className="text-[8px] text-slate-600 mt-1 rotate-[-45deg] origin-top-left whitespace-nowrap">
                {label}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ---- Icons ---- */

function PdfIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
      />
    </svg>
  );
}
