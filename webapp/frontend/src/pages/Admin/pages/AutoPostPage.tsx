import { useNavigate } from "react-router-dom";

import AutoPostHistory from "../autopost/AutoPostHistory";
import AutoPostSlots from "../autopost/AutoPostSlots";
import AutoPostStatus from "../autopost/AutoPostStatus";
import PostNowSheet from "../autopost/PostNowSheet";
import { useAdminHeader } from "../hooks/useAdminHeader";
import { useHistorySheet } from "../hooks/useHistorySheet";
import { adminPagePath } from "../routing";

const POST_NOW_SHEET = "autopost.postNow";

/**
 * Auto-post control room: read-only settings summary (edit on Settings, one
 * tap from the header menu), today's schedule slots, a manual "post now"
 * sheet with confirmation + job polling, and the full post history
 * (CONTRACT_P12.md §m010).
 */
export default function AutoPostPage() {
  const navigate = useNavigate();
  const postNow = useHistorySheet(POST_NOW_SHEET);

  useAdminHeader({
    primary: { labelKey: "adminAutopost.postNow.button", onClick: () => postNow.openSheet() },
    menu: [
      {
        labelKey: "adminAutopost.status.editLink",
        onClick: () => navigate(adminPagePath("settings")),
      },
    ],
  });

  return (
    <div className="space-y-3">
      <AutoPostStatus />
      <AutoPostSlots />
      <AutoPostHistory />
      <PostNowSheet name={POST_NOW_SHEET} />
    </div>
  );
}
