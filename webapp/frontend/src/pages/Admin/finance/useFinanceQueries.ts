import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { adminKeys, getFinanceReferrals, getFinanceSummary, getFinanceTransactions } from "../../../api/admin";
import type { FinanceReferralItem, FinanceSummary, FinanceTransactionItem, FinanceTransactionsQuery } from "../../../api/adminTypes";
import { useCursorQuery, type CursorQueryResult } from "../hooks/useCursorQuery";

/** `GET /admin/finance/summary?days=` — totals + daily series for the KPI cards and chart. */
export function useFinanceSummary(days: number): UseQueryResult<FinanceSummary> {
  return useQuery<FinanceSummary>({
    queryKey: adminKeys.financeSummary(days),
    queryFn: () => getFinanceSummary(days),
    retry: false,
  });
}

/** `GET /admin/finance/transactions` — cursor-paginated, refetches whenever a filter changes. */
export function useFinanceTransactions(query: FinanceTransactionsQuery): CursorQueryResult<FinanceTransactionItem> {
  return useCursorQuery<FinanceTransactionItem>(
    adminKeys.financeTransactions(query),
    (cursor) => getFinanceTransactions({ ...query, cursor: cursor ?? undefined }),
  );
}

/** `GET /admin/finance/referrals` — cursor-paginated, no filters. */
export function useFinanceReferrals(): CursorQueryResult<FinanceReferralItem> {
  return useCursorQuery<FinanceReferralItem>(
    adminKeys.financeReferrals(),
    (cursor) => getFinanceReferrals({ cursor: cursor ?? undefined }),
  );
}
