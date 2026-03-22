import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getOverview, getAlertsSummary } from "../lib/api";
import { useDateFilter } from "../lib/DateFilterContext";
import type { OverviewData, AlertsSummary } from "../lib/api";
import {
  formatCompactCurrency,
  formatNumber,
  riskColor,
} from "../lib/formatters";
import StatCard from "../components/StatCard";
import RiskBadge from "../components/RiskBadge";

export default function Dashboard() {
  const { applyToParams, dateFilter } = useDateFilter();
  const [data, setData] = useState<OverviewData | null>(null);
  const [alerts, setAlerts] = useState<AlertsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    const params = applyToParams({});
    Promise.all([getOverview(params), getAlertsSummary()])
      .then(([overview, alertsSummary]) => {
        setData(overview);
        setAlerts(alertsSummary);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [dateFilter.startDate, dateFilter.endDate]);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;
  if (!data) return null;

  const maxDeptSpending = Math.max(
    ...data.spending_by_department.map((d) => d.total_spending)
  );
  const maxVendorSpending = Math.max(
    ...data.top_vendors.map((v) => v.total_paid)
  );

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-slate-500 text-sm mt-1">
          Chicago spending investigation overview
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard
          label="Total Spending"
          value={formatCompactCurrency(data.total_spending)}
          accent="text-emerald-400"
          icon={
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
        />
        <StatCard
          label="Total Payments"
          value={formatNumber(data.total_payments)}
          accent="text-blue-400"
          icon={
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 002.25-2.25V6.75A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25v10.5A2.25 2.25 0 004.5 19.5z" />
            </svg>
          }
        />
        <StatCard
          label="Flagged Payments"
          value={formatNumber(data.flagged_payments_count)}
          accent="text-orange-400"
          icon={
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 3v1.5M3 21v-6m0 0l2.77-.693a9 9 0 016.208.682l.108.054a9 9 0 006.086.71l3.114-.732a48.524 48.524 0 01-.005-10.499l-3.11.732a9 9 0 01-6.085-.711l-.108-.054a9 9 0 00-6.208-.682L3 4.5M3 15V4.5" />
            </svg>
          }
        />
        <StatCard
          label="High-Risk Vendors"
          value={formatNumber(data.high_risk_vendors_count)}
          accent="text-red-400"
          icon={
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
            </svg>
          }
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Spending by Department */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
              Spending by Department
            </h2>
            <Link
              to="/departments"
              className="text-xs text-blue-400 hover:text-blue-300"
            >
              View all
            </Link>
          </div>
          <div className="space-y-3">
            {data.spending_by_department.filter(d => d.department_name).slice(0, 12).map((dept) => (
              <div key={dept.department_name}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-400 truncate mr-2 max-w-[60%]">
                    {dept.department_name}
                  </span>
                  <span className="text-slate-300 font-medium whitespace-nowrap">
                    {formatCompactCurrency(dept.total_spending)}
                  </span>
                </div>
                <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500 rounded-full transition-all"
                    style={{
                      width: `${(dept.total_spending / maxDeptSpending) * 100}%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Top Vendors */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
              Top 20 Vendors
            </h2>
            <Link
              to="/vendors"
              className="text-xs text-blue-400 hover:text-blue-300"
            >
              View all
            </Link>
          </div>
          <div className="space-y-2.5">
            {data.top_vendors.slice(0, 20).map((vendor) => (
              <div key={vendor.vendor_name} className="group">
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-slate-400 truncate mr-2 max-w-[45%]">
                    {vendor.vendor_name}
                  </span>
                  <div className="flex items-center gap-2">
                    <RiskBadge score={vendor.risk_score} showScore={false} />
                    <span className="text-slate-300 font-medium whitespace-nowrap">
                      {formatCompactCurrency(vendor.total_paid)}
                    </span>
                  </div>
                </div>
                <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      vendor.risk_score >= 75
                        ? "bg-red-500"
                        : vendor.risk_score >= 50
                        ? "bg-orange-500"
                        : vendor.risk_score >= 25
                        ? "bg-yellow-500"
                        : "bg-emerald-500"
                    }`}
                    style={{
                      width: `${(vendor.total_paid / maxVendorSpending) * 100}%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Spending by Year */}
      {data.spending_by_year.length > 0 && (
        <div className="card p-5 mb-6">
          <h2 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">
            Spending by Year
          </h2>
          <div className="flex items-end gap-2 h-40">
            {data.spending_by_year.map((yr) => {
              const maxYr = Math.max(
                ...data.spending_by_year.map((y) => y.total_spending)
              );
              const pct = maxYr > 0 ? (yr.total_spending / maxYr) * 100 : 0;
              return (
                <div
                  key={yr.year}
                  className="flex-1 flex flex-col items-center gap-1"
                >
                  <span className="text-xs text-slate-400">
                    {formatCompactCurrency(yr.total_spending)}
                  </span>
                  <div
                    className="w-full bg-blue-500/80 rounded-t transition-all"
                    style={{ height: `${pct}%`, minHeight: "4px" }}
                  />
                  <span className="text-xs text-slate-500">{yr.year}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Alert Summary */}
      {alerts && (
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
              Alert Summary
            </h2>
            <Link
              to="/alerts"
              className="text-xs text-blue-400 hover:text-blue-300"
            >
              View all alerts
            </Link>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
            <div className="bg-slate-800/50 rounded-lg p-3">
              <p className="text-2xl font-bold text-white">
                {formatNumber(alerts.total_count)}
              </p>
              <p className="text-xs text-slate-500">Total Alerts</p>
            </div>
            <div className="bg-red-500/10 rounded-lg p-3 border border-red-500/20">
              <p className={`text-2xl font-bold ${riskColor(100)}`}>
                {formatNumber(alerts.critical_count)}
              </p>
              <p className="text-xs text-slate-500">Critical</p>
            </div>
          </div>
          <div className="space-y-2">
            {alerts.by_flag_type.map((ft) => (
              <div
                key={ft.flag_type}
                className="flex items-center justify-between text-sm"
              >
                <span className="text-slate-400">{ft.flag_type}</span>
                <span className="text-slate-300 font-medium">{ft.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function LoadingState() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-slate-500 text-sm">Loading dashboard data...</p>
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="card p-6 text-center max-w-md">
        <div className="text-red-400 text-4xl mb-3">!</div>
        <h2 className="text-white font-semibold mb-1">Failed to load data</h2>
        <p className="text-slate-400 text-sm">{message}</p>
        <p className="text-slate-500 text-xs mt-2">
          Make sure the API server is running at http://localhost:5000
        </p>
      </div>
    </div>
  );
}
