import type { AdminFinanceDict } from "../uz/adminFinance";

const adminFinance: Record<keyof AdminFinanceDict, string> = {
  "adminFinance.title": "Финансы",

  "adminFinance.period.aria": "Период",
  "adminFinance.period.7d": "7 дней",
  "adminFinance.period.30d": "30 дней",
  "adminFinance.period.90d": "90 дней",
  "adminFinance.period.365d": "365 дней",

  "adminFinance.stat.revenue": "Доход",
  "adminFinance.stat.activations": "Активации",
  "adminFinance.stat.adminCredits": "Кредиты админа",
  "adminFinance.stat.referralPayouts": "Реферальные выплаты",
  "adminFinance.stat.outstandingBalance": "Остаток баланса",

  "adminFinance.chart.title": "Доход и активации",
  "adminFinance.chart.revenue": "Доход",
  "adminFinance.chart.activations": "Активации",
  "adminFinance.chart.empty": "Нет данных за этот период.",

  "adminFinance.transactions.title": "Транзакции",
  "adminFinance.transactions.export": "Скачать CSV",
  "adminFinance.transactions.empty": "Транзакции не найдены.",
  "adminFinance.transactions.userIdPlaceholder": "ID пользователя",
  "adminFinance.transactions.col.id": "ID",
  "adminFinance.transactions.col.user": "Пользователь",
  "adminFinance.transactions.col.kind": "Тип",
  "adminFinance.transactions.col.amount": "Сумма",
  "adminFinance.transactions.col.balanceAfter": "Баланс",
  "adminFinance.transactions.col.actor": "Кто выполнил",
  "adminFinance.transactions.col.note": "Заметка",
  "adminFinance.transactions.col.date": "Дата",

  "adminFinance.filter.kindLabel": "Тип",

  "adminFinance.kind.pro_activation": "Активация Pro",
  "adminFinance.kind.referral_reward": "Реферальная награда",
  "adminFinance.kind.admin_credit": "Кредит от админа",
  "adminFinance.kind.admin_reset": "Сброс админом",
  "adminFinance.kind.adjustment": "Корректировка",

  "adminFinance.referrals.title": "Рефералы",
  "adminFinance.referrals.empty": "Рефералы не найдены.",
  "adminFinance.referrals.col.inviter": "Пригласивший",
  "adminFinance.referrals.col.invitedCount": "Приглашено",
  "adminFinance.referrals.col.paidSum": "Выплачено",
};
export default adminFinance;
