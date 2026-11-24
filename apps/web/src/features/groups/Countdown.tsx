import { useEffect, useState } from "react";

import { countdown } from "@/lib/format";

export function Countdown({ target }: { target: string }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const left = countdown(target, now);

  if (left.past) {
    return <p className="text-center text-lg font-extrabold">🎉 Chegou o grande dia!</p>;
  }
  const parts = [
    { value: left.days, label: left.days === 1 ? "dia" : "dias" },
    { value: left.hours, label: "horas" },
    { value: left.minutes, label: "min" },
    { value: left.seconds, label: "seg" },
  ];
  return (
    <div
      aria-label="Contagem regressiva para o evento"
      className="grid grid-cols-4 gap-2 text-center"
    >
      {parts.map((part) => (
        <div key={part.label} className="rounded-2xl bg-(--accent-soft) px-1 py-3">
          <span className="block text-2xl font-black text-(--accent-text) tabular-nums">
            {String(part.value).padStart(2, "0")}
          </span>
          <span className="text-xs font-bold text-(--accent-text)">{part.label}</span>
        </div>
      ))}
    </div>
  );
}
