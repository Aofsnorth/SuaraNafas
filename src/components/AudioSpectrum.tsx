const bars = [
  12, 28, 18, 40, 22, 34, 16, 44, 20, 38, 14, 30, 24, 42, 18, 36, 20, 32, 26,
  46, 22, 28, 16, 40, 24, 34, 18, 44, 20, 38, 14, 30, 24, 42, 18, 36,
];

const total = bars.length;
const gap = 4;
const viewWidth = 800;
const viewHeight = 128;
const barWidth = viewWidth / total - gap;

export function AudioSpectrum() {
  return (
    <figure
      className="w-full h-32 md:h-48"
      aria-label="Representasi grafis frekuensi suara pernapasan"
    >
      <svg
        viewBox={`0 0 ${viewWidth} ${viewHeight}`}
        preserveAspectRatio="none"
        className="w-full h-full"
      >
        {bars.map((height, index) => {
          const x = index * (viewWidth / total) + gap / 2;
          const y = viewHeight - height;
          const isAccent = index % 8 === 0;

          return (
            <rect
              key={index}
              x={x}
              y={y}
              width={barWidth}
              height={height}
              rx={2}
              fill={isAccent ? "var(--color-accent)" : "var(--color-rule-2)"}
              className="spectrum-bar"
              style={{ animationDelay: `${index * 0.05}s` }}
            />
          );
        })}
      </svg>
      <figcaption className="sr-only">
        Ilustrasi stilisasi spektrum frekuensi suara pernapasan, bukan data
        rekaman nyata.
      </figcaption>
    </figure>
  );
}
