import { claraSession } from "./store";

export function forgetClara() {
  claraSession.clear();
}
