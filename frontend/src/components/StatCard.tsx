import type { ReactNode } from "react";

interface StatCardProps {
  label: string;
  value: string;
  icon: ReactNode;
  sublabel?: string;
  accent?: string;
}

export default function StatCard({
  label,
  value,
  icon,
  sublabel,
  accent = "text-blue-400",
}: StatCardProps) {
  return (
    <div className="card p-5">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">
            {label}
          </p>
          <p className={`text-2xl font-bold mt-1 ${accent}`}>{value}</p>
          {sublabel && (
            <p className="text-xs text-slate-500 mt-1">{sublabel}</p>
          )}
        </div>
        <div className="text-slate-600 ml-3">{icon}</div>
      </div>
    </div>
  );
}
