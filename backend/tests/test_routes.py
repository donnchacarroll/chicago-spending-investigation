"""Integration tests for all API route endpoints."""

import pytest


class TestOverviewRoutes:
    def test_overview(self, client):
        resp = client.get("/api/overview/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total_spending" in data
        assert "total_payments" in data

    def test_overview_top_vendors_excludes_intergovernmental(self, client):
        resp = client.get("/api/overview/")
        assert resp.status_code == 200
        data = resp.get_json()
        vendor_names = [v["vendor_name"] for v in data["top_vendors"]]
        assert "COOK COUNTY TREASURER" not in vendor_names
        assert "STATE OF ILLINOIS TREASURERS OFFICE" not in vendor_names
        assert "CHICAGO TRANSIT AUTHORITY" not in vendor_names


class TestPaymentRoutes:
    def test_payments_list(self, client):
        resp = client.get("/api/payments/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "payments" in data
        assert "total" in data

    def test_payments_with_search(self, client):
        # The payments list endpoint uses ?vendor= (not ?search=) for vendor filtering
        resp = client.get("/api/payments/?vendor=EXTREME")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "payments" in data


class TestVendorRoutes:
    def test_vendors_list(self, client):
        resp = client.get("/api/vendors/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "vendors" in data
        assert "total" in data

    def test_vendors_list_excludes_intergovernmental(self, client):
        resp = client.get("/api/vendors/")
        assert resp.status_code == 200
        data = resp.get_json()
        vendor_names = [v["vendor_name"] for v in data["vendors"]]
        assert "COOK COUNTY TREASURER" not in vendor_names
        assert "STATE OF ILLINOIS TREASURERS OFFICE" not in vendor_names

    def test_vendor_detail(self, client):
        resp = client.get("/api/vendors/EXTREME_VENDOR_LLC")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "summary" in data


class TestDepartmentRoutes:
    def test_departments_list(self, client):
        resp = client.get("/api/departments/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "departments" in data

    def test_departments_true_cost(self, client):
        resp = client.get("/api/departments/true-cost")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "departments" in data

    def test_department_detail(self, client):
        resp = client.get("/api/departments/POLICE")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "summary" in data


class TestContractRoutes:
    def test_contracts_summary(self, client):
        resp = client.get("/api/contracts/summary")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total_contracts" in data

    def test_contracts_list(self, client):
        resp = client.get("/api/contracts/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "contracts" in data

    def test_repeat_overspenders(self, client):
        resp = client.get("/api/contracts/repeat-overspenders")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "vendors" in data


class TestCategoryRoutes:
    def test_categories(self, client):
        resp = client.get("/api/categories/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "by_category" in data

    def test_direct_vouchers(self, client):
        resp = client.get("/api/categories/direct-vouchers")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "by_subcategory" in data


class TestTrendRoutes:
    def test_timeseries(self, client):
        resp = client.get("/api/trends/timeseries")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "series" in data

    def test_yoy(self, client):
        resp = client.get("/api/trends/yoy")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "items" in data

    def test_patterns(self, client):
        resp = client.get("/api/trends/patterns")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "seasonality" in data


class TestAlertRoutes:
    def test_alerts_list(self, client):
        resp = client.get("/api/alerts/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "alerts" in data

    def test_alerts_summary(self, client):
        resp = client.get("/api/alerts/summary")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "by_flag_type" in data


class TestNetworkRoutes:
    def test_address_clusters(self, client):
        resp = client.get("/api/network/address-clusters")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "clusters" in data

    def test_vendor_aliases(self, client):
        resp = client.get("/api/network/vendor-aliases")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "aliases" in data

    def test_network_summary(self, client):
        resp = client.get("/api/network/summary")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "address_clusters" in data


class TestIntergovernmentalRoutes:
    def test_intergovernmental_summary(self, client):
        resp = client.get("/api/intergovernmental/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total_spending" in data
        assert "payment_count" in data
        assert "top_recipients" in data
        assert data["total_spending"] > 0
        assert data["payment_count"] > 0

    def test_intergovernmental_top_recipients_are_gov_entities(self, client):
        resp = client.get("/api/intergovernmental/")
        assert resp.status_code == 200
        data = resp.get_json()
        recipient_names = [r["vendor_name"] for r in data["top_recipients"]]
        assert "COOK COUNTY TREASURER" in recipient_names

    def test_intergovernmental_detail(self, client):
        resp = client.get("/api/intergovernmental/COOK%20COUNTY%20TREASURER")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total_paid" in data
        assert "payment_count" in data
        assert data["total_paid"] > 0


class TestDonationRoutes:
    def test_donations_summary(self, client):
        resp = client.get("/api/donations/summary")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total_donations" in data or "message" in data

    def test_donations_red_flags(self, client):
        resp = client.get("/api/donations/red-flags")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "flags" in data or "message" in data
