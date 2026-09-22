import { lazy, Suspense, useMemo } from "react";
import { Download } from "lucide-react";

import type { TranslationKey } from "../../../i18n";
import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import type {
  FinanceTransactionsQuery,
  WalletTransactionKind,
} from "../../../api/adminTypes";
import ErrorCard from "../components/ErrorCard";
import LoadMore from "../components/LoadMore";
import QueryState from "../components/QueryState";
import { downloadCsv } from "../finance/csv";
import { useFinanceReferrals, useFinanceSummary, useFinanceTransactions } from "../finance/useFinanceQueries";
import {
  Accordion,
  EmptyState,
  FilterChips,
  KeyValue,
  List,
  ListRow,
  PeriodSelector,
  periodDays,
  Skeleton,
  StatTile,
  StatusChip,
  Tabs,
  TabPanel,
  useAdminFilters,
  useAdminHeader,
  useQueryState,
  useUrlTabs,
  type FilterDef,
  type PeriodValue,
  type Tone,
} from "../ui";

const FinanceChart = lazy(() => import("../finance/FinanceChart"));

const KIND_LABEL: Record<WalletTransactionKind, TranslationKey> = {
  pro_activation: "adminFinance.kind.pro_activation",
  referral_reward: "adminFinance.kind.referral_reward",
  admin_credit: "adminFinance.kind.admin_credit",
  admin_reset: "adminFinance.kind.admin_reset",
  adjustment: "adminFinance.kind.adjustment",
};

const KIND_TONE: Record<WalletTransactionKind, Tone> = {
  pro_activation: "success",
  referral_reward: "success",
  admin_credit: "primary",
  admin_reset: "warning",
  adjustment: "neutral",
};

const KIND_OPTIONS = (Object.keys(KIND_LABEL) as WalletTransactionKind[]).map((kind) => ({
  value: kind,
  labelKey: KIND_LABEL[kind],
}));

const FILTERS: FilterDef[] = [
  { key: "kind", labelKey: "adminFinance.filter.kindLabel", type: "select", options: KIND_OPTIONS },
  {
    key: "user_id",
    labelKey: "adminFinance.filter.userId",
    type: "text",
    placeholderKey: "adminFinance.transactions.userIdPlaceholder",
  },
  { key: "date", labelKey: "adminFinance.filter.dateLabel", type: "date-range" },
];

/** `YYYY-MM-DD` (local) -> unix seconds at the start/end of that day. */
function dayBoundary(date: string | undefined, end: boolean): number | undefined {
  if (!date) return undefined;
  const time = end ? "23:59:59" : "00:00:00";
  const ms = new Date(`${date}T${time}`).getTime();
  return Number.isNaN(ms) ? undefined : Math.floor(ms / 1000);
}

