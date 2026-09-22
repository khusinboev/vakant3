import type { AdminDict } from "../uz/admin";

const admin: Record<keyof AdminDict, string> = {
  // ── Shell ──────────────────────────────────────────────────────────────────
  "admin.title": "Admin panel",
  "admin.accessDenied": "The admin panel is for administrators only.",


  "admin.status.on": "On",
  "admin.status.off": "Off",

  "admin.dash.sparklineAria": "New users chart for the last 7 days",
  "admin.dash.sparklineLabel": "New users — 7 days",
  "admin.dash.systemOk": "System healthy",
  "admin.dash.systemDegraded": "System issue",
  "admin.dash.systemUnknown": "System status unknown",
  "admin.dash.autoPostLabel": "Auto-post",
  "admin.dash.postedTodayLabel": "Posted today",
  "admin.dash.referralLabel": "Referral",
  "admin.dash.minReferralsLabel": "Min. referrals",

  // ── Overview ───────────────────────────────────────────────────────────────
  "admin.overview.kpiTitle": "Resume KPI targets",

  "admin.kpi.completion": "Completion",
  "admin.kpi.sendSuccess": "Send success",
  "admin.kpi.pdfExport": "PDF export",
  "admin.kpi.creationTime": "Creation time",
  "admin.kpi.minutesShort": "min",
  "admin.kpi.openedUsers": "Opened",
  "admin.kpi.completedUsers": "Completed",
  "admin.kpi.sendAttempts": "Sent",

  // ── Settings ───────────────────────────────────────────────────────────────
  "admin.settings.group.autoPost": "Auto-post",
  "admin.settings.group.referralGate": "Referral gate",
  "admin.settings.group.pro": "Pro plan",
  "admin.settings.group.resumeKpi": "Resume KPI targets",

  "admin.settings.field.enabled": "Enabled",
  "admin.settings.field.channel": "Channel",
  "admin.settings.field.channelLang": "Channel language",
  "admin.settings.field.autoPostMinSalary": "Minimum salary (UZS)",
  "admin.settings.field.perDayMin": "Min per day",
  "admin.settings.field.perDayMax": "Max per day",
  "admin.settings.field.requiredRefs": "Referrals required",
  "admin.settings.field.proPrice": "Pro price (UZS)",
  "admin.settings.field.referralReward": "Referral reward (UZS)",
  "admin.settings.field.proMinSalary": "Pro minimum salary (UZS)",
  "admin.settings.field.targetCreationMinutes": "Creation time (min)",
  "admin.settings.field.targetCompletionRate": "Completion rate (%)",
  "admin.settings.field.targetSendRate": "Send success rate (%)",
  "admin.settings.field.targetExportRate": "PDF export success rate (%)",

  "admin.settings.editAria": "Edit {label}",
  "admin.settings.saved": "Setting saved.",
  "admin.settings.saving": "Saving…",
  "admin.settings.conflict.message": "This setting was changed elsewhere.",
  "admin.settings.conflict.reload": "Reload",
  "admin.settings.validation.number": "{label}: enter a number.",
  "admin.settings.validation.negative": "{label}: cannot be negative.",
  "admin.settings.validation.empty": "{label}: the value cannot be empty.",
  "admin.settings.validation.perDayRange":
    "The daily minimum must not exceed the maximum ({min} > {max}).",

  // ── Analytics ──────────────────────────────────────────────────────────────
  "admin.analytics.opsTitle": "Operations (24 h)",
  "admin.analytics.success": "Success",
  "admin.analytics.error": "Error",
  "admin.analytics.opSave": "Save",
  "admin.analytics.opSend": "Send",
  "admin.analytics.opExport": "Export",
  "admin.analytics.activeUsers": "Active users",
  "admin.analytics.opened": "Opened",
  "admin.analytics.ready": "Ready",
  "admin.analytics.latencyTitle": "Latency (average)",
  "admin.analytics.funnelTitle": "Funnel ({hours} h)",
  "admin.analytics.funnelEmpty": "No funnel data yet.",
  "admin.analytics.diagTitle": "Diagnostic errors",
  "admin.analytics.diagCount": "{n}×",
  "admin.analytics.noErrors": "No errors in the last 24 hours.",

  "admin.latency.ttfi": "TTFI",
  "admin.latency.save": "Save",
  "admin.latency.send": "Send",
  "admin.latency.export": "Export",
  "admin.latency.unit": "ms",

  "admin.funnel.entered": "{n} entered",
  "admin.funnel.dropped": "{n} dropped off",
  "admin.funnel.step.basic": "Basics",
  "admin.funnel.step.experience": "Experience",
  "admin.funnel.step.education": "Education",
  "admin.funnel.step.skills": "Skills",
  "admin.funnel.step.summary": "Summary",
  "admin.funnel.step.template": "Template",
  "admin.funnel.step.final": "Final",

  // ── Users ──────────────────────────────────────────────────────────────────

  // ── Shell v2 (AdminLayout / registry / shared components) ─────────────────
  "admin.nav.aria": "Admin sections",
  "admin.nav.group.main": "Overview",
  "admin.nav.group.people": "People",
  "admin.nav.group.content": "Content & channels",
  "admin.nav.group.money": "Finance",
  "admin.nav.group.system": "System",

  "admin.nav.overview": "Dashboard",
  "admin.nav.analytics": "Analytics",
  "admin.nav.resume": "Resume analytics",
  "admin.nav.users": "Users",
  "admin.nav.broadcasts": "Broadcasts",
  "admin.nav.channels": "Channels",
  "admin.nav.autopost": "Auto-post",
  "admin.nav.content": "Content",
  "admin.nav.finance": "Finance",
  "admin.nav.system": "System",
  "admin.nav.settings": "Settings",

  "admin.role.owner": "Owner",
  "admin.role.admin": "Admin",
  "admin.role.moderator": "Moderator",
  "admin.role.viewer": "Viewer",
  "admin.role.required": "This section needs the \"{role}\" role or higher.",

  "admin.shell.openPanel": "Open the admin panel",

  "admin.table.empty": "No data found.",
  "admin.table.loadMore": "Load more",
  "admin.table.loadingMore": "Loading...",
  "admin.table.total": "Total: {total}",

  "admin.confirm.title": "Confirm this action?",
  "admin.confirm.confirm": "Confirm",
  "admin.confirm.cancel": "Cancel",
  "admin.confirm.working": "Working...",

  "admin.filter.searchPlaceholder": "Search...",
  "admin.filter.all": "All",
  "admin.filter.from": "From",
  "admin.filter.to": "To",

  "admin.empty.default": "Nothing here yet.",
  "admin.stat.deltaUp": "up {value}",
  "admin.stat.deltaDown": "down {value}",


  // ── Analytics dashboard (daily_stats rollup) ────────────────────────────────
  "admin.analytics2.stat.groupLabel": "Today's numbers",
  "admin.analytics2.stat.hintToday": "today",
  "admin.analytics2.stat.newUsers": "New users",
  "admin.analytics2.stat.activeUsers": "Active users",
  "admin.analytics2.stat.proUsers": "Pro users",
  "admin.analytics2.stat.revenue": "Revenue",
  "admin.analytics2.stat.saves": "Saves",
  "admin.analytics2.stat.resumeSendsOk": "Resumes sent",
  "admin.analytics2.stat.resumeSendsErr": "Resume errors",
  "admin.analytics2.stat.autoPosts": "Auto-posts",
  "admin.analytics2.stat.notifications": "Notifications",

  "admin.analytics2.chart.usersTitle": "Users",
  "admin.analytics2.chart.usersAria": "Daily new and active users chart",
  "admin.analytics2.chart.usersNew": "New",
  "admin.analytics2.chart.usersActive": "Active",
  "admin.analytics2.chart.revenueTitle": "Revenue",
  "admin.analytics2.chart.revenueAria": "Daily revenue chart",
  "admin.analytics2.chart.resumeSendsTitle": "Resume sends",
  "admin.analytics2.chart.resumeSendsAria": "Daily successful and failed resume sends chart",
  "admin.analytics2.chart.resumeOk": "Ok",
  "admin.analytics2.chart.resumeErr": "Error",
  "admin.analytics2.chart.notifTitle": "Notifications & auto-posts",
  "admin.analytics2.chart.notifAria": "Daily notifications and auto-posts chart",
  "admin.analytics2.chart.notifNotifications": "Notifications",
  "admin.analytics2.chart.notifAutoPosts": "Auto-posts",

  "admin.analytics2.empty.title": "No stats computed yet",
  "admin.analytics2.empty.description":
    "The daily rollup hasn't run yet — charts will appear once the first day is complete.",

  "admin.analytics2.resumeKpi.title": "Resume KPIs",

  // ── Shell v3 (AdminShell / AdminBar / Rail / ui kit) ─────────────────────
  "admin.shell.back": "Back",
  "admin.shell.menu": "More actions",
  "admin.shell.actions": "Actions",
  "admin.shell.content": "Admin content",

  "admin.bar.home": "Home",
  "admin.bar.users": "People",
  "admin.bar.broadcasts": "Broadcast",
  "admin.bar.more": "More",

  "admin.more.title": "Sections",
  "admin.more.quickActions": "Quick actions",
  "admin.more.quick.postNow": "Post now",
  "admin.more.quick.newBroadcast": "New broadcast",
  "admin.more.quick.addChannel": "Add channel",

  "admin.rail.pin": "Pin the menu",
  "admin.rail.unpin": "Collapse the menu",

  "admin.sheet.close": "Close",

  "admin.filter.title": "Filters",
  "admin.filter.open": "Filters",
  "admin.filter.openCount": "Filters ({count})",
  "admin.filter.apply": "Apply",
  "admin.filter.clear": "Clear",
  "admin.filter.removeAria": "Remove the {label} filter",
  "admin.filter.on": "On",

  "admin.search.clear": "Clear the search",

  "admin.tabs.aria": "Sections",
  "admin.toolbar.more": "More",
  "admin.toolbar.moreAria": "More actions",

  "admin.period.aria": "Period",
  "admin.period.7": "7 days",
  "admin.period.30": "30 days",
  "admin.period.90": "90 days",
  "admin.period.365": "1 year",


};
export default admin;
