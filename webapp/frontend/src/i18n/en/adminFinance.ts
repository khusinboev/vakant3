import type { AdminFinanceDict } from "../uz/adminFinance";

const adminFinance: Record<keyof AdminFinanceDict, string> = {
  "adminFinance.title": "Finance",

  "adminFinance.period.aria": "Period",
  "adminFinance.period.7d": "7 days",
  "adminFinance.period.30d": "30 days",
  "adminFinance.period.90d": "90 days",
  "adminFinance.period.365d": "365 days",

  "adminFinance.stat.revenue": "Revenue",
  "adminFinance.stat.activations": "Activations",
  "adminFinance.stat.adminCredits": "Admin credits",
  "adminFinance.stat.referralPayouts": "Referral payouts",
  "adminFinance.stat.outstandingBalance": "Outstanding balance",

  "adminFinance.chart.title": "Revenue and activations",
  "adminFinance.chart.revenue": "Revenue",
  "adminFinance.chart.activations": "Activations",
  "adminFinance.chart.empty": "No data for this period.",

  "adminFinance.transactions.title": "Transactions",
  "adminFinance.transactions.export": "Download CSV",
  "adminFinance.transactions.empty": "No transactions found.",
  "adminFinance.transactions.userIdPlaceholder": "User ID",
  "adminFinance.transactions.col.id": "ID",
  "adminFinance.transactions.col.user": "User",
  "adminFinance.transactions.col.kind": "Kind",
  "adminFinance.transactions.col.amount": "Amount",
  "adminFinance.transactions.col.balanceAfter": "Balance",
  "adminFinance.transactions.col.actor": "Actor",
  "adminFinance.transactions.col.note": "Note",
  "adminFinance.transactions.col.date": "Date",

  "adminFinance.filter.kindLabel": "Kind",

  "adminFinance.kind.pro_activation": "Pro activation",
  "adminFinance.kind.referral_reward": "Referral reward",
  "adminFinance.kind.admin_credit": "Admin credit",
  "adminFinance.kind.admin_reset": "Admin reset",
  "adminFinance.kind.adjustment": "Adjustment",

  "adminFinance.referrals.title": "Referrals",
  "adminFinance.referrals.empty": "No referrals found.",
  "adminFinance.referrals.col.inviter": "Inviter",
  "adminFinance.referrals.col.invitedCount": "Invited",
  "adminFinance.referrals.col.paidSum": "Paid sum",
};
export default adminFinance;
