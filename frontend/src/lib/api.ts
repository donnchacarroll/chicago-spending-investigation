const BASE = import.meta.env.DEV ? "http://localhost:5001/api" : "/api";

async function fetchApi<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${BASE}${path}`);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, value);
      }
    }
  }
  const res = await fetch(url.toString());
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

// Types

export interface OverviewData {
  total_spending: number;
  total_payments: number;
  flagged_payments_count: number;
  high_risk_vendors_count: number;
  departments_count: number;
  spending_by_department: Array<{ department_name: string; total_spending: number; payment_count: number }>;
  spending_by_year: Array<{ year: number; total_spending: number; payment_count: number }>;
  top_vendors: Array<{ vendor_name: string; total_paid: number; payment_count: number; risk_score: number }>;
}

export interface PaymentContract {
  contract_number: string;
  description: string;
  contract_type_desc: string;
  procurement_type: string;
  award_amount: number;
  start_date: string;
  end_date: string;
  approval_date: string;
  specification_number: string;
  contract_vendor: string;
  vendor_id: string;
  address_1: string;
  city: string;
  state: string;
  zip: string;
  pdf_url: string;
  total_paid_on_contract: number;
  contract_payment_count: number;
}

export interface Payment {
  voucher_number: string;
  vendor_name: string;
  department_name: string;
  amount: number;
  check_date: string;
  contract_number: string;
  contract_type: string;
  risk_score: number;
  year: number;
  month: number;
  spending_category?: string;
  dv_subcategory?: string;
  flags?: Array<{ flag_type: string; description: string; risk_score: number }>;
  contract?: PaymentContract | null;
  vendor_context?: { total_payments: number; total_paid: number; avg_payment: number };
}

export interface PaymentsResponse {
  payments: Payment[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface Vendor {
  vendor_name: string;
  total_paid: number;
  payment_count: number;
  department_count: number;
  risk_score: number;
}

export interface VendorsResponse {
  vendors: Vendor[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface VendorDetail {
  summary: {
    vendor_name: string;
    total_paid: number;
    payment_count: number;
    avg_payment: number;
    risk_score: number;
    flag_count: number;
    department_count: number;
  };
  payment_history: Array<{ year: number; month: number; total: number; count: number }>;
  departments: Array<{ department_name: string; total_paid: number; payment_count: number }>;
  contracts: Array<{ contract_number: string; award_amount: number }>;
  flags: Array<{ flag_type: string; description: string; risk_score: number; amount: number }>;
}

export interface Department {
  department_name: string;
  total_spending: number;
  payment_count: number;
  vendor_count: number;
  risk_score: number;
}

export interface DepartmentsResponse {
  departments: Department[];
}

export interface DepartmentDetail {
  department_name: string;
  total_spending: number;
  payment_count: number;
  vendor_count: number;
  avg_payment: number;
  top_vendors: Array<{ vendor_name: string; total_paid: number; payment_count: number }>;
  monthly_trend: Array<{ year: number; month: number; total_spending: number; payment_count: number }>;
  flags: Array<{ flag_type: string; count: number }>;
}

export interface Alert {
  voucher_number: string;
  vendor_name: string;
  department_name: string;
  amount: number;
  flag_type: string;
  description: string;
  risk_score: number;
}

export interface AlertsResponse {
  alerts: Alert[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface AlertsSummary {
  by_flag_type: Array<{ flag_type: string; count: number }>;
  total_count: number;
  critical_count: number;
}

export interface AlertDetail {
  alerts: Alert[];
  payment: {
    voucher_number: string;
    vendor_name: string;
    department_name: string;
    amount: number;
    check_date: string;
    contract_number: string;
    contract_type: string;
  };
  group_stats: {
    payment_count: number;
    mean_amount: number;
    std_amount: number;
    min_amount: number;
    max_amount: number;
    median_amount: number;
    p25_amount: number;
    p75_amount: number;
  };
  comparison_payments: Array<{
    voucher_number: string;
    amount: number;
    check_date: string;
    contract_number: string;
  }>;
  explanation: Array<{ title: string; text: string }>;
}

export interface CategorySummary {
  category: string;
  total_spending: number;
  payment_count: number;
  vendor_count: number;
  avg_payment: number;
}

export interface ProcurementSummary {
  procurement_type: string;
  total_spending: number;
  payment_count: number;
  vendor_count: number;
}

export interface ContractTypeSummary {
  contract_type: string;
  category: string;
  total_spending: number;
  payment_count: number;
}

export interface CategoriesData {
  by_category: CategorySummary[];
  by_procurement: ProcurementSummary[];
  by_contract_type: ContractTypeSummary[];
  no_contract_spending: { total: number; count: number };
}

export interface CategoryDetail {
  category: string;
  total_spending: number;
  payment_count: number;
  top_vendors: Array<{ vendor_name: string; total_paid: number; payment_count: number }>;
  top_departments: Array<{ department_name: string; total_spending: number; payment_count: number }>;
  monthly_trend: Array<{ year: number; month: number; total: number; count: number }>;
  largest_payments: Array<{
    vendor_name: string;
    amount: number;
    check_date: string;
    department_name: string;
    purchase_order_description: string;
  }>;
}

export interface DVBreakdown {
  by_subcategory: Array<{
    subcategory: string;
    total_spending: number;
    payment_count: number;
    vendor_count: number;
    avg_payment: number;
  }>;
  top_vendors: Array<{ vendor_name: string; total_paid: number; payment_count: number; avg_payment: number }>;
  largest_payments: Array<{
    vendor_name: string;
    amount: number;
    check_date: string;
    department_name: string;
    subcategory: string;
    voucher_number: string;
  }>;
  individual_stats: {
    payment_count: number;
    total_spending: number;
    avg_payment: number;
    median_payment: number;
  };
}

// API functions

export function getOverview(params?: Record<string, string>) {
  return fetchApi<OverviewData>("/overview", params);
}

export function getPayments(params?: Record<string, string>) {
  return fetchApi<PaymentsResponse>("/payments", params);
}

export function getPaymentDetail(voucherNumber: string) {
  return fetchApi<Payment>(`/payments/${encodeURIComponent(voucherNumber)}`);
}

export function getVendors(params?: Record<string, string>) {
  return fetchApi<VendorsResponse>("/vendors", params);
}

export function getVendorDetail(vendorName: string) {
  return fetchApi<VendorDetail>(`/vendors/${encodeURIComponent(vendorName)}`);
}

export function getDepartments(params?: Record<string, string>) {
  return fetchApi<DepartmentsResponse>("/departments", params);
}

export function getDepartmentDetail(name: string) {
  return fetchApi<DepartmentDetail>(`/departments/${encodeURIComponent(name)}`);
}

export function getAlerts(params?: Record<string, string>) {
  return fetchApi<AlertsResponse>("/alerts", params);
}

export function getAlertsSummary() {
  return fetchApi<AlertsSummary>("/alerts/summary");
}

export function getAlertDetail(voucherNumber: string) {
  return fetchApi<AlertDetail>(`/alerts/detail/${encodeURIComponent(voucherNumber)}`);
}

export function getCategories(params?: Record<string, string>) {
  return fetchApi<CategoriesData>("/categories/", params);
}

export function getCategoryDetail(name: string, params?: Record<string, string>) {
  return fetchApi<CategoryDetail>(`/categories/${encodeURIComponent(name)}`, params);
}

export function getDVBreakdown(params?: Record<string, string>) {
  return fetchApi<DVBreakdown>("/categories/direct-vouchers", params);
}

// Contract types

export interface ContractListItem {
  contract_number: string;
  description: string;
  vendor_name: string;
  department: string;
  award_amount: number;
  total_paid: number;
  overspend_ratio: number;
  payment_count: number;
  start_date: string;
  end_date: string;
  contract_type: string;
  procurement_type: string;
  pdf_url: string;
}

export interface ContractsResponse {
  contracts: ContractListItem[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface ContractDetail {
  contract: ContractListItem & {
    vendor_id: string;
    address: string;
    city: string;
    state: string;
    zip: string;
    approval_date: string;
    specification_number: string;
  };
  payments: Array<{
    voucher_number: string;
    amount: number;
    check_date: string;
    department_name: string;
  }>;
  monthly_spending: Array<{
    year: number;
    month: number;
    amount: number;
    count: number;
  }>;
}

export interface ContractSummary {
  total_contracts: number;
  total_award_value: number;
  total_paid: number;
  overspent_count: number;
  overspent_total_excess: number;
  by_type: Array<{ contract_type: string; count: number; total_award: number }>;
  by_procurement: Array<{ procurement_type: string; count: number; total_award: number }>;
}

// Trends types

export interface TimeseriesDataPoint {
  year: number;
  month: number;
  amount: number;
  count: number;
}

export interface TimeseriesSeries {
  name: string;
  data: TimeseriesDataPoint[];
  total: number;
}

export interface TimeseriesResponse {
  dimension: string;
  series: TimeseriesSeries[];
  monthly_totals: TimeseriesDataPoint[];
}

export interface YoYItem {
  name: string;
  by_year: Record<string, number>;
  total: number;
  yoy_change_pct: number;
}

export interface YoYResponse {
  dimension: string;
  years: number[];
  items: YoYItem[];
}

export interface SeasonalityPoint {
  month: number;
  avg_spending: number;
  label: string;
}

export interface QuarterlyPoint {
  year: number;
  quarter: number;
  amount: number;
  count: number;
}

export interface GrowthDimensionItem {
  name: string;
  latest: number;
  prior: number;
  change_pct: number;
}

export interface GrowthData {
  latest_year: number;
  prior_year: number;
  latest_total: number;
  prior_total: number;
  growth_pct: number;
  by_dimension: GrowthDimensionItem[];
}

export interface SpikeData {
  year: number;
  month: number;
  amount: number;
  avg_for_month: number;
  spike_ratio: number;
  top_vendor: string;
}

export interface PatternsResponse {
  seasonality: SeasonalityPoint[];
  quarterly: QuarterlyPoint[];
  growth: GrowthData;
  spikes: SpikeData[];
}

// Contract API functions

export function getContracts(params?: Record<string, string>) {
  return fetchApi<ContractsResponse>("/contracts/", params);
}

export function getContractDetail(contractNumber: string) {
  return fetchApi<ContractDetail>(`/contracts/${encodeURIComponent(contractNumber)}`);
}

export function getContractsSummary() {
  return fetchApi<ContractSummary>("/contracts/summary");
}

// Trends API functions

export function getTrends(params?: Record<string, string>) {
  return fetchApi<TimeseriesResponse>("/trends/timeseries", params);
}

export function getTrendsYoY(params?: Record<string, string>) {
  return fetchApi<YoYResponse>("/trends/yoy", params);
}

export function getTrendsPatterns(params?: Record<string, string>) {
  return fetchApi<PatternsResponse>("/trends/patterns", params);
}

// Network / Vendor Network Analysis types

export interface NetworkSummary {
  address_clusters: { total: number; with_3plus: number; total_awards: number };
  vendor_aliases: { total_groups: number; total_awards: number };
  sole_source_stats: { total_vendors: number; total_awards: number; repeat_winners: number };
  top_risk_clusters: Array<{
    address: string;
    city: string;
    vendor_count: number;
    total_awards: number;
    risk_flags: string[];
  }>;
}

export interface AddressCluster {
  address: string;
  city: string;
  zip: string;
  vendor_count: number;
  vendors: string[];
  total_awards: number;
  total_paid: number;
  departments: string[];
  risk_flags: string[];
}

export interface AddressClustersResponse {
  clusters: AddressCluster[];
  total_clusters: number;
  total_vendors_in_clusters: number;
  total_awards_in_clusters: number;
}

export interface VendorAlias {
  vendor_id: string;
  names: string[];
  total_awards: number;
  contract_count: number;
  departments: string[];
}

export interface VendorAliasesResponse {
  aliases: VendorAlias[];
  total_alias_groups: number;
}

export interface ClusterVendor {
  vendor_name: string;
  vendor_id: string;
  contracts: Array<{ contract_number: string; award_amount: number; description: string }>;
  total_awards: number;
  total_paid: number;
  departments: string[];
}

export interface ClusterDetail {
  address: string;
  vendors: ClusterVendor[];
  shared_departments: string[];
  risk_assessment: {
    jv_entities: number;
    sole_source_contracts: number;
    single_department_pct: number;
    largest_vendor_pct: number;
  };
}

// Network API functions

export function getNetworkSummary(params?: Record<string, string>) {
  return fetchApi<NetworkSummary>("/network/summary", params);
}

export function getAddressClusters(params?: Record<string, string>) {
  return fetchApi<AddressClustersResponse>("/network/address-clusters", params);
}

export function getVendorAliases(params?: Record<string, string>) {
  return fetchApi<VendorAliasesResponse>("/network/vendor-aliases", params);
}

export function getClusterDetail(address: string, params?: Record<string, string>) {
  return fetchApi<ClusterDetail>(`/network/cluster/${encodeURIComponent(address)}`, params);
}
