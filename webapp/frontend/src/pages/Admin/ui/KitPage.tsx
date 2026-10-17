import { useState } from "react";
import { Check, Download, Plus, Trash2 } from "lucide-react";

import { useAdminHeader } from "../hooks/useAdminHeader";
import { useHistorySheet } from "../hooks/useHistorySheet";
import Accordion from "./Accordion";
import ActionBar from "./ActionBar";
import Button, { IconButton } from "./Button";
import { Badge, Chip, StatusChip, StatusDot } from "./Chip";
import EmptyState from "./EmptyState";
import { FilterChips, useAdminFilters, type FilterDef } from "./Filters";
import JsonDetails from "./JsonDetails";
import KeyValue from "./KeyValue";
import { List, ListRow } from "./List";
import PeriodSelector, { type PeriodValue } from "./PeriodSelector";
import ProgressBar from "./ProgressBar";
import SearchBar from "./SearchBar";
import { Sheet } from "./Sheet";
import Skeleton from "./Skeleton";
import StatTile from "./StatTile";
import Tabs, { SegmentedControl, useUrlTabs } from "./Tabs";
import Toolbar from "./Toolbar";

const FILTERS: FilterDef[] = [
  {
    key: "pro",
    labelKey: "admin.nav.finance",
    type: "select",
    options: [
      { value: "1", labelKey: "admin.status.on" },
      { value: "0", labelKey: "admin.status.off" },
    ],
  },
  { key: "banned", labelKey: "admin.status.off", type: "toggle" },
  { key: "created", labelKey: "admin.filter.from", type: "date-range" },
];

function Row({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-1.5">
      <h2 className="text-[11px] font-bold uppercase tracking-wider text-muted">{title}</h2>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </section>
  );
}

/**
 * `/admin/_kit` — dev-only visual smoke test for the v3 kit (spec §5.1).
 * Never registered in a production build (`registry.ts` filters `devOnly`).
 */
