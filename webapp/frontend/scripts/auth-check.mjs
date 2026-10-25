// Run: node scripts/auth-check.mjs  (Node >= 22.18 strips TypeScript types)
// The launch identity decision of src/lib/authPlan.ts (used by hooks/useTelegramAuth.ts).
import assert from "node:assert/strict";
import { isAccountSwitch, planAuthBoot, userScopedKeys } from "../src/lib/authPlan.ts";

const A = 900000000001;
const B = 900000000002;
const LINK = "A".repeat(39);
const sA = { token: "tok-a", userId: A };
const legacy = { token: "tok-old", userId: null };
const base = { hasInitData: false, initDataUserId: null, botLink: null, botLinkUserId: null, stored: null };
const plan = (over) => planAuthBoot({ ...base, ...over });
let n = 0;
const eq = (actual, expected, msg) => {
  assert.deepEqual(actual, expected, msg);
  n += 1;
};

// (a) initData present: reuse only for the same recorded user, else clear + login.
eq(plan({ hasInitData: true, initDataUserId: A, stored: sA }), { kind: "reuse" }, "same account reuses");
eq(plan({ hasInitData: true, initDataUserId: B, stored: sA }), { kind: "initData", clearStored: true }, "other account is replaced");
eq(plan({ hasInitData: true, initDataUserId: A, stored: legacy }), { kind: "initData", clearStored: true }, "unknown owner is replaced");
eq(plan({ hasInitData: true, initDataUserId: null, stored: sA }), { kind: "initData", clearStored: true }, "no initData user id: login");
eq(plan({ hasInitData: true, initDataUserId: A }), { kind: "initData", clearStored: false }, "nothing stored: login");
// initData wins over a link, even one for the stored user.
eq(
  plan({ hasInitData: true, initDataUserId: B, botLink: LINK, botLinkUserId: A, stored: sA }),
  { kind: "initData", clearStored: true },
  "initData beats bt",
);

// (b) bt without initData: always exchanged, the stored session is always dropped.
eq(
  plan({ botLink: LINK, botLinkUserId: B, stored: sA }),
  { kind: "botLink", clearStored: true, fallback: null },
  "bt of another account replaces, no fallback",
);
eq(
  plan({ botLink: LINK, botLinkUserId: A, stored: sA }),
  { kind: "botLink", clearStored: true, fallback: sA },
  "bt of the same account is still exchanged; own session is the fallback",
);
eq(
  plan({ botLink: LINK, botLinkUserId: null, stored: legacy }),
  { kind: "botLink", clearStored: true, fallback: null },
  "unknown owners never match",
);
eq(plan({ botLink: LINK, botLinkUserId: A }), { kind: "botLink", clearStored: false, fallback: null }, "bt, nothing stored");

// (c) no identity source.
eq(plan({ stored: sA }), { kind: "restore" }, "reload after bt left the URL");
eq(plan({}), { kind: "none" }, "nothing at all");

eq(isAccountSwitch(A, B), true, "switch");
eq(isAccountSwitch(A, A), false, "same");
eq(isAccountSwitch(null, A), false, "first login");

const keys = [
  `resume_wizard_draft_v2:${A}`,
  `resume_wizard_photo_v1:${A}`,
  `resume_wizard_draft_v2:${B}`,
  `resume_wizard_draft_v2:${A}0`,
  "vakant_lang",
  "session_token",
];
eq(userScopedKeys(keys, A), [`resume_wizard_draft_v2:${A}`, `resume_wizard_photo_v1:${A}`], "only A's keys");
eq(userScopedKeys(keys, 0), [], "invalid id purges nothing");

console.log(`auth-check: ${n} assertions ok`);
