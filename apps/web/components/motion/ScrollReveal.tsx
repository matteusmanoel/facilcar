"use client";

import { useEffect, useRef } from "react";
import { cn } from "@/lib/cn";

type Direction = "up" | "left" | "right";

type Props = {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  direction?: Direction;
  once?: boolean;
};

const directionClass: Record<Direction, string> = {
  up: "reveal",
  left: "reveal reveal-left",
  right: "reveal reveal-right",
};

export function ScrollReveal({
  children,
  className,
  delay = 0,
  direction = "up",
  once = true,
}: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (mq.matches) {
      el.classList.add("is-visible");
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setTimeout(() => {
              el.classList.add("is-visible");
            }, delay);
            if (once) observer.unobserve(el);
          } else if (!once) {
            el.classList.remove("is-visible");
          }
        });
      },
      { threshold: 0.12 },
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [delay, once]);

  return (
    <div
      ref={ref}
      className={cn(directionClass[direction], className)}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </div>
  );
}
