export function SpectrogramView({ matrix }: { matrix: number[][] }) {
  return (
    <div className="spectrogram" role="img" aria-label="Visual spektrogram simulasi">
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
