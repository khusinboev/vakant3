import { useMemo, useState } from "react";
import { CreditCard, Download, Landmark, TrendingUp, Users, Wallet } from "lucide-react";

import type { TranslationKey } from "../../../i18n";
import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import type {
  FinanceReferralItem,
  FinanceTransactionItem,
  FinanceTransactionsQuery,
  WalletTransactionKind,
} from "../../../api/adminTypes";
import DataTable, { type Column } from "../components/DataTable";
import FilterBar, { type FilterOption } from "../components/FilterBar";
import QueryState from "../components/QueryState";
import StatCard from "../components/StatCard";
import { downloadCsv } from "../finance/csv";
import FinanceChart from "../finance/FinanceChart";
import PeriodSelector, { type FinancePeriod } from "../finance/PeriodSelector";
import { useFinanceReferrals, useFinanceSummary, useFinanceTransactions } from "../finance/useFinanceQueries";

const KIND_LABEL: Record<WalletTransactionKind, TranslationKey> = {
  pro_activation: "adminFinance.kind.pro_activation",
  referral_reward: "adminFinance.kind.referral_reward",
  admin_credit: "adminFinance.kind.admin_credit",
  admin_reset: "adminFinance.kind.admin_reset",
  adjustment: "adminFinance.kind.adjustment",
};

const KIND_OPTIONS: FilterOption[] = (Object.keys(KIND_LABEL) as WalletTransactionKind[]).map((kind) => ({
  value: kind,
  labelKey: KIND_LABEL[kind],
}));

type DateRange = { from: string; to: string };
const EMPTY_RANGE: DateRange = { from: "", to: "" };

/** `YYYY-MM-DD` (local) -> unix seconds at the start/end of that day. */
function dayBoundary(date: string, end: boolean): number | undefined {
  if (!date) return undefined;
  const time = end ? "23:59:59" : "00:00:00";
  const ms = new Date(`${date}T${time}`).getTime();
  return Number.isNaN(ms) ? undefined : Math.floor(ms / 1000);
}

