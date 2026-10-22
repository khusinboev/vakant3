// Run: node scripts/nav-check.mjs  (Node >= 22.18 strips TypeScript types)
import assert from "node:assert/strict";
import { parentOf, isAdminPath } from "../src/lib/nav/parents.ts";

const cases = [
  ["/app", null],
  ["/", null],
  ["/profile", "/app"],
  ["/hub", "/app"],
  ["/saves", "/profile"],
  ["/wallet", "/profile"],
  ["/referral", "/profile"],
  ["/hub/resume", "/hub"],
  ["/hub/laws", "/hub"],
  ["/hub/laws/", "/hub"],
  ["/unknown", "/app"],
  ["/admin", "/app"],
  ["/admin/users", "/admin"],
  ["/admin/users/7", "/admin/users"],
  ["/admin/users/7/action/ban", "/admin/users/7"],
  ["/admin/content/laws/5", "/admin/content/laws"],
  ["/admin/content/laws", "/admin/content"],
  ["/admin/broadcasts/new", "/admin/broadcasts"],
];
for (const [path, parent] of cases) assert.equal(parentOf(path), parent, path);

assert.equal(parentOf("/wallet", { navParent: "/app" }), "/app");
assert.equal(parentOf("/wallet", { navParent: "//evil.example" }), "/profile");
assert.equal(parentOf("/wallet", { navParent: "/wallet" }), "/profile");
assert.equal(parentOf("/app", { navParent: "/profile" }), null);
assert.ok(isAdminPath("/admin") && isAdminPath("/admin/x") && !isAdminPath("/administrator"));
console.log(`nav-check: ${cases.length + 5} assertions ok`);
