import { useEffect, useState } from "react";
import { api } from "@/lib/api";

let demoMode: Promise<boolean> | null = null;

/** True when the API seeded the sample company; demo hints and sample accounts show only then. */
export function useDemoMode() {
  const [demo, setDemo] = useState(false);
  useEffect(() => {
    let active = true;
    demoMode ??= api<{ demo: boolean }>("/api/auth/options")
      .then((options) => options.demo)
      .catch(() => {
        demoMode = null;
        return false;
      });
    demoMode.then((value) => { if (active) setDemo(value); });
    return () => { active = false; };
  }, []);
  return demo;
}
