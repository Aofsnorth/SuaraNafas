import { AnalysisScore } from "@/lib/types";

export function ScoreBars({ scores }: { scores: AnalysisScore[] }) {
  return (
    <div className="score-bars">
      {scores.map((score) => {
        const percentage = Math.round(score.value * 100);
        return (
          <div className="score-bar" key={score.label}>
            <div className="score-bar__head">
              <span>{score.label}</span>
              <span>{percentage}%</span>
            </div>
            <div className="score-bar__track">
              <div className="score-bar__fill" style={{ width: `${percentage}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