export default function KitPage() {
  const [search, setSearch] = useState("");
  const [period, setPeriod] = useState<PeriodValue>("30");
  const [segment, setSegment] = useState("uz");
  const [tab, setTab] = useUrlTabs<"one" | "two" | "three">("kitTab", "one");
  const filters = useAdminFilters(FILTERS, "kit.filters");
  const sheet = useHistorySheet("kit.sheet");

  useAdminHeader({
    title: "UI kit",
    primary: { label: "Primary", onClick: () => sheet.openSheet() },
    menu: [
      { label: "Menu action", onClick: () => undefined },
      { label: "Danger action", onClick: () => undefined, danger: true },
    ],
  });

  return (
    <div className="space-y-3 pb-4">
      <Row title="Button — sm / md">
        <Button size="sm" variant="primary" onClick={() => undefined}>
          Primary sm
        </Button>
        <Button size="md" variant="primary" onClick={() => undefined}>
          Primary md
        </Button>
        <Button size="sm" variant="secondary" icon={Plus} onClick={() => undefined}>
          Secondary
        </Button>
        <Button size="sm" variant="ghost" onClick={() => undefined}>
          Ghost
        </Button>
        <Button size="sm" variant="danger" icon={Trash2} onClick={() => undefined}>
          Danger
        </Button>
        <Button size="sm" variant="primary" loading onClick={() => undefined}>
          Loading
        </Button>
        <Button size="sm" variant="secondary" disabled onClick={() => undefined}>
          Disabled
        </Button>
        <IconButton icon={Download} ariaLabel="Download" onClick={() => undefined} />
        <IconButton icon={Check} ariaLabel="Confirm" size="md" variant="primary" onClick={() => undefined} />
      </Row>

      <Row title="Chip / Badge / Status">
        <Chip label="Neutral" />
        <Chip label="Primary" tone="primary" />
        <Chip label="Removable" tone="primary" removable onRemove={() => undefined} />
        <Badge count={7} />
        <Badge count={120} tone="danger" />
        <StatusChip status="done" />
        <StatusChip status="queued" />
        <StatusChip status="failed" />
        <StatusChip status="cancelled" />
        <StatusDot status="running" label="running" />
      </Row>

      <Row title="ProgressBar">
        <div className="w-full space-y-1.5">
          <ProgressBar value={35} label="35%" />
          <ProgressBar value={80} tone="success" label="80%" />
        </div>
      </Row>

      <section className="space-y-1.5">
        <h2 className="text-[11px] font-bold uppercase tracking-wider text-muted">StatTile 2×2</h2>
        <div className="grid grid-cols-2 gap-1.5">
          <StatTile label="New users" value="1 284" delta={12.4} />
          <StatTile label="Revenue" value="2 400 000" delta={-3.1} hint="today" />
          <StatTile label="Pro" value="312" />
          <StatTile label="Loading" value="" loading />
        </div>
      </section>

      <section className="space-y-1.5">
        <h2 className="text-[11px] font-bold uppercase tracking-wider text-muted">SearchBar + filters</h2>
        <SearchBar value={search} onChange={setSearch} />
        <FilterChips defs={FILTERS} state={filters} />
      </section>

      <section className="space-y-1.5">
        <h2 className="text-[11px] font-bold uppercase tracking-wider text-muted">Tabs / Segmented / Period</h2>
        <Tabs
          tabs={[
            { id: "one", label: "One" },
            { id: "two", label: "Two", badge: 3 },
            { id: "three", label: "Three" },
          ]}
          value={tab}
          onChange={setTab}
        />
        <div className="flex flex-wrap items-center gap-2">
          <SegmentedControl
            options={[
              { value: "uz", label: "UZ" },
              { value: "ru", label: "RU" },
              { value: "en", label: "EN" },
            ]}
            value={segment}
            onChange={setSegment}
            ariaLabel="Language"
          />
          <PeriodSelector value={period} onChange={setPeriod} periods={["7", "30", "90", "365"]} />
        </div>
      </section>

      <section className="space-y-1.5">
        <h2 className="text-[11px] font-bold uppercase tracking-wider text-muted">List</h2>
        <List>
          <ListRow title="Single line row" meta="40px" />
          <ListRow
            leading={<StatusDot status="done" />}
            title="Two line row"
            subtitle="id 12345 · Pro · 40 000"
            trailing={<StatusChip status="sent" />}
            meta="2 min"
            onClick={() => undefined}
          />
          <ListRow title="Link row" subtitle="navigates" to="/admin" />
        </List>
      </section>

      <section className="space-y-1.5">
        <h2 className="text-[11px] font-bold uppercase tracking-wider text-muted">KeyValue</h2>
        <KeyValue
          rows={[
            { label: "Status", value: "running", tone: "success" },
            { label: "Sent", value: "1 204 / 3 000" },
            { label: "Started", value: "12:40" },
          ]}
        />
      </section>

      <section className="space-y-1.5">
        <h2 className="text-[11px] font-bold uppercase tracking-wider text-muted">Accordion</h2>
        <Accordion
          queryKey="kitSection"
          items={[
            { id: "a", title: "First section", summary: "closed summary", content: <p>Body A</p> },
            { id: "b", title: "Second section", content: <p>Body B</p> },
          ]}
        />
      </section>

      <Row title="Toolbar (overflow on mobile)">
        <Toolbar
          name="kit.toolbar"
          max={2}
          items={[
            { id: "a", label: "One", onClick: () => undefined },
            { id: "b", label: "Two", onClick: () => undefined },
            { id: "c", label: "Three", onClick: () => undefined },
            { id: "d", label: "Delete", onClick: () => undefined, danger: true },
          ]}
        />
      </Row>

      <Row title="Sheet">
        <Button size="sm" variant="secondary" onClick={() => sheet.openSheet()}>
          Open sheet
        </Button>
        <Sheet name="kit.sheet" title="History-backed sheet">
          <p className="text-[13px] text-muted">Back / Esc / the backdrop all close this.</p>
        </Sheet>
      </Row>

      <section className="space-y-1.5">
        <h2 className="text-[11px] font-bold uppercase tracking-wider text-muted">Skeleton / Empty / Json</h2>
        <Skeleton lines={3} />
        <Skeleton rows={2} />
        <EmptyState label="Nothing here yet" description="96px compact empty state" />
        <JsonDetails data={{ code: "INTERNAL_ERROR", request_id: "abc123" }} labelKey="admin.toolbar.more" />
      </section>

      <ActionBar
        primary={{ label: "Primary action", onClick: () => undefined }}
        secondary={{ label: "Test", onClick: () => undefined }}
      />
    </div>
  );
}
