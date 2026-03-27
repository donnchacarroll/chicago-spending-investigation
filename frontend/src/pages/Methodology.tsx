export default function Methodology() {
  return (
    <div className="max-w-4xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Data Notes & Methodology</h1>
        <p className="text-slate-500 text-sm mt-1">
          Caveats, approximations, and assumptions in this analysis
        </p>
      </div>

      <div className="space-y-8">
        {/* Data Scope */}
        <Section title="Data Scope">
          <DataPoint type="hard">
            <strong>Payment data covers 2023 to present</strong> (currently through early 2026).
            Pre-2023 data exists in the source CSV but is excluded because earlier records are annual
            aggregates rather than individual payments, making them incomparable.
          </DataPoint>
          <DataPoint type="hard">
            <strong>Payment data comes from the City of Chicago Voucher Payments dataset.</strong> This
            covers vendor payments processed through the city's voucher system. It does not include
            payroll disbursements, capital expenditures processed through other systems, or
            federal/state pass-through funds that don't flow through city accounts.
          </DataPoint>
          <DataPoint type="unknown">
            <strong>We don't know what percentage of total city spending flows through the voucher system.</strong> There
            may be significant spending categories (inter-governmental transfers, bond payments, capital
            projects) that are processed through separate systems and are invisible to this analysis.
          </DataPoint>
        </Section>

        {/* Department Attribution */}
        <Section title="Department Attribution">
          <DataPoint type="hard">
            <strong>Only ~38% of payments are directly tagged to a department.</strong> The remainder
            are "Direct Voucher" payments with no department field. These are typically city-wide
            costs (pensions, insurance, debt service) or payments processed centrally.
          </DataPoint>
          <DataPoint type="estimate">
            <strong>Pension fund payments are manually mapped to departments.</strong> We hardcode that
            "POLICEMENS A & B FUND" and "CHICAGO PATROLMEN'S FCU" map to CPD, and "FIREMENS ANNUITY
            BENEFIT FUND" and "CHICAGO FIREMANS ASSN CREDIT" map to CFD. Other pension funds
            (Municipal Employees, Laborers) serve multiple departments and are allocated proportionally.
            This mapping may miss pension vehicles that have changed names or been restructured.
          </DataPoint>
          <DataPoint type="estimate">
            <strong>Single-department vendors are attributed based on contract history.</strong> If 90%+
            of a vendor's total contract value goes to one department, all their untagged payments are
            attributed to that department. This threshold is arbitrary and the attribution may be wrong
            for vendors whose department mix has changed over time.
          </DataPoint>
          <DataPoint type="estimate">
            <strong>Shared costs are allocated proportionally by headcount.</strong> Seven shared-cost
            vendors (Municipal Employee Pension Fund, Amalgamated Bank, Nationwide Retirement, MEABF,
            Laborers & Retirement Board, Blue Cross Blue Shield, USI Insurance) have their untagged
            payments split across all departments based on each department's share of total budgeted
            positions. This assumes costs scale linearly with headcount, which is unlikely to be exactly
            true — a department with more senior employees may have higher per-capita pension costs.
          </DataPoint>
          <DataPoint type="unknown">
            <strong>The shared-cost vendor list is manually curated.</strong> There may be other vendors
            whose payments should be treated as shared costs but are instead sitting in "Other Direct
            Voucher" uncategorized. We have no systematic way to identify all shared-cost vendors.
          </DataPoint>
        </Section>

        {/* Salary & Headcount */}
        <Section title="Salary & Headcount Data">
          <DataPoint type="hard">
            <strong>2023–2025 salary data comes from the Chicago Budget Ordinance.</strong> These are
            budgeted positions and pay rates — what the city authorized, not necessarily what was
            actually spent on payroll. Vacancies, overtime, and mid-year hires/separations are not
            reflected.
          </DataPoint>
          <DataPoint type="estimate">
            <strong>2026 salary data uses the current employee snapshot.</strong> The city publishes a
            "Current Employee Names, Salaries, and Position Titles" dataset that reflects a
            point-in-time view. This is actual current employees (not budgeted), so it tends to be
            lower than the budget ordinance figures for the same department.
          </DataPoint>
          <DataPoint type="estimate">
            <strong>Employee counts for hourly workers are approximated.</strong> The budget ordinance
            records hourly positions with total budgeted hours rather than headcount. We count each
            hourly position line as one employee, which may overcount (one line could represent
            multiple part-time workers) or undercount (one line could be one person working many hours).
          </DataPoint>
          <DataPoint type="unknown">
            <strong>Department names differ across datasets.</strong> The budget ordinance uses names
            like "Chicago Police Department" while payments use "CHICAGO POLICE DEPARTMENT" and
            abbreviations like "DEPT OF FINANCE". We normalize to uppercase and maintain a manual
            mapping table, but some departments may fail to match — resulting in salary data appearing
            as a separate row from payment data for the same department.
          </DataPoint>
          <DataPoint type="hard">
            <strong>Salary data does not include benefits, overtime, or employer contributions.</strong> The
            budget ordinance records base pay rates. Actual compensation costs are typically 30–50%
            higher when including health insurance, pension contributions, overtime, and other benefits.
            Some of these costs appear in the payment data (e.g., Blue Cross payments, pension fund
            contributions) but are allocated as estimated shared costs, not tied to specific employees.
          </DataPoint>
        </Section>

        {/* Contract Data */}
        <Section title="Contract Data">
          <DataPoint type="hard">
            <strong>Contract award amounts represent maximum authorized spending, not actual spending.</strong> A
            $10M contract award means the city authorized up to $10M, but actual payments may be much
            less. Contract awards are shown for reference in the True Cost view but are not added into
            the total true cost calculation.
          </DataPoint>
          <DataPoint type="hard">
            <strong>Contract awards are not year-filtered.</strong> They represent the full authorized
            amount regardless of when payments occur. A multi-year contract appears at its full value
            even when viewing a single year.
          </DataPoint>
          <DataPoint type="estimate">
            <strong>Contract-to-payment matching uses contract numbers.</strong> Not all payments
            reference a contract number, and some contract numbers in the payments data may not match
            the contracts database due to formatting differences or data entry inconsistencies.
          </DataPoint>
        </Section>

        {/* Spending Categories */}
        <Section title="Spending Categories">
          <DataPoint type="estimate">
            <strong>Contract-based payments are categorized using the contract type description.</strong> This
            mapping groups ~50 contract type codes into broader categories (Construction, Professional
            Services, Technology, etc.). The mapping is manually maintained and some contract types may
            be miscategorized.
          </DataPoint>
          <DataPoint type="estimate">
            <strong>Direct Voucher payments are categorized by vendor name pattern matching.</strong> We
            use keyword-based heuristics to classify DV payments into subcategories (Pensions, Debt
            Service, Legal Settlements, etc.). This is inherently imprecise — a vendor named "ABC
            Services" could be anything. Approximately 70% of DV payments by count fall into "Other
            Direct Voucher" because they can't be reliably classified.
          </DataPoint>
        </Section>

        {/* Risk Scoring */}
        <Section title="Risk Scoring & Alerts">
          <DataPoint type="estimate">
            <strong>Risk scores are statistical indicators, not fraud detection.</strong> The scoring
            system flags statistical anomalies: outlier amounts (z-score &gt; 3), potential duplicates
            (same vendor/amount within 3 days), potential payment splitting (multiple payments near
            threshold amounts within 7 days), contract overspending, and vendor concentration. These
            patterns have legitimate explanations in most cases.
          </DataPoint>
          <DataPoint type="estimate">
            <strong>Duplicate detection uses simple heuristics.</strong> Two payments to the same vendor
            for the same amount within 3 days are flagged as potential duplicates. This catches some
            real duplicates but also flags legitimate recurring payments (e.g., monthly rent).
          </DataPoint>
          <DataPoint type="unknown">
            <strong>We cannot determine the false positive rate of any alert type.</strong> Without
            ground truth data on actual fraud, waste, or errors, we cannot calculate precision or
            recall for our detection methods.
          </DataPoint>
        </Section>

        {/* True Cost View */}
        <Section title="True Cost Calculations">
          <DataPoint type="hard">
            <strong>True Cost = Confirmed Payments + Attributed + Estimated.</strong> Salary and
            contract awards are displayed alongside but are not included in the total. This means the
            "true cost" metric is really "total payment-based costs attributed to the department,"
            not a comprehensive department budget.
          </DataPoint>
          <DataPoint type="estimate">
            <strong>The "estimated" tier is the least reliable.</strong> For large departments like CPD,
            estimated costs (proportional allocation of shared vendors) can represent 40–60% of the
            total true cost. The actual allocation of shared costs may differ significantly from a
            simple headcount ratio.
          </DataPoint>
          <DataPoint type="unknown">
            <strong>"All Years" view sums across 2023–present.</strong> For departments, the employee
            count and salary shown in the "All Years" view uses the latest available year's data (2026
            snapshot). The payment-based costs are summed across all years. This means a department
            that was reorganized or renamed mid-period may show fragmented data.
          </DataPoint>
        </Section>

        {/* Political Donations */}
        <Section title="Political Donations">
          <DataPoint type="estimate">
            <strong>Donation matching uses fuzzy name matching.</strong> Vendor names are matched against
            FEC donor records by name and employer. This can produce false positives (common names) and
            false negatives (donors who use different name variants). A donation match does not imply
            any wrongdoing.
          </DataPoint>
          <DataPoint type="hard">
            <strong>Only the top 30 vendors by payment volume are checked.</strong> Smaller vendors
            may also have political donation activity that is not captured.
          </DataPoint>
        </Section>

        {/* Separator */}
        <div className="border-t border-slate-700/50 pt-8">
          <h2 className="text-xl font-bold text-white mb-6">
            Recommendations for Improved Data Transparency
          </h2>
          <p className="text-sm text-slate-400 mb-6">
            The following recommendations address data gaps and integrity issues that limit the
            public's ability to understand how city funds are spent.
          </p>

          <div className="space-y-6">
            <Recommendation
              priority="critical"
              title="Tag all payments with a department"
            >
              The single biggest data gap is that most Direct Voucher payments have no department
              attribution. The city should require a department code on every payment voucher. This
              would eliminate the need for the attribution and estimation tiers entirely, replacing
              guesswork with actual data. Currently, over 60% of payments by dollar value cannot be
              directly tied to a department.
            </Recommendation>

            <Recommendation
              priority="critical"
              title="Publish actual payroll expenditure data"
            >
              The city publishes budgeted positions (Budget Ordinance) and current employee snapshots,
              but neither reflects actual payroll spending. Publishing annual payroll expenditures by
              department — including overtime, benefits, and employer pension contributions — would
              allow accurate department cost analysis without estimating from headcount ratios.
            </Recommendation>

            <Recommendation
              priority="high"
              title="Publish a unified historical salary dataset"
            >
              Salary data is currently split across separate Budget Ordinance datasets per year (each
              with a different API endpoint ID) and a single current-employee snapshot. A unified
              dataset with a year column — or at minimum, a catalog page listing all years and their
              endpoint IDs — would make historical analysis significantly easier.
            </Recommendation>

            <Recommendation
              priority="high"
              title="Link payments to contracts consistently"
            >
              Many payments reference contract numbers that don't match the contracts database, or have
              no contract reference at all. A foreign key relationship between payments and contracts,
              enforced at the data entry level, would enable reliable tracking of spending against
              contract authorizations.
            </Recommendation>

            <Recommendation
              priority="high"
              title="Standardize department names across datasets"
            >
              Department names vary across the payments, contracts, salary, and budget datasets —
              using abbreviations, different capitalization, and occasionally different names entirely
              for the same department. A canonical department ID used consistently across all published
              datasets would eliminate matching errors.
            </Recommendation>

            <Recommendation
              priority="medium"
              title="Publish shared cost allocation methodology"
            >
              The city internally allocates shared costs (pension contributions, insurance, debt service)
              to departments for budgeting purposes. Publishing these allocations would replace our
              headcount-based estimates with the city's own methodology, which presumably accounts for
              factors like salary levels, age demographics, and service-specific insurance rates.
            </Recommendation>

            <Recommendation
              priority="medium"
              title="Include payment purpose or description fields"
            >
              Payments include a vendor name and amount but no description of what was purchased or why.
              Even a brief purpose code or description field would enable much more meaningful
              categorization than the current approach of inferring purpose from vendor names and
              contract types.
            </Recommendation>

            <Recommendation
              priority="medium"
              title="Provide full historical payment detail"
            >
              Pre-2022 payment data in the published dataset appears as annual aggregates rather than
              individual transactions. Publishing the full transaction detail for historical years
              would enable trend analysis and anomaly detection across a longer time horizon.
            </Recommendation>

            <Recommendation
              priority="low"
              title="Publish vendor master data"
            >
              A vendor registry with unique IDs, legal names, DBAs, and parent company relationships
              would enable more accurate vendor analysis. Currently, the same entity may appear under
              multiple name variants, and we cannot reliably identify related vendors.
            </Recommendation>
          </div>
        </div>

        {/* Legend */}
        <div className="card p-4 border border-slate-700/50 mt-8">
          <h3 className="text-sm font-semibold text-white mb-3">Legend</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div className="flex items-start gap-2">
              <span className="mt-0.5 w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0" />
              <div>
                <span className="text-emerald-400 font-medium">Hard data</span>
                <span className="text-slate-500"> — directly from published city datasets, no transformation</span>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <span className="mt-0.5 w-2 h-2 rounded-full bg-amber-500 flex-shrink-0" />
              <div>
                <span className="text-amber-400 font-medium">Estimate</span>
                <span className="text-slate-500"> — derived through heuristics, mappings, or proportional allocation</span>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <span className="mt-0.5 w-2 h-2 rounded-full bg-red-400 flex-shrink-0" />
              <div>
                <span className="text-red-400 font-medium">Unknown</span>
                <span className="text-slate-500"> — data gap or assumption that cannot be validated</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="text-lg font-semibold text-white mb-4">{title}</h2>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function DataPoint({
  type,
  children,
}: {
  type: "hard" | "estimate" | "unknown";
  children: React.ReactNode;
}) {
  const colors = {
    hard: "border-emerald-500/30 bg-emerald-500/5",
    estimate: "border-amber-500/30 bg-amber-500/5",
    unknown: "border-red-400/30 bg-red-400/5",
  };
  const dots = {
    hard: "bg-emerald-500",
    estimate: "bg-amber-500",
    unknown: "bg-red-400",
  };
  const labels = {
    hard: "Hard data",
    estimate: "Estimate",
    unknown: "Unknown",
  };

  return (
    <div className={`card p-4 border ${colors[type]}`}>
      <div className="flex items-start gap-3">
        <div className="flex items-center gap-1.5 flex-shrink-0 mt-0.5">
          <span className={`w-2 h-2 rounded-full ${dots[type]}`} />
          <span className={`text-[10px] font-medium uppercase tracking-wider ${
            type === "hard" ? "text-emerald-400" : type === "estimate" ? "text-amber-400" : "text-red-400"
          }`}>
            {labels[type]}
          </span>
        </div>
        <p className="text-sm text-slate-300 leading-relaxed">{children}</p>
      </div>
    </div>
  );
}

function Recommendation({
  priority,
  title,
  children,
}: {
  priority: "critical" | "high" | "medium" | "low";
  title: string;
  children: React.ReactNode;
}) {
  const colors = {
    critical: "border-red-500/30 bg-red-500/5",
    high: "border-amber-500/30 bg-amber-500/5",
    medium: "border-blue-500/30 bg-blue-500/5",
    low: "border-slate-500/30 bg-slate-500/5",
  };
  const badges = {
    critical: "bg-red-500/20 text-red-400 border-red-500/30",
    high: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    medium: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    low: "bg-slate-500/20 text-slate-400 border-slate-500/30",
  };

  return (
    <div className={`card p-4 border ${colors[priority]}`}>
      <div className="flex items-center gap-2 mb-2">
        <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold border ${badges[priority]}`}>
          {priority.toUpperCase()}
        </span>
        <h3 className="text-sm font-semibold text-white">{title}</h3>
      </div>
      <p className="text-sm text-slate-400 leading-relaxed">{children}</p>
    </div>
  );
}
