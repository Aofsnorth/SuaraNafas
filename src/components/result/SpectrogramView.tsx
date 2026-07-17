interface SpectrogramViewProps {
  matrix: number[][];
  source?: "audio" | "backend";
}

export function SpectrogramView({ matrix, source }: SpectrogramViewProps) {
  return (
    <div
      className="spectrogram"
      role="img"
      aria-label={
        source === "audio"
          ? "Spektrogram yang dihitung dari audio pengguna"
          : "Spektrogram keluaran backend"
      }
    >
      {matrix.map((row, rowIndex) => (
        <div className="spectrogram__row" key={`row-${rowIndex}`}>
          {row.map((value, colIndex) => (
            <span
              className="spectrogram__cell"
              key={`cell-${rowIndex}-${colIndex}`}
              style={{ opacity: 0.14 + value * 0.86 }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}
