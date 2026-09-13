"use client";

import { useEffect, useState } from "react";
import { VehicleCard, type VehicleCardVehicle } from "@/features/catalog/ui/VehicleCard";

type Props = {
  vehicles: VehicleCardVehicle[];
};

const MOBILE_SHIFTS = [
  "translate-x-0 rotate-[-0.4deg]",
  "translate-x-5 rotate-[1.1deg]",
  "-translate-x-4 rotate-[-1deg]",
  "translate-x-3 rotate-[0.6deg]",
  "-translate-x-6 rotate-[-0.8deg]",
  "translate-x-2 rotate-[0.3deg]",
];

export function FeaturedVehiclesCarousel({ vehicles }: Props) {
  const [paused, setPaused] = useState(false);
  const [reduceMotion, setReduceMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReduceMotion(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  if (vehicles.length === 0) return null;

  const staticGrid = (
    <div className="grid items-stretch gap-3 sm:gap-4 md:grid-cols-3">
      {vehicles.slice(0, 3).map((v, i) => (
        <VehicleCard key={v.id} vehicle={v} featured headingLevel="h3" priority={i === 0} />
      ))}
    </div>
  );

  if (reduceMotion || vehicles.length === 1) return staticGrid;

  const loop = [...vehicles, ...vehicles];
  const durationSec = Math.max(32, vehicles.length * 8);
  const playState = paused ? "paused" : "running";

  return (
    <div
      className="group"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <style>{`
        @keyframes featured-marquee {
          from { transform: translateX(0); }
          to { transform: translateX(-50%); }
        }
        @keyframes featured-marquee-y {
          from { transform: translateY(0); }
          to { transform: translateY(-50%); }
        }
        .featured-marquee-track {
          animation-name: featured-marquee;
          animation-timing-function: linear;
          animation-iteration-count: infinite;
          will-change: transform;
        }
        .featured-marquee-track-y {
          animation-name: featured-marquee-y;
          animation-timing-function: linear;
          animation-iteration-count: infinite;
          will-change: transform;
        }
      `}</style>
      <div className="hidden overflow-hidden md:block">
        <div
          className="featured-marquee-track flex w-max items-stretch gap-4 pr-4 group-hover:[animation-play-state:paused]"
          style={{ animationDuration: `${durationSec}s`, animationPlayState: playState }}
        >
          {loop.map((v, i) => (
            <div key={`${v.id}-h-${i}`} className="h-auto w-[min(22rem,32vw)] shrink-0">
              <VehicleCard vehicle={v} featured headingLevel="h3" priority={i === 0} />
            </div>
          ))}
        </div>
      </div>

      <div className="relative h-[68rem] overflow-hidden md:hidden">
        <div
          className="pointer-events-none absolute inset-x-0 top-0 z-10 h-10 bg-gradient-to-b from-background to-transparent"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute inset-x-0 bottom-0 z-10 h-10 bg-gradient-to-t from-background to-transparent"
          aria-hidden
        />
        <div
          className="featured-marquee-track-y flex flex-col gap-4 px-1 group-hover:[animation-play-state:paused]"
          style={{ animationDuration: `${Math.max(28, vehicles.length * 6)}s`, animationPlayState: playState }}
        >
          {loop.map((v, i) => (
            <div
              key={`${v.id}-v-${i}`}
              className={`w-[84%] max-w-sm ${MOBILE_SHIFTS[i % MOBILE_SHIFTS.length]} ${
                i % 2 === 0 ? "self-start" : "self-end"
              }`}
            >
              <VehicleCard vehicle={v} featured headingLevel="h3" priority={i < 3} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
