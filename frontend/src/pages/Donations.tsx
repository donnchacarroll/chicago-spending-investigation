import { useEffect, useState } from "react";
import {
  getDonationsSummary,
  getVendorDonations,
  getDonationRedFlags,
} from "../lib/api";
import type {
  DonationsSummary,
  VendorDonationDetail,
  RedFlagsResponse,
} from "../lib/api";
import { formatCurrency, formatCompactCurrency, formatDate, formatNumber } from "../lib/formatters";

function ratioColor(ratio: number): string {
  if (ratio > 0.01) return "text-red-400";
  if (ratio > 0.001) return "text-yellow-400";
  return "text-green-400";
}

function ratioBgColor(ratio: number): string {
  if (ratio > 0.01) return "bg-red-500/20 text-red-400 border-red-500/30";
  if (ratio > 0.001) return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
  return "bg-green-500/20 text-green-400 border-green-500/30";
}

function formatPercent(ratio: number): string {
  return (ratio * 100).toFixed(4) + "%";
}

function flagTypeBadgeColor(flagType: string): string {
  if (flagType.includes("sole_source")) return "bg-red-500/20 text-red-400 border-red-500/30";
  if (flagType.includes("large")) return "bg-orange-500/20 text-orange-400 border-orange-500/30";
  if (flagType.includes("timing")) return "bg-purple-500/20 text-purple-400 border-purple-500/30";
  return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
}

