import { useState } from "react";

export function useNow(): number {
  const [now] = useState(Date.now);
  return now;
}