export default function FinancePage() {
  const t = useT();
  const { formatMoney, formatNumber, formatDateTime } = useLocale();

  const [tab, setTab] = useUrlTabs<"summary" | "transactions" | "referrals">("tab", "summary");
  const [period, setPeriod] = useQueryState<PeriodValue>("period", "30");
  const summary = useFinanceSummary(periodDays(period));

  const filters = useAdminFilters(FILTERS, "finance.filters");

  const transactionsQuery = useMemo<FinanceTransactionsQuery>(() => {
    const query: FinanceTransactionsQuery = {};
    const kind = filters.values.kind;
    if (kind) query.kind = kind as WalletTransactionKind;
    const userIdRaw = filters.values.user_id?.trim();
    if (userIdRaw) {
      const userId = Number(userIdRaw);
      if (Number.isFinite(userId)) query.user_id = userId;
    }
    const from = dayBoundary(filters.values.date_from, false);
    const to = dayBoundary(filters.values.date_to, true);
    if (from !== undefined) query.from = from;
    if (to !== undefined) query.to = to;
    return query;
  }, [filters.values]);

  const transactions = useFinanceTransactions(transactionsQuery);
  const referrals = useFinanceReferrals();

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

  useAdminHeader({
    titleKey: "adminFinance.title",
    menu:
      tab === "transactions"
        ? [
            {
              labelKey: "adminFinance.transactions.export",
              icon: Download,
              onClick: exportTransactions,
              disabled: transactions.items.length === 0,
            },
          ]
        : undefined,
  });

  return (
    <div className="space-y-3 pb-3">
      <Tabs
        tabs={[
          { id: "summary", labelKey: "adminFinance.tab.summary" },
          { id: "transactions", labelKey: "adminFinance.tab.transactions" },
          { id: "referrals", labelKey: "adminFinance.tab.referrals" },
        ]}
        value={tab}
        onChange={setTab}
      />

      <TabPanel id="summary" active={tab === "summary"}>
        <div className="space-y-3">
          <PeriodSelector value={period} onChange={setPeriod} periods={["7", "30", "90", "365"]} />
          <QueryState query={summary} skeletonClassName="h-40">
            {(data) => (
              <>
                <div className="grid grid-cols-2 gap-1.5">
                  <StatTile labelKey="adminFinance.stat.revenue" value={formatMoney(data.totals.revenue)} />
                  <StatTile
                    labelKey="adminFinance.stat.activations"
                    value={formatNumber(data.totals.activations)}
                  />
                  <StatTile
                    labelKey="adminFinance.stat.adminCredits"
                    value={formatMoney(data.totals.admin_credits)}
                  />
                  <StatTile
                    labelKey="adminFinance.stat.referralPayouts"
                    value={formatMoney(data.totals.referral_payouts)}
                  />
                </div>
                <KeyValue
                  rows={[
                    {
                      labelKey: "adminFinance.stat.outstandingBalance",
                      value: formatMoney(data.totals.balance_outstanding),
                    },
                  ]}
                />
                <Accordion
                  queryKey="financeChart"
                  items={[
                    {
                      id: "chart",
                      titleKey: "adminFinance.chart.title",
                      content: (
                        <Suspense fallback={<Skeleton height="h-40" />}>
                          <FinanceChart series={data.series} />
                        </Suspense>
                      ),
                    },
                  ]}
                />
              </>
            )}
          </QueryState>
        </div>
      </TabPanel>

      <TabPanel id="transactions" active={tab === "transactions"}>
        <div className="space-y-2">
          <FilterChips defs={FILTERS} state={filters} />

          {transactions.isLoading ? (
            <Skeleton rows={5} />
          ) : transactions.error ? (
            <ErrorCard error={transactions.error} onRetry={transactions.refetch} />
          ) : transactions.items.length === 0 ? (
            <EmptyState labelKey="adminFinance.transactions.empty" />
          ) : (
            <List>
              {transactions.items.map((row) => (
                <ListRow
                  key={row.id}
                  title={
                    <span className="inline-flex items-center gap-1.5">
                      <StatusChip status={row.kind} tone={KIND_TONE[row.kind]} label={t(KIND_LABEL[row.kind])} />
                      <span className={`tabular-nums ${row.amount < 0 ? "text-danger" : "text-success"}`}>
                        {row.amount > 0 ? "+" : ""}
                        {formatMoney(row.amount)}
                      </span>
                    </span>
                  }
                  subtitle={`#${row.user_id}`}
                  meta={formatDateTime(row.created_at)}
                />
              ))}
            </List>
          )}

          <LoadMore
            onLoadMore={transactions.loadMore}
            hasMore={transactions.hasMore}
            loading={transactions.isFetchingMore}
            total={transactions.total}
            loaded={transactions.items.length}
          />
        </div>
      </TabPanel>

      <TabPanel id="referrals" active={tab === "referrals"}>
        <div className="space-y-2">
          {referrals.isLoading ? (
            <Skeleton rows={5} />
          ) : referrals.error ? (
            <ErrorCard error={referrals.error} onRetry={referrals.refetch} />
          ) : referrals.items.length === 0 ? (
            <EmptyState labelKey="adminFinance.referrals.empty" />
          ) : (
            <List>
              {referrals.items.map((row) => (
                <ListRow
                  key={row.inviter_id}
                  title={row.inviter_name}
                  subtitle={`#${row.inviter_id}`}
                  trailing={
                    <span className="text-[13px] font-semibold tabular-nums text-text">
                      {formatMoney(row.paid_sum)}
                    </span>
                  }
                  meta={`${formatNumber(row.invited_count)} ${t("adminFinance.referrals.invitedSuffix")}`}
                />
              ))}
            </List>
          )}

          <LoadMore
            onLoadMore={referrals.loadMore}
            hasMore={referrals.hasMore}
            loading={referrals.isFetchingMore}
            total={referrals.total}
            loaded={referrals.items.length}
          />
        </div>
      </TabPanel>
    </div>
  );
}
