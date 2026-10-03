import { ANALYSIS_PRICE_IDR } from "./domain";

/**
 * Public billing configuration for the client.
 *
 * Deliberately contains no secrets: the server key never leaves the server, and
 * the client only needs to know the price, the currency, and whether it is
 * talking to a sandbox gateway.
 */
export interface PublicBillingConfig {
  enabled: boolean;
  sandbox: boolean;
  priceIdr: number;
  currency: "IDR";
  unvalidatedCountries: string[];
}

export const PUBLIC_BILLING_CONFIG: PublicBillingConfig = {
  enabled: Boolean(process.env.MIDTRANS_SERVER_KEY),
  sandbox: process.env.MIDTRANS_SANDBOX !== "false",
  priceIdr: ANALYSIS_PRICE_IDR,
  currency: "IDR",
  unvalidatedCountries: ["ID"],
};