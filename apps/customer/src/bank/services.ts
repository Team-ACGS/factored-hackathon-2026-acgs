import { clock, http } from "../api/session";
import { createBankApi } from "./api";
import { createBankQueries } from "./queries";

export const bank = createBankApi(http);

export const bankQueries = createBankQueries(bank, clock);
