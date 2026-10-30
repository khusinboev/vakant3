/**
 * Typed client for `/api/payments/*` (webapp/payments/router.py).
 *
 * Nothing here credits money: the server credits a top-up only when Click's
 * Shop API `Complete` arrives; the client just polls the order.
 */
import client from "./client";

export type ClickMethod = "page" | "card" | "phone" | "app";
export type OrderState = "created" | "pending" | "paid" | "cancelled";

export type PaymentOrder = {
  id: string;
  provider: "click";
  purpose: "topup";
  amount: number;
  state: OrderState;
  method: ClickMethod | "paynet" | null;
  bonus_amount: number;
  created_at: number;
  paid_at: number | null;
};

export type PaymentsConfig = {
  enabled: boolean;
  min_amount: number;
  max_amount: number;
  bonus_percent: number;
};

export type PaynetInfo = {
  enabled: boolean;
  payer_id: string | null;
  app_url: string | null;
};

export const paymentKeys = {
  config: ["payments", "config"] as const,
  paynet: ["payments", "paynet"] as const,
  order: (id: string) => ["payments", "order", id] as const,
};

export async function getPaymentsConfig(): Promise<PaymentsConfig> {
  return (await client.get<PaymentsConfig>("/payments/config")).data;
}

export async function getPaynetInfo(): Promise<PaynetInfo> {
  return (await client.get<PaynetInfo>("/payments/paynet/info")).data;
}

export async function createOrder(amount: number, method: ClickMethod) {
  return (
    await client.post<{ order: PaymentOrder; checkout_url: string }>("/payments/orders", { amount, method })
  ).data;
}

export async function getOrder(orderId: string): Promise<PaymentOrder> {
  return (await client.get<{ order: PaymentOrder }>(`/payments/orders/${encodeURIComponent(orderId)}`)).data.order;
}

/** "Karta" step 1. The card number goes once over HTTPS; never stored client-side. */
export async function clickCardStart(orderId: string, cardNumber: string, expireDate: string) {
  return (
    await client.post<{ phone_masked: string }>(
      "/payments/click/card",
      { order_id: orderId, card_number: cardNumber, expire_date: expireDate },
      { timeout: 45_000 },
    )
  ).data;
}

/** "Karta" step 2: SMS code -> payment. `paid` only once the Shop API settled it. */
export async function clickCardConfirm(orderId: string, smsCode: string) {
  return (
    await client.post<{ status: "paid" | "pending" | "cancelled" }>(
      "/payments/click/card/verify",
      { order_id: orderId, sms_code: smsCode },
      { timeout: 60_000 },
    )
  ).data;
}

/** "Telefon raqam": an invoice goes to the Click app of `phone`. */
export async function clickInvoice(orderId: string, phone: string) {
  return (
    await client.post<{ status: "sent" }>(
      "/payments/click/invoice",
      { order_id: orderId, phone },
      { timeout: 45_000 },
    )
  ).data;
}
