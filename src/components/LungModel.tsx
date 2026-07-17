"use client";

import { useEffect, useMemo, useRef, useState, Suspense } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import {
  useGLTF,
  OrbitControls,
  Environment,
  Html,
  Center,
} from "@react-three/drei";
import { motion, AnimatePresence } from "framer-motion";
import * as THREE from "three";
import { useReducedMotion } from "@/hooks/useReducedMotion";

interface HotspotData {
  id: string;
  position: [number, number, number];
  label: string;
  description: string;
}

const hotspots: HotspotData[] = [
  {
    id: "bronchi",
    position: [0, 1.05, 0.55],
    label: "Bronkus",
    description:
      "Saluran udara yang menghubungkan trakea ke paru-paru. Pola suara di sini membantu model mengenali anomali.",
  },
  {
    id: "tissue",
    position: [-0.85, 0.15, 0.55],
    label: "Jaringan paru",
    description:
      "Area pertukaran oksigen. Perubahan tekstur suara napas dapat mengindikasikan adanya infeksi.",
  },
  {
    id: "ai",
    position: [0.95, -0.25, 0.55],
    label: "Analisis AI",
    description:
      "Model membandingkan spektrum frekuensi rekaman dengan pola yang terkait dengan TB.",
  },
];

function createNoiseTexture() {
  const size = 256;
  const data = new Uint8Array(size * size);
  for (let i = 0; i < size * size; i += 1) {
    data[i] = Math.floor(Math.random() * 255);
  }
  const texture = new THREE.DataTexture(data, size, size, THREE.RedFormat);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.needsUpdate = true;
  return texture;
}

function resolveCssThreeColor(token: string, fallback: string) {
  if (typeof document === "undefined") return new THREE.Color(fallback);

  const probe = document.createElement("span");
  probe.style.color = `var(${token})`;
  probe.style.position = "absolute";
  probe.style.visibility = "hidden";
  document.body.appendChild(probe);
  const resolved = getComputedStyle(probe).color;
  probe.remove();

  const canvas = document.createElement("canvas");
  canvas.width = 1;
  canvas.height = 1;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context || !resolved) return new THREE.Color(fallback);

  context.fillStyle = resolved;
  context.fillRect(0, 0, 1, 1);
  const [red, green, blue] = context.getImageData(0, 0, 1, 1).data;
  return new THREE.Color(red / 255, green / 255, blue / 255);
}

function LungMesh() {
  const { scene } = useGLTF("/models/lung.glb");
  const shouldReduce = useReducedMotion();
  const materialRef = useRef<THREE.MeshPhysicalMaterial | null>(null);

  const noise = useMemo(() => createNoiseTexture(), []);
  const material = useMemo(
    () =>
      new THREE.MeshPhysicalMaterial({
        color: resolveCssThreeColor("--color-accent", "#c6ccd6"),
        metalness: 0.02,
        roughness: 0.42,
        roughnessMap: noise,
        bumpMap: noise,
        bumpScale: 0.01,
        transmission: 0.78,
        thickness: 1.4,
        ior: 1.38,
        clearcoat: 0.48,
        clearcoatRoughness: 0.28,
        attenuationColor: resolveCssThreeColor("--color-paper-3", "#10243a"),
        attenuationDistance: 1.1,
        emissive: resolveCssThreeColor("--color-accent-2", "#9aa0ab"),
        emissiveIntensity: 0.08,
        side: THREE.DoubleSide,
      }),
    [noise],
  );

  const clonedScene = useMemo(() => {
    const clone = scene.clone();
    clone.traverse((child) => {
      const mesh = child as THREE.Mesh;
      if (mesh.isMesh) {
        mesh.material = material;
      }
    });
    return clone;
  }, [material, scene]);

  useEffect(() => {
    materialRef.current = material;
    return () => {
      material.dispose();
      noise.dispose();
    };
  }, [material, noise]);

  useFrame(({ clock }) => {
    const mat = materialRef.current;
    if (shouldReduce || !mat) return;
    mat.emissiveIntensity = 0.08 + Math.sin(clock.elapsedTime * 1.4) * 0.04;
  });

  return <primitive object={clonedScene} scale={1.15} />;
}

interface HotspotProps {
  data: HotspotData;
  isActive: boolean;
  onClick: () => void;
}

function Hotspot({ data, isActive, onClick }: HotspotProps) {
  return (
    <Html position={data.position} center distanceFactor={8}>
      <div className="relative">
        <button
          type="button"
          onClick={onClick}
          className="flex items-center gap-2 px-3 py-2 rounded-sm border border-control-border bg-paper/85 backdrop-blur-md text-ink hover:border-accent hover:text-accent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span className="w-2 h-2 rounded-full bg-accent" />
          <span className="text-xs font-medium whitespace-nowrap">
            {data.label}
          </span>
        </button>

        <AnimatePresence>
          {isActive && (
            <motion.div
              className="absolute top-full left-1/2 -translate-x-1/2 mt-2 w-56 p-3 rounded-sm border border-rule bg-paper shadow-lg"
              initial={{ opacity: 0, y: -5 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -5 }}
              transition={{ duration: 0.2 }}
            >
              <p className="text-xs text-ink-2 leading-relaxed">
                {data.description}
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </Html>
  );
}

interface HotspotsProps {
  activeId: string | null;
  setActiveId: (id: string | null) => void;
}

function Hotspots({ activeId, setActiveId }: HotspotsProps) {
  return (
    <>
      {hotspots.map((hotspot) => (
        <Hotspot
          key={hotspot.id}
          data={hotspot}
          isActive={activeId === hotspot.id}
          onClick={() =>
            setActiveId(activeId === hotspot.id ? null : hotspot.id)
          }
        />
      ))}
    </>
  );
}

function Loader() {
  return (
    <Html center>
      <span className="text-xs text-ink-2">Memuat model paru-paru…</span>
    </Html>
  );
}

function LungScene() {
  const [activeId, setActiveId] = useState<string | null>(null);
  const shouldReduce = useReducedMotion();

  return (
    <Canvas
      camera={{ position: [0, 0, 4.2], fov: 35 }}
      gl={{ antialias: true, alpha: true }}
      style={{ width: "100%", height: "100%" }}
      onPointerMissed={() => setActiveId(null)}
    >
      <ambientLight intensity={0.35} />
      <directionalLight position={[5, 5, 5]} intensity={1.1} color="#eaf4ff" />
      <directionalLight position={[-5, -2, -5]} intensity={0.4} color="#aeb4c0" />

      <Suspense fallback={<Loader />}>
        <Environment preset="city" />
        <Center>
          <LungMesh />
          <Hotspots activeId={activeId} setActiveId={setActiveId} />
        </Center>
        <OrbitControls
          enablePan={false}
          enableZoom={false}
          enableRotate
          autoRotate={!shouldReduce}
          autoRotateSpeed={0.5}
          minDistance={2.5}
          maxDistance={8}
          dampingFactor={0.05}
        />
      </Suspense>
    </Canvas>
  );
}

export default function LungModel() {
  return (
    <div
      role="img"
      aria-label="Model 3D paru-paru interaktif dengan titik analisis AI"
      className="w-full h-full"
    >
      <LungScene />
    </div>
  );
}
