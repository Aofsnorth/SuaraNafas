"use client";

import dynamic from "next/dynamic";
import {
  Component,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

const LungModel = dynamic(() => import("./LungModel"), { ssr: false });

function LungFallback() {
  return (
    <div className="lung-fallback" role="status">
      <p>
        Visualisasi 3D tidak tersedia pada perangkat ini. Alur tetap sama:
        rekam audio, bentuk representasi spektrum, lalu tampilkan hasil skrining
        atau simulasi antarmuka.
      </p>
    </div>
  );
}

interface SceneErrorBoundaryProps {
  children: ReactNode;
}

interface SceneErrorBoundaryState {
  hasError: boolean;
}

class SceneErrorBoundary extends Component<
  SceneErrorBoundaryProps,
  SceneErrorBoundaryState
> {
  state: SceneErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): SceneErrorBoundaryState {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) return <LungFallback />;
    return this.props.children;
  }
}

export function LungModelWrapper() {
  const rootRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"idle" | "ready" | "unsupported">("idle");

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        observer.disconnect();

        const canvas = document.createElement("canvas");
        const context =
          canvas.getContext("webgl2") ??
          canvas.getContext("webgl") ??
          canvas.getContext("experimental-webgl");
        setStatus(context ? "ready" : "unsupported");
      },
      { rootMargin: "320px" },
    );

    observer.observe(root);
    return () => observer.disconnect();
  }, []);

  let content: ReactNode = (
    <div className="lung-loading" role="status">
      Memuat visualisasi saat bagian ini mendekati layar…
    </div>
  );

  if (status === "unsupported") {
    content = <LungFallback />;
  } else if (status === "ready") {
    content = (
      <SceneErrorBoundary>
        <LungModel />
      </SceneErrorBoundary>
    );
  }

  return (
    <div ref={rootRef} className="lung-model-shell">
      {content}
    </div>
  );
}
