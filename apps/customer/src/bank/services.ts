import { http } from "../api/session";
import { createBankApi } from "./api";

export const bank = createBankApi(http);
