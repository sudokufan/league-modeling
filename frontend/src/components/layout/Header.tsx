interface HeaderProps {
  leagueName: string;
  displayName?: string;
  weeksCompleted: number;
  totalWeeks: number;
  bestOfN: number;
  playoffSpots: number;
  isCompleted: boolean;
}

export default function Header({
  leagueName,
  displayName,
  weeksCompleted,
  totalWeeks,
  bestOfN,
  playoffSpots,
  isCompleted,
}: HeaderProps) {
  const playoffText = isCompleted
    ? playoffSpots > 0
      ? `Top ${playoffSpots} qualified`
      : "No playoffs"
    : playoffSpots > 0
      ? `Top ${playoffSpots} qualify`
      : "No playoffs";

  const subtitle = `Week ${weeksCompleted}/${totalWeeks} · Best ${bestOfN} of ${totalWeeks} · ${playoffText}`;

  return (
    <div className="text-center pb-0 mb-4">
      <div className="mb-1">
        <h1 className="text-[1.8em] text-[#e94560] tracking-wide mb-0.5 inline">
          {leagueName}
        </h1>
        {isCompleted && (
          <span className="inline-block bg-[#2ecc71] text-[#1a1a2e] text-[0.4em] px-3 py-1 rounded font-bold tracking-widest align-middle ml-2.5">
            COMPLETED
          </span>
        )}
      </div>
      {displayName && (
        <div className="text-[1em] text-[#666] italic mb-1">{displayName}</div>
      )}
      <div className="text-[#888] text-[0.85em]">{subtitle}</div>
    </div>
  );
}
