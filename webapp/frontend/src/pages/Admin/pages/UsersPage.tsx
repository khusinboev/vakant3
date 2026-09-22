import { useParams } from "react-router-dom";

import UserDetailScreen from "../users/UserDetailScreen";
import UsersListScreen from "../users/UsersListScreen";

/**
 * The Users section (spec §4 / §4b).
 *
 * `registry.ts` points `/admin/users`, `/admin/users/:id` and
 * `/admin/users/:id/action/:action` at this one component; the `:id` parameter
 * is what decides between the list and the detail screen, so back always walks
 * detail -> list -> panel.
 *
 * It also absorbed the old "Quick actions" tab: adding balance, resetting an
 * account and inspecting a resume all happen on the user they belong to, and
 * the "open by id" sheet in the list header replaces the id boxes.
 */
export default function UsersPage() {
  const { id } = useParams();
  return id ? <UserDetailScreen /> : <UsersListScreen />;
}
