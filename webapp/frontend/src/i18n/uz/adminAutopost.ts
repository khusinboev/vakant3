/** adminAutopost namespace — owned by the corresponding admin page agent. uz is the source. */
const adminAutopost = {
  "adminAutopost.status.enabledLabel": "Holati",
  "adminAutopost.status.enabled": "Yoqilgan",
  "adminAutopost.status.disabled": "O'chirilgan",
  "adminAutopost.status.channel": "Kanal",
  "adminAutopost.status.notSet": "Belgilanmagan",
  "adminAutopost.status.channelLang": "Kanal tili",
  "adminAutopost.status.minSalary": "Minimal maosh",
  "adminAutopost.status.perDay": "Kuniga postlar",
  "adminAutopost.status.perDayRange": "{min}–{max}",
  "adminAutopost.status.editLink": "Sozlamalarda tahrirlash",
  "adminAutopost.status.sent": "Yuborilgan",
  "adminAutopost.status.failed": "Xatolik",
  "adminAutopost.status.skipped": "O'tkazib yuborilgan",

  "adminAutopost.schedule.postedOf": "Joylandi: {posted} / {total}",
  "adminAutopost.schedule.empty": "Bugun uchun slotlar yo'q",

  "adminAutopost.postNow.title": "Hoziroq joylash",
  "adminAutopost.postNow.description": "Vakansiya ID (uid) ni kiriting yoki bo'sh qoldiring — navbatdagi mos vakansiya tanlanadi.",
  "adminAutopost.postNow.uidLabel": "Vakansiya UID",
  "adminAutopost.postNow.uidPlaceholder": "osonish_12345",
  "adminAutopost.postNow.button": "Hoziroq joylash",
  "adminAutopost.postNow.confirmTitle": "Hoziroq joylashni tasdiqlang",
  "adminAutopost.postNow.confirmDescription": "{uid} kanalga hoziroq joylanadi. Davom etasizmi?",
  "adminAutopost.postNow.confirmButton": "Joylash",
  "adminAutopost.postNow.nextInQueue": "Navbatdagi mos vakansiya",
  "adminAutopost.postNow.jobDone": "Vakansiya kanalga joylandi",
  "adminAutopost.postNow.jobFailedGeneric": "Joylash muvaffaqiyatsiz tugadi",
  "adminAutopost.postNow.jobStatus.queued": "Navbatda",
  "adminAutopost.postNow.jobStatus.running": "Bajarilmoqda",
  "adminAutopost.postNow.jobStatus.done": "Bajarildi",
  "adminAutopost.postNow.jobStatus.failed": "Xatolik",
  "adminAutopost.postNow.jobStatusLabel": "Vazifa holati",
  "adminAutopost.postNow.resultUid": "Vakansiya",
  "adminAutopost.postNow.resultMessageId": "Xabar ID",
  "adminAutopost.postNow.resultError": "Xato",

  "adminAutopost.history.title": "Joylashlar tarixi",
  "adminAutopost.history.empty": "Hali joylashlar yo'q",
  "adminAutopost.history.filter.status": "Holat bo'yicha",
};

export type AdminAutopostDict = typeof adminAutopost;
export default adminAutopost;
