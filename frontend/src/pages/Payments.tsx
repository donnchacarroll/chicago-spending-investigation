import { useEffect, useState, useCallback } from "react";
import {
  getPayments,
  getDepartments,
  getPaymentDetail,
} from "../lib/api";
import { useDateFilter } from "../lib/DateFilterContext";
import type { Payment, PaymentsResponse, Department } from "../lib/api";
import { formatCurrency, formatDate } from "../lib/formatters";
import DataTable from "../components/DataTable";
import type { Column } from "../components/DataTable";
import RiskBadge from "../components/RiskBadge";
import Pagination from "../components/Pagination";

export default function Payments() {
  const { applyToParams, dateFilter } = useDateFilter();
  const [data, setData] = useState<PaymentsResponse | null>(null);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPayment, setSelectedPayment] = useState<Payment | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Filters
  const [page, setPage] = useState(1);
  const [department, setDepartment] = useState("");
  const [vendor, setVendor] = useState("");
  const [minAmount, setMinAmount] = useState("");
  const [maxAmount, setMaxAmount] = useState("");
  const [minRisk, setMinRisk] = useState("");
  const [flagType, setFlagType] = useState("");

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {
        page: String(page),
        per_page: "50",
      };
      if (department) params.department = department;
      if (vendor) params.vendor = vendor;
      if (minAmount) params.min_amount = minAmount;
      if (maxAmount) params.max_amount = maxAmount;
      if (minRisk) params.min_risk_score = minRisk;
      if (flagType) params.flag_type = flagType;

      const result = await getPayments(applyToParams(params));
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [page, department, vendor, minAmount, maxAmount, minRisk, flagType, dateFilter.startDate, dateFilter.endDate]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    getDepartments()
      .then((res) => setDepartments(res.departments))
      .catch(() => {});
  }, []);

  const handleRowClick = async (row: Payment) => {
    setDetailLoading(true);
    try {
      const detail = await getPaymentDetail(row.voucher_number);
      setSelectedPayment(detail);
    } catch {
      setSelectedPayment(row);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleSearch = () => {
    setPage(1);
    fetchData();
  };

  const handleReset = () => {
    setDepartment("");
    setVendor("");
    setMinAmount("");
    setMaxAmount("");
    setMinRisk("");
    setFlagType("");
    setPage(1);
  };

  const columns: Column<Payment>[] = [
    {
      key: "check_date",
      header: "Date",
      render: (row) => (
        <span className="text-slate-400 text-xs whitespace-nowrap">
          {formatDate(row.check_date)}
        </span>
      ),
    },
    {
      key: "vendor_name",
      header: "Vendor",
      render: (row) => (
        <span className="text-white font-medium truncate max-w-[200px] block">
          {row.vendor_name}
        </span>
      ),
    },
    {
      key: "department_name",
      header: "Department",
      render: (row) => (
        <span className="text-slate-400 text-xs truncate max-w-[150px] block">
          {row.department_name}
        </span>
      ),
    },
    {
      key: "amount",
      header: "Amount",
      render: (row) => (
        <span className="text-emerald-400 font-medium whitespace-nowrap">
          {formatCurrency(row.amount)}
        </span>
      ),
      className: "text-right",
    },
    {
      key: "contract_number",
      header: "Contract",
      render: (row) => (
        <span className="text-slate-500 text-xs">
          {row.contract_number || "N/A"}
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
        <h1 className="text-2xl font-bold text-white">Payments</h1>
        <p className="text-slate-500 text-sm mt-1">
          Search and investigate individual payments
        </p>
      </div>

      {/* Filter bar */}
      <div className="card p-4 mb-4">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <select
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
            className="input-field"
          >
            <option value="">All Departments</option>
            {departments.filter(d => d.department_name).map((d) => (
              <option key={d.department_name} value={d.department_name}>
                {d.department_name}
              </option>
            ))}
          </select>

          <input
            type="text"
            placeholder="Vendor name..."
            value={vendor}
            onChange={(e) => setVendor(e.target.value)}
            className="input-field px-3 py-2"
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />

          <input
            type="number"
            placeholder="Min amount"
            value={minAmount}
            onChange={(e) => setMinAmount(e.target.value)}
            className="input-field px-3 py-2"
          />

          <input
            type="number"
            placeholder="Max amount"
            value={maxAmount}
            onChange={(e) => setMaxAmount(e.target.value)}
            className="input-field px-3 py-2"
          />

          <input
            type="number"
            placeholder="Min risk score"
            value={minRisk}
            onChange={(e) => setMinRisk(e.target.value)}
            className="input-field px-3 py-2"
            min="0"
            max="100"
          />

          <select
            value={flagType}
            onChange={(e) => setFlagType(e.target.value)}
            className="input-field"
          >
            <option value="">All Flag Types</option>
            <option value="OUTLIER_AMOUNT">Outlier Amount</option>
            <option value="DUPLICATE_PAYMENT">Duplicate Payment</option>
            <option value="SPLIT_PAYMENT">Split Payment</option>
            <option value="HIGH_CONCENTRATION">High Concentration</option>
            <option value="CONTRACT_OVERSPEND">Contract Overspend</option>
            <option value="NO_CONTRACT_HIGH_VALUE">No Contract (High Value)</option>
          </select>
        </div>

        <div className="flex gap-2 mt-3">
          <button onClick={handleSearch} className="btn-primary">
            Search
          </button>
          <button onClick={handleReset} className="btn-secondary">
            Reset
          </button>
          {data && (
            <span className="text-xs text-slate-500 self-center ml-2">
              {data.total.toLocaleString()} results
            </span>
          )}
        </div>
      </div>

      {/* Results */}
      {loading ? (
        <div className="card p-8 text-center">
          <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          <p className="text-slate-500 text-sm">Loading payments...</p>
        </div>
      ) : error ? (
        <div className="card p-8 text-center text-red-400">{error}</div>
      ) : data ? (
        <>
          <DataTable
            columns={columns}
            data={data.payments}
            keyField="voucher_number"
            onRowClick={(row) => handleRowClick(row as unknown as Payment)}
            emptyMessage="No payments match your filters"
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

      {/* Payment Detail Modal */}
      {selectedPayment && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedPayment(null)}
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
              <PaymentDetailPanel
                payment={selectedPayment}
                onClose={() => setSelectedPayment(null)}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function PaymentDetailPanel({ payment, onClose }: { payment: Payment; onClose: () => void }) {
  const ct = payment.contract;
  const vc = payment.vendor_context;
  const hasContract = ct && ct.description;

  return (
    <>
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="text-lg font-bold text-white">{payment.vendor_name}</h2>
          <p className="text-xs text-slate-500">Voucher: {payment.voucher_number}</p>
        </div>
        <button onClick={onClose} className="text-slate-500 hover:text-white text-xl leading-none">&times;</button>
      </div>

      {/* Payment basics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        <div className="bg-slate-800/50 rounded-lg p-3">
          <p className="text-lg font-bold text-emerald-400">{formatCurrency(payment.amount)}</p>
          <p className="text-[10px] text-slate-500">Payment Amount</p>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-3">
          <p className="text-sm font-medium text-slate-200">{formatDate(payment.check_date)}</p>
          <p className="text-[10px] text-slate-500">Date</p>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-3">
          <p className="text-sm font-medium text-slate-200 truncate">{payment.department_name || "N/A"}</p>
          <p className="text-[10px] text-slate-500">Department</p>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-3">
          <RiskBadge score={payment.risk_score} />
          <p className="text-[10px] text-slate-500 mt-1">Risk Score</p>
        </div>
      </div>

      {/* Category tags */}
      <div className="flex flex-wrap gap-2 mb-5">
        {payment.spending_category && (
          <span className="text-xs bg-blue-500/20 text-blue-400 border border-blue-500/30 px-2 py-1 rounded">
            {payment.spending_category}
          </span>
        )}
        {payment.dv_subcategory && (
          <span className="text-xs bg-orange-500/20 text-orange-400 border border-orange-500/30 px-2 py-1 rounded">
            {payment.dv_subcategory}
          </span>
        )}
        {payment.contract_type === "direct_voucher" && (
          <span className="text-xs bg-orange-500/20 text-orange-400 border border-orange-500/30 px-2 py-1 rounded">
            DIRECT VOUCHER — No Contract
          </span>
        )}
      </div>

      {/* Contract details */}
      {hasContract ? (
        <div className="mb-5 bg-blue-500/5 border border-blue-500/20 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-white">Contract Details</h3>
            {ct.pdf_url && (
              <a
                href={ct.pdf_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded transition-colors flex items-center gap-1"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                </svg>
                View Contract PDF
              </a>
            )}
          </div>

          {/* What is this contract for? */}
          <div className="mb-3">
            <p className="text-[10px] text-slate-500 mb-1">PURPOSE</p>
            <p className="text-sm text-slate-200">{ct.description}</p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-3">
            <div>
              <p className="text-[10px] text-slate-500">Contract #</p>
              <p className="text-xs text-slate-300 font-mono">{ct.contract_number}</p>
            </div>
            <div>
              <p className="text-[10px] text-slate-500">Type</p>
              <p className="text-xs text-slate-300">{ct.contract_type_desc}</p>
            </div>
            <div>
              <p className="text-[10px] text-slate-500">Procurement</p>
              <p className={`text-xs font-medium ${
                ct.procurement_type === "SOLE SOURCE" ? "text-orange-400" :
                ct.procurement_type === "EMERGENCY" ? "text-red-400" : "text-slate-300"
              }`}>
                {ct.procurement_type || "N/A"}
              </p>
            </div>
            <div>
              <p className="text-[10px] text-slate-500">Award Amount</p>
              <p className="text-xs text-slate-300">{ct.award_amount ? formatCurrency(ct.award_amount) : "N/A"}</p>
            </div>
            <div>
              <p className="text-[10px] text-slate-500">Period</p>
              <p className="text-xs text-slate-300">
                {ct.start_date ? ct.start_date.split("T")[0] : "?"} to {ct.end_date ? ct.end_date.split("T")[0] : "?"}
              </p>
            </div>
            {ct.specification_number && (
              <div>
                <p className="text-[10px] text-slate-500">Spec #</p>
                <p className="text-xs text-slate-300 font-mono">{ct.specification_number}</p>
              </div>
            )}
          </div>

          {/* Award vs Paid bar */}
          {ct.award_amount > 0 && ct.total_paid_on_contract > 0 && (
            <div className="mt-3">
              <p className="text-[10px] text-slate-500 mb-1">AWARD vs TOTAL PAID ON THIS CONTRACT</p>
              <div className="h-4 bg-slate-800 rounded-full overflow-hidden relative">
                <div
                  className={`h-full rounded-full ${
                    ct.total_paid_on_contract > ct.award_amount * 1.1 ? "bg-red-500" :
                    ct.total_paid_on_contract > ct.award_amount ? "bg-orange-500" : "bg-blue-500"
                  }`}
                  style={{ width: `${Math.min(100, (ct.total_paid_on_contract / ct.award_amount) * 100)}%` }}
                />
              </div>
              <div className="flex justify-between text-[10px] mt-1">
                <span className="text-slate-500">Award: {formatCurrency(ct.award_amount)}</span>
                <span className={
                  ct.total_paid_on_contract > ct.award_amount * 1.1 ? "text-red-400 font-medium" : "text-slate-400"
                }>
                  Paid: {formatCurrency(ct.total_paid_on_contract)}
                  {ct.total_paid_on_contract > ct.award_amount * 1.1 && (
                    <span className="ml-1">
                      ({((ct.total_paid_on_contract / ct.award_amount - 1) * 100).toFixed(0)}% over)
                    </span>
                  )}
                </span>
              </div>
              <p className="text-[10px] text-slate-600 mt-1">
                {ct.contract_payment_count} total payments on this contract
              </p>
            </div>
          )}

          {/* Vendor info */}
          {ct.address_1 && (
            <div className="mt-3 pt-3 border-t border-slate-700/50">
              <p className="text-[10px] text-slate-500 mb-1">VENDOR</p>
              <p className="text-xs text-slate-300">
                {ct.contract_vendor}
                {ct.vendor_id && <span className="text-slate-500 ml-2">(ID: {ct.vendor_id})</span>}
              </p>
              <p className="text-xs text-slate-500">
                {ct.address_1}{ct.city ? `, ${ct.city}` : ""} {ct.state} {ct.zip}
              </p>
            </div>
          )}
        </div>
      ) : payment.contract_type === "direct_voucher" ? (
        <div className="mb-5 bg-orange-500/5 border border-orange-500/20 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-orange-400 mb-2">No Contract on File</h3>
          <p className="text-xs text-slate-400">
            This payment was made as a direct voucher without an associated contract.
            {payment.amount > 25000 && (
              <span className="text-orange-300 font-medium">
                {" "}At {formatCurrency(payment.amount)}, this exceeds the $25,000 threshold where a contract would typically be expected.
              </span>
            )}
          </p>
        </div>
      ) : null}

      {/* Vendor context */}
      {vc && vc.total_payments > 1 && (
        <div className="mb-5 bg-slate-800/30 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-slate-300 mb-2">Vendor Payment History</h3>
          <p className="text-xs text-slate-400">
            The city has made <span className="text-white font-medium">{vc.total_payments.toLocaleString()}</span> payments
            to {payment.vendor_name} totaling <span className="text-emerald-400 font-medium">{formatCurrency(vc.total_paid)}</span>.
            Average payment: {formatCurrency(vc.avg_payment)}.
            {payment.amount > vc.avg_payment * 3 && (
              <span className="text-orange-400 font-medium">
                {" "}This payment is {(payment.amount / vc.avg_payment).toFixed(1)}x the average.
              </span>
            )}
          </p>
        </div>
      )}

      {/* Flags */}
      {payment.flags && payment.flags.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-white mb-2">
            Alerts ({payment.flags.length})
          </h3>
          <div className="space-y-2">
            {payment.flags.map((flag, i) => (
              <div key={i} className="bg-slate-800/50 rounded-lg p-3 border border-slate-700">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-medium text-orange-400 uppercase">{flag.flag_type}</span>
                  <RiskBadge score={flag.risk_score} />
                </div>
                <p className="text-sm text-slate-400">{flag.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* No flags */}
      {(!payment.flags || payment.flags.length === 0) && (
        <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-lg p-3">
          <p className="text-xs text-emerald-400">No alerts flagged for this payment.</p>
        </div>
      )}
    </>
  );
}
