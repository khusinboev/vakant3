/**
 * Admin UI kit v3 — the density scale of `docs/ADMIN_UI_V3_SPEC.md` §3.
 *
 *   import { Button, List, ListRow, Sheet, useHistorySheet } from "../ui";
 *
 * Nothing in `src/pages/Admin` should style a button, a chip, a sheet or a
 * skeleton by hand: 13px body, 11px meta, 32/40px controls, 40/56px rows.
 */
export { default as Button, IconButton } from "./Button";
export type { ButtonProps, ButtonSize, ButtonVariant, IconButtonProps } from "./Button";

export { default as Chip, Badge, StatusChip, StatusDot, statusTone, TONE_CLASS, TONE_DOT } from "./Chip";
export type { BadgeProps, ChipProps, StatusChipProps, StatusDotProps, Tone } from "./Chip";

export { default as ProgressBar } from "./ProgressBar";
export type { ProgressBarProps } from "./ProgressBar";

export { default as StatTile } from "./StatTile";
export type { StatTileProps } from "./StatTile";

export { default as KeyValue } from "./KeyValue";
export type { KeyValueProps, KeyValueRow } from "./KeyValue";

export { default as List, ListRow } from "./List";
export type { ListProps, ListRowProps } from "./List";

export { default as SearchBar } from "./SearchBar";
export type { SearchBarProps } from "./SearchBar";

export { default as FilterChips, FilterSheet, useAdminFilters, filterParamKeys } from "./Filters";
export type {
  AdminFilterState,
  FilterChipsProps,
  FilterDef,
  FilterOptionDef,
  FilterSheetProps,
  FilterValues,
} from "./Filters";

export { default as Accordion } from "./Accordion";
export type { AccordionItem, AccordionProps } from "./Accordion";

export { default as Tabs, SegmentedControl, TabPanel, useUrlTabs } from "./Tabs";
export type { SegmentedControlProps, SegmentedOption, TabDef, TabsProps } from "./Tabs";

export { default as Toolbar } from "./Toolbar";
export type { ToolbarItem, ToolbarProps } from "./Toolbar";

export { default as ActionBar } from "./ActionBar";
export type { ActionBarProps, ActionSpec } from "./ActionBar";

export { default as Skeleton } from "./Skeleton";
export type { SkeletonProps } from "./Skeleton";

export { default as EmptyState } from "./EmptyState";
export type { EmptyStateProps } from "./EmptyState";

export { default as JsonDetails } from "./JsonDetails";
export type { JsonDetailsProps } from "./JsonDetails";

export { default as PeriodSelector, periodDays, PERIOD_LABEL_KEY } from "./PeriodSelector";
export type { PeriodSelectorProps, PeriodValue } from "./PeriodSelector";

export { default as Sheet, SheetFrame } from "./Sheet";
export type { SheetFrameProps, SheetProps, SheetSize } from "./Sheet";

// ── Hooks the kit is built on (re-exported so pages have one import path) ───
export { useHistorySheet, hasOpenSheet, sheetsFromState } from "../hooks/useHistorySheet";
export type { HistorySheet } from "../hooks/useHistorySheet";
export { useAdminBack, adminBackAction } from "../hooks/useAdminBack";
export { useQueryState } from "../hooks/useQueryState";
export type { QueryStateOptions } from "../hooks/useQueryState";
export { useAdminHeader } from "../hooks/useAdminHeader";
export type { AdminHeaderConfig, AdminMenuItem, AdminPrimaryAction } from "../hooks/useAdminHeader";
export { haptic } from "../hooks/haptics";
export type { HapticKind } from "../hooks/haptics";
export { useIsDesktop, useIsDesktopSm, useMediaQuery } from "../hooks/useMediaQuery";
