/** Open Telegram's share dialog for a referral link. */
export function shareRefLink(refLink: string, shareText: string): void {
  const tg = window.Telegram?.WebApp;
  const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(refLink)}&text=${encodeURIComponent(shareText)}`;
  if (tg?.openTelegramLink) tg.openTelegramLink(shareUrl);
  else window.open(shareUrl, "_blank", "noopener,noreferrer");
}

/** Clipboard write that resolves to false instead of throwing on denial. */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