export default function FinancePage() {
  const t = useT();
  const { formatMoney, formatNumber, formatDateTime } = useLocale();

  const [days, setDays] = useState<FinancePeriod>(30);
  const summary = useFinanceSummary(days);

  const [kind, setKind] = useState("");
  const [userIdInput, setUserIdInput] = useState("");
  const [dateRange, setDateRange] = useState<DateRange>(EMPTY_RANGE);

  const transactionsQuery = useMemo<FinanceTransactionsQuery>(() => {
    const query: FinanceTransactionsQuery = {};
    if (kind) query.kind = kind as WalletTransactionKind;
    const trimmed = userIdInput.trim();
    if (trimmed) {
      const userId = Number(trimmed);
      if (Number.isFinite(userId)) query.user_id = userId;
    }
    const from = dayBoundary(dateRange.from, false);
    const to = dayBoundary(dateRange.to, true);
    if (from !== undefined) query.from = from;
    if (to !== undefined) query.to = to;
    return query;
  }, [kind, userIdInput, dateRange]);

  const transactions = useFinanceTransactions(transactionsQuery);
  const referrals = useFinanceReferrals();

  const resetFilters = () => {
    setKind("");
    setUserIdInput("");
    setDateRange(EMPTY_RANGE);
  };
  const filtersActive = Boolean(kind || userIdInput.trim() || dateRange.from || dateRange.to);

  const exportTransactions = () => {
    downloadCsv(
      `finance-transactions-${Date.now()}.csv`,
      [
        t("adminFinance.transactions.col.id"),
        t("adminFinance.transactions.col.user"),
        t("adminFinance.transactions.col.kind"),
        t("adminFinance.transactions.col.amount"),
        t("adminFinance.transactions.col.balanceAfter"),
        t("adminFinance.transactions.col.actor"),
        t("adminFinance.transactions.col.note"),
        t("adminFinance.transactions.col.date"),
      ],
      transactions.items.map((row) => [
        row.id,
        row.user_id,
        t(KIND_LABEL[row.kind]),
        row.amount,
        row.balance_after,
        row.actor_id ?? "",
        row.note ?? "",
        formatDateTime(row.created_at),
      ]),
    );
  };

  const transactionColumns: Column<FinanceTransactionItem>[] = [
    { key: "id", labelKey: "adminFinance.transactions.col.id", hideOnCard: true },
    { key: "user_id", labelKey: "adminFinance.transactions.col.user" },
    {
      key: "kind",
      labelKey: "adminFinance.transactions.col.kind",
      render: (row) => t(KIND_LABEL[row.kind]),
    },
    {
      key: "amount",
      labelKey: "adminFinance.transactions.col.amount",
      align: "right",
      render: (row) => (
        <span className={row.amount < 0 ? "text-danger" : "text-success"}>
          {row.amount > 0 ? "+" : ""}
          {formatMoney(row.amount)}
        </span>
      ),
    },
    {
      key: "balance_after",
      labelKey: "adminFinance.transactions.col.balanceAfter",
      align: "right",
      render: (row) => formatMoney(row.balance_after),
      hideOnCard: true,
    },
    {
      key: "actor_id",
      labelKey: "adminFinance.transactions.col.actor",
      render: (row) => row.actor_id ?? "—",
      hideOnCard: true,
    },
    {
      key: "note",
      labelKey: "adminFinance.transactions.col.note",
      render: (row) => row.note ?? "—",
      className: "max-w-[16rem] truncate",
      hideOnCard: true,
    },
    {
      key: "created_at",
      labelKey: "adminFinance.transactions.col.date",
      render: (row) => formatDateTime(row.created_at),
    },
  ];

  const referralColumns: Column<FinanceReferralItem>[] = [
    {
      key: "inviter",
      labelKey: "adminFinance.referrals.col.inviter",
      render: (row) => (
        <span>
          {row.inviter_name} <span className="text-muted">#{row.inviter_id}</span>
        </span>
      ),
    },
    {
      key: "invited_count",
      labelKey: "adminFinance.referrals.col.invitedCount",
      align: "right",
      render: (row) => formatNumber(row.invited_count),
    },
    {
      key: "paid_sum",
      labelKey: "adminFinance.referrals.col.paidSum",
      align: "right",
      render: (row) => formatMoney(row.paid_sum),
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-display text-lg font-extrabold text-text">{t("adminFinance.title")}</h1>
        <PeriodSelector value={days} onChange={setDays} />
      </div>

      <QueryState query={summary} skeletonClassName="h-40">
        {(data) => (
          <>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              <StatCard
                labelKey="adminFinance.stat.revenue"
                value={formatMoney(data.totals.revenue)}
                icon={Wallet}
              />
              <StatCard
                labelKey="adminFinance.stat.activations"
                value={formatNumber(data.totals.activations)}
                icon={TrendingUp}
              />
              <StatCard
                labelKey="adminFinance.stat.adminCredits"
                value={formatMoney(data.totals.admin_credits)}
                icon={CreditCard}
              />
              <StatCard
                labelKey="adminFinance.stat.referralPayouts"
                value={formatMoney(data.totals.referral_payouts)}
                icon={Users}
              />
              <StatCard
                labelKey="adminFinance.stat.outstandingBalance"
                value={formatMoney(data.totals.balance_outstanding)}
                icon={Landmark}
              />
            </div>

            <FinanceChart series={data.series} />
          </>
        )}
      </QueryState>

      <section className="card space-y-3 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-widest text-muted">
            {t("adminFinance.transactions.title")}
          </h2>
          <button
            type="button"
            onClick={exportTransactions}
            disabled={transactions.items.length === 0}
            className="tap-target inline-flex items-center gap-1.5 rounded-xl border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-text disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download size={13} aria-hidden="true" />
            {t("adminFinance.transactions.export")}
          </button>
        </div>

        <FilterBar onReset={filtersActive ? resetFilters : undefined}>
          <FilterBar.Select
            value={kind}
            onChange={setKind}
            options={KIND_OPTIONS}
            allKey="admin.filter.all"
            labelKey="adminFinance.filter.kindLabel"
            className="w-40"
          />
          <FilterBar.Search
            value={userIdInput}
            onChange={setUserIdInput}
            placeholderKey="adminFinance.transactions.userIdPlaceholder"
            className="max-w-[12rem]"
          />
          <FilterBar.DateRange from={dateRange.from} to={dateRange.to} onChange={setDateRange} />
        </FilterBar>

        <DataTable
          columns={transactionColumns}
          rows={transactions.items}
          getRowId={(row) => row.id}
          loading={transactions.isLoading}
          error={transactions.error}
          onRetry={transactions.refetch}
          onLoadMore={transactions.loadMore}
          hasMore={transactions.hasMore}
          loadingMore={transactions.isFetchingMore}
          total={transactions.total}
          emptyKey="adminFinance.transactions.empty"
          captionKey="adminFinance.transactions.title"
        />
      </section>

      <section className="card space-y-3 p-4">
        <h2 className="text-[11px] font-semibold uppercase tracking-widest text-muted">
          {t("adminFinance.referrals.title")}
        </h2>
        <DataTable
          columns={referralColumns}
          rows={referrals.items}
          getRowId={(row) => row.inviter_id}
          loading={referrals.isLoading}
          error={referrals.error}
          onRetry={referrals.refetch}
          onLoadMore={referrals.loadMore}
          hasMore={referrals.hasMore}
          loadingMore={referrals.isFetchingMore}
          total={referrals.total}
          emptyKey="adminFinance.referrals.empty"
          captionKey="adminFinance.referrals.title"
        />
      </section>
    </div>
  );
}