export default function Donations() {
  const [summary, setSummary] = useState<DonationsSummary | null>(null);
  const [redFlags, setRedFlags] = useState<RedFlagsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Vendor detail drill-down
  const [expandedVendor, setExpandedVendor] = useState<string | null>(null);
  const [vendorDetail, setVendorDetail] = useState<VendorDonationDetail | null>(null);
  const [vendorDetailLoading, setVendorDetailLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([getDonationsSummary(), getDonationRedFlags()])
      .then(([s, rf]) => {
        setSummary(s);
        setRedFlags(rf);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load donations data");
      })
      .finally(() => setLoading(false));
  }, []);

  const handleVendorExpand = async (vendorName: string) => {
    if (expandedVendor === vendorName) {
      setExpandedVendor(null);
      setVendorDetail(null);
      return;
    }
    setExpandedVendor(vendorName);
    setVendorDetailLoading(true);
    try {
      const detail = await getVendorDonations(vendorName);
      setVendorDetail(detail);
    } catch {
      setVendorDetail(null);
    } finally {
      setVendorDetailLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="card p-8 text-center">
        <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
        <p className="text-slate-500 text-sm">Loading donations analysis...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white">Political Donations Analysis</h1>
          <p className="text-slate-500 text-sm mt-1">
            Cross-referencing city vendors with federal campaign contributions
          </p>
        </div>
        <div className="card p-8 text-center">
          <p className="text-slate-400 text-sm mb-2">No data available</p>
          <p className="text-slate-600 text-xs">
            The donations analysis API may not be available yet. This feature cross-references
            vendor data with federal campaign finance records (FEC). Please try again later.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Political Donations Analysis</h1>
        <p className="text-slate-500 text-sm mt-1">
          Cross-referencing city vendors with federal campaign contributions
        </p>
      </div>

      {/* Disclaimer */}
      <div className="card p-4 mb-6 border-amber-500/30 bg-amber-500/5">
        <div className="flex gap-3">
          <div className="flex-shrink-0 mt-0.5">
            <svg className="w-5 h-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
          </div>
          <div>
            <p className="text-sm text-amber-200 font-medium mb-1">Data Source Notice</p>
            <p className="text-xs text-slate-400 leading-relaxed">
              This analysis uses federal (FEC) campaign finance data. Illinois state and local campaign
              donations are not yet included. Donation matches are based on name similarity and should
              be verified independently.
            </p>
          </div>
        </div>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
          <div className="card p-4">
            <p className="text-2xl font-bold text-white">
              {formatNumber(summary.total_donations)}
            </p>
            <p className="text-xs text-slate-500">Total Donations Found</p>
          </div>
          <div className="card p-4">
            <p className="text-2xl font-bold text-emerald-400">
              {formatCompactCurrency(summary.total_amount)}
            </p>
            <p className="text-xs text-slate-500">Total Amount Donated</p>
          </div>
          <div className="card p-4">
            <p className="text-2xl font-bold text-blue-400">
              {formatNumber(summary.vendors_with_donations)}
            </p>
            <p className="text-xs text-slate-500">Vendors with Donations</p>
          </div>
          <div className="card p-4">
            <p className="text-sm font-bold text-slate-300">Federal (FEC)</p>
            <p className="text-xs text-slate-500 mt-1">Data Source</p>
            <p className="text-[10px] text-slate-600 mt-0.5">State data coming soon</p>
          </div>
        </div>
      )}

      {/* Top Donor Vendors */}
      {summary && summary.top_donor_vendors.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-white mb-1">Top Donor Vendors</h2>
          <p className="text-xs text-slate-500 mb-4">
            City vendors ranked by total political donations — click to investigate
          </p>

          <div className="space-y-2">
            {summary.top_donor_vendors.map((vendor) => {
              const isExpanded = expandedVendor === vendor.vendor_name;
              const ratio = vendor.total_contracts > 0
                ? vendor.total_donated / vendor.total_contracts
                : 0;

              return (
                <div key={vendor.vendor_name}>
                  <div
                    className={`card p-4 cursor-pointer transition-colors ${
                      isExpanded
                        ? "bg-slate-800/80 border-blue-500/40"
                        : "hover:bg-slate-800/60"
                    }`}
                    onClick={() => handleVendorExpand(vendor.vendor_name)}
                  >
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm font-medium text-white truncate">
                            {vendor.vendor_name}
                          </span>
                          <span className="text-[10px] text-slate-600">
                            {isExpanded ? "Click to collapse" : "Click to investigate"}
                          </span>
                        </div>
                        <div className="flex items-center gap-4 text-xs text-slate-500">
                          <span>
                            Donated: <span className="text-emerald-400 font-medium">{formatCurrency(vendor.total_donated)}</span>
                          </span>
                          <span>
                            {formatNumber(vendor.donation_count)} donation{vendor.donation_count !== 1 ? "s" : ""}
                          </span>
                          <span>
                            Contracts: <span className="text-slate-300">{formatCompactCurrency(vendor.total_contracts)}</span>
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 flex-shrink-0">
                        {vendor.total_contracts > 0 && (
                          <div className="text-right">
                            <p className={`text-sm font-bold ${ratioColor(ratio)}`}>
                              {formatPercent(ratio)}
                            </p>
                            <p className="text-[10px] text-slate-600">Donation/Contract</p>
                          </div>
                        )}
                        <span className="text-slate-600 text-lg">
                          {isExpanded ? "\u25B2" : "\u25BC"}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Vendor detail panel */}
                  {isExpanded && (
                    <div className="card p-5 mt-1 border-l-2 border-blue-500/50 ml-2">
                      {vendorDetailLoading ? (
                        <div className="flex items-center gap-2 py-4">
                          <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                          <span className="text-slate-500 text-sm">Loading vendor donation details...</span>
                        </div>
                      ) : vendorDetail ? (
                        <VendorDetailPanel detail={vendorDetail} />
                      ) : (
                        <p className="text-slate-500 text-sm">
                          No additional details available for this vendor.
                        </p>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Red Flags */}
      {redFlags && redFlags.flags.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-white mb-1">Red Flags</h2>
          <p className="text-xs text-slate-500 mb-4">
            Patterns that may warrant further investigation
          </p>

          <div className="space-y-2">
            {redFlags.flags.map((flag, i) => (
              <div
                key={`${flag.vendor_name}-${flag.flag_type}-${i}`}
                className="card p-4 border-l-2 border-red-500/50"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className="text-sm font-medium text-white">
                        {flag.vendor_name}
                      </span>
                      <span className={`text-[10px] px-2 py-0.5 rounded border font-medium ${flagTypeBadgeColor(flag.flag_type)}`}>
                        {flag.flag_type.replace(/_/g, " ")}
                      </span>
                    </div>
                    <p className="text-sm text-slate-400 mt-1">{flag.description}</p>
                  </div>
                  <div className="text-right flex-shrink-0 space-y-1">
                    <div>
                      <p className="text-xs text-slate-500">Donated</p>
                      <p className="text-sm font-medium text-emerald-400">
                        {formatCurrency(flag.donation_total)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Contracts</p>
                      <p className="text-sm font-medium text-slate-300">
                        {formatCompactCurrency(flag.contract_total)}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top Recipients */}
      {summary && summary.top_recipients.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-white mb-1">Top Recipients</h2>
          <p className="text-xs text-slate-500 mb-4">
            Political committees receiving the most from city vendors
          </p>

          <div className="card overflow-hidden">
            {summary.top_recipients.map((recipient, i) => {
              const maxAmount = summary.top_recipients[0]?.total_received || 1;
              const barWidth = (recipient.total_received / maxAmount) * 100;

              return (
                <div
                  key={recipient.committee}
                  className={`px-4 py-3 ${
                    i < summary.top_recipients.length - 1
                      ? "border-b border-slate-800"
                      : ""
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-sm text-slate-300 font-medium truncate mr-4">
                      {recipient.committee}
                    </span>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      <span className="text-xs text-slate-500">
                        {formatNumber(recipient.donor_count)} donor{recipient.donor_count !== 1 ? "s" : ""}
                      </span>
                      <span className="text-sm font-medium text-emerald-400">
                        {formatCurrency(recipient.total_received)}
                      </span>
                    </div>
                  </div>
                  <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500/60 rounded-full transition-all"
                      style={{ width: `${barWidth}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Empty state */}
      {summary && summary.total_donations === 0 && (
        <div className="card p-8 text-center">
          <p className="text-slate-400 text-sm mb-2">No donation data available</p>
          <p className="text-slate-600 text-xs">
            No matches were found between city vendors and federal campaign finance records.
            This may indicate the data has not been loaded yet, or no matches exist in
            the current dataset.
          </p>
        </div>
      )}
    </div>
  );
}

function VendorDetailPanel({ detail }: { detail: VendorDonationDetail }) {
  const ratio = detail.donation_to_contract_ratio;

  return (
    <div className="space-y-5">
      {/* Key metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-slate-800/50 rounded-lg p-3">
          <p className="text-sm font-bold text-white">{detail.vendor_name}</p>
          <p className="text-[10px] text-slate-500">Vendor</p>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-3">
          <p className="text-sm font-bold text-slate-200">
            {formatCompactCurrency(detail.contract_value)}
          </p>
          <p className="text-[10px] text-slate-500">Total Contract Value</p>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-3">
          <p className="text-sm font-bold text-emerald-400">
            {formatCurrency(detail.total_donated)}
          </p>
          <p className="text-[10px] text-slate-500">
            Total Donated ({formatNumber(detail.donation_count)})
          </p>
        </div>
        <div className={`rounded-lg p-3 border ${ratioBgColor(ratio)}`}>
          <p className="text-sm font-bold">{formatPercent(ratio)}</p>
          <p className="text-[10px] opacity-70">Donation / Contract Ratio</p>
        </div>
      </div>

      {/* Donations list */}
      {detail.donations.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-white mb-2">
            All Donations ({detail.donations.length})
          </h4>
          <div className="max-h-64 overflow-auto rounded border border-slate-700">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-slate-500 border-b border-slate-700 bg-slate-800/50">
                  <th className="text-left px-3 py-2">Date</th>
                  <th className="text-left px-3 py-2">Donor</th>
                  <th className="text-right px-3 py-2">Amount</th>
                  <th className="text-left px-3 py-2">Recipient Committee</th>
                  <th className="text-left px-3 py-2">Match</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {detail.donations.map((d, i) => (
                  <tr key={i} className="hover:bg-slate-800/40">
                    <td className="px-3 py-1.5 text-slate-400 whitespace-nowrap">
                      {formatDate(d.date)}
                    </td>
                    <td className="px-3 py-1.5 text-slate-300">{d.donor_name}</td>
                    <td className="px-3 py-1.5 text-right font-medium text-emerald-400">
                      {formatCurrency(d.amount)}
                    </td>
                    <td className="px-3 py-1.5 text-slate-400 truncate max-w-[200px]">
                      {d.recipient_committee}
                    </td>
                    <td className="px-3 py-1.5">
                      <MatchTypeBadge type={d.match_type} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Recipients breakdown */}
      {detail.recipients.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-white mb-2">
            Recipients Breakdown
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {detail.recipients.map((r) => (
              <div
                key={r.committee}
                className="bg-slate-800/50 rounded-lg p-3 flex items-center justify-between"
              >
                <div className="min-w-0 mr-3">
                  <p className="text-xs text-slate-300 font-medium truncate">
                    {r.committee}
                  </p>
                  <p className="text-[10px] text-slate-500">
                    {formatNumber(r.count)} contribution{r.count !== 1 ? "s" : ""}
                  </p>
                </div>
                <p className="text-sm font-medium text-emerald-400 flex-shrink-0">
                  {formatCurrency(r.total)}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Employee donors */}
      {detail.employees_who_donated.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-white mb-2">
            Employee Donors
          </h4>
          <p className="text-[10px] text-slate-500 mb-2">
            Individuals matched by employer name in FEC records
          </p>
          <div className="space-y-1.5">
            {detail.employees_who_donated.map((emp) => (
              <div
                key={emp.name}
                className="flex items-center justify-between bg-slate-800/50 rounded px-3 py-2"
              >
                <div className="flex items-center gap-2">
                  <MatchTypeBadge type="employee" />
                  <span className="text-xs text-slate-300">{emp.name}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-[10px] text-slate-500">
                    {formatNumber(emp.count)} contribution{emp.count !== 1 ? "s" : ""}
                  </span>
                  <span className="text-xs font-medium text-emerald-400">
                    {formatCurrency(emp.total)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function MatchTypeBadge({ type }: { type: string }) {
  const isCompany =
    type === "company_name" || type === "company" || type === "Company";
  if (isCompany) {
    return (
      <span className="text-[10px] px-1.5 py-0.5 rounded border font-medium bg-blue-500/20 text-blue-400 border-blue-500/30">
        Company
      </span>
    );
  }
  return (
    <span className="text-[10px] px-1.5 py-0.5 rounded border font-medium bg-purple-500/20 text-purple-400 border-purple-500/30">
      Employee
    </span>
  );
}
