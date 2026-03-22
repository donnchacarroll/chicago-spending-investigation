import { riskBgColor, riskLabel } from "../lib/formatters";

interface RiskBadgeProps {
  score: number;
  showScore?: boolean;
}

export default function RiskBadge({ score, showScore = true }: RiskBadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${riskBgColor(
        score
      )}`}
    >
      {riskLabel(score)}
      {showScore && <span className="opacity-75">{score}</span>}
    </span>
  );
}
