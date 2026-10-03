import { useNavigate } from "@tanstack/react-router";
import { useCallback } from "react";

import { claraSession } from "./store";
import type { Topic } from "./topics";

export function useOpenClara() {
  const navigate = useNavigate();
  return useCallback(
    (topic: Topic | null) => {
      if (topic) claraSession.startTopic(topic);
      void navigate({ to: "/chat" });
    },
    [navigate],
  );
}
