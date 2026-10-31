import { useLocation, useParams } from "react-router-dom";

import BroadcastDetailPage from "../broadcasts/BroadcastDetail";
import BroadcastList from "../broadcasts/BroadcastList";
import Composer from "../broadcasts/Composer";

/**
 * The three broadcast routes are three real URLs (spec §2), all served by this
 * one registry entry: `/admin/broadcasts` (list), `/admin/broadcasts/new`
 * (composer) and `/admin/broadcasts/:id` (the live job). Each view declares
 * its own header, so back always steps exactly one level.
 */
export default function BroadcastsPage() {
  const { id } = useParams<{ id?: string }>();
  const { pathname } = useLocation();

  if (pathname.endsWith("/new") || id === "new") return <Composer />;

  const numericId = Number(id);
  if (id && Number.isFinite(numericId)) return <BroadcastDetailPage id={numericId} />;

  return <BroadcastList />;
}
