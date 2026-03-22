import { createContext, useContext, useState, useCallback } from "react";
import type { ReactNode } from "react";

interface DateFilter {
  startDate: string; // YYYY-MM-DD or ""
  endDate: string;
}

interface DateFilterContextType {
  dateFilter: DateFilter;
  setDateFilter: (f: DateFilter) => void;
  clearDateFilter: () => void;
  /** Merge date filter into a params object for API calls */
  applyToParams: (params: Record<string, string>) => Record<string, string>;
  hasFilter: boolean;
}

const DateFilterContext = createContext<DateFilterContextType | null>(null);

export function DateFilterProvider({ children }: { children: ReactNode }) {
  const [dateFilter, setDateFilter] = useState<DateFilter>({
    startDate: "",
    endDate: "",
  });

  const clearDateFilter = useCallback(() => {
    setDateFilter({ startDate: "", endDate: "" });
  }, []);

  const applyToParams = useCallback(
    (params: Record<string, string>) => {
      const result = { ...params };
      if (dateFilter.startDate) result.start_date = dateFilter.startDate;
      if (dateFilter.endDate) result.end_date = dateFilter.endDate;
      return result;
    },
    [dateFilter]
  );

  const hasFilter = dateFilter.startDate !== "" || dateFilter.endDate !== "";

  return (
    <DateFilterContext.Provider
      value={{ dateFilter, setDateFilter, clearDateFilter, applyToParams, hasFilter }}
    >
      {children}
    </DateFilterContext.Provider>
  );
}

export function useDateFilter() {
  const ctx = useContext(DateFilterContext);
  if (!ctx) throw new Error("useDateFilter must be used within DateFilterProvider");
  return ctx;
}
