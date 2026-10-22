import type { AdminFinanceDict } from "../uz/adminFinance";

const adminFinance: Record<keyof AdminFinanceDict, string> = {
  "adminFinance.title": "Finance",

  "adminFinance.tab.summary": "Summary",
  "adminFinance.tab.transactions": "Transactions",
  "adminFinance.tab.referrals": "Referrals",


  "adminFinance.stat.revenue": "Revenue",
  "adminFinance.stat.activations": "Activations",
  "adminFinance.stat.adminCredits": "Admin credits",
  "adminFinance.stat.referralPayouts": "Referral payouts",
  "adminFinance.stat.outstandingBalance": "Outstanding balance",

  "adminFinance.chart.title": "Revenue and activations",
  "adminFinance.chart.revenue": "Revenue",
  "adminFinance.chart.activations": "Activations",
  "adminFinance.chart.empty": "No data for this period.",

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
  "adminFinance.filter.userId": "User ID",
  "adminFinance.filter.dateLabel": "Date range",

  "adminFinance.kind.pro_activation": "Pro activation",
  "adminFinance.kind.referral_reward": "Referral reward",
  "adminFinance.kind.admin_credit": "Admin credit",
  "adminFinance.kind.admin_reset": "Admin reset",
  "adminFinance.kind.adjustment": "Adjustment",

  "adminFinance.referrals.empty": "No referrals found.",
  "adminFinance.referrals.invitedSuffix": "invited",

  "adminFinance.kind.topup": "Click top-up",
  "adminFinance.kind.topup_bonus": "Payment bonus",
  "adminFinance.stat.topups": "Click top-ups",
  "adminFinance.stat.topupBonuses": "Payment bonuses",
  "adminFinance.tab.payments": "Payments",
  "adminFinance.payments.empty": "No payments found.",
  "adminFinance.payments.bonus": "bonus",
  "adminFinance.filter.statusLabel": "Status",
  "adminFinance.filter.methodLabel": "Method",
  "adminFinance.state.created": "Created",
  "adminFinance.state.pending": "Pending",
  "adminFinance.state.paid": "Paid",
  "adminFinance.state.cancelled": "Cancelled",
  "adminFinance.method.page": "Click page",
  "adminFinance.method.card": "Card",
  "adminFinance.method.phone": "Phone",
  "adminFinance.method.app": "Click app",
};
export default adminFinance;
