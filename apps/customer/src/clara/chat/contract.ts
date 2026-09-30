import type { EntityState } from "@clara/ui/lib/entity";

import type { MessageKey } from "../../i18n/en";
import type { BarChoice, ChatState, PanelPick, ViewSpec } from "./state";

export interface ClaraChat {
  state: ChatState;
  notice: MessageKey | null;
  send: (text: string) => void;
  select: (id: string) => void;
  confirm: (choice: BarChoice) => void;
  pick: (pick: PanelPick) => void;
  cancelPick: () => void;
  confirmPick: () => void;
  navigate: (spec: ViewSpec, face: EntityState) => void;
  restore: (viewId: string) => void;
  retry: (entryId: string) => void;
  reload: () => void;
  reset: () => void;
}
