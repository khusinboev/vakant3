import { useState, type FormEvent } from "react";
import { CheckCircle2, PlusCircle, ShieldAlert } from "lucide-react";

import Field, { INPUT_CLS } from "../../../components/ui/Field";
import { useT } from "../../../i18n/useT";
import type { ChannelCreateResult } from "../../../api/adminTypes";
import Button from "../ui/Button";
import { describeAddChannelError, type ChannelFormMessage } from "./channelErrors";
import { useAddChannel } from "./useChannels";

type Result =
  | { kind: "success"; data: ChannelCreateResult }
  | { kind: "error"; message: ChannelFormMessage };

/**
 * The body of the "channels.add" sheet (`ChannelsPage`): paste a link
 * (@name, t.me/name, t.me/+invite, -100… id), submit, and see the resolved
 * result right there — a private invite link cannot be resolved by `getChat`,
 * so the backend asks for the numeric chat id alongside it
 * (CHANNEL_INVALID{reason: "invite_link_requires_chat_id"}); this form reveals
 * that second field only when the server actually asks for it. The sheet
 * itself stays open after success so the admin can see the result before
 * closing it (back / Esc / the sheet's own close button).
 */
export default function AddChannelForm() {
  const t = useT();
  const addChannel = useAddChannel();
  const [link, setLink] = useState("");
  const [chatId, setChatId] = useState("");
  const [needsChatId, setNeedsChatId] = useState(false);
  const [result, setResult] = useState<Result | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const trimmedLink = link.trim();
    if (!trimmedLink || addChannel.isPending) return;

    const trimmedChatId = chatId.trim();
    const parsedChatId = trimmedChatId ? Number(trimmedChatId) : undefined;

    setResult(null);
    try {
      const data = await addChannel.mutateAsync({
        link: trimmedLink,
        chat_id: parsedChatId !== undefined && Number.isFinite(parsedChatId) ? parsedChatId : undefined,
      });
      setResult({ kind: "success", data });
      setLink("");
      setChatId("");
      setNeedsChatId(false);
    } catch (error) {
      const failure = describeAddChannelError(error);
      setResult({ kind: "error", message: failure.message });
      if (failure.needsChatId) setNeedsChatId(true);
    }
  };

  return (
    <form onSubmit={(event) => void submit(event)} className="space-y-3">
      <Field label={t("adminChannels.add.linkLabel")} hint={t("adminChannels.add.linkHint")}>
        <input
          className={INPUT_CLS}
          value={link}
          onChange={(event) => setLink(event.target.value)}
          placeholder={t("adminChannels.add.linkPlaceholder")}
          autoComplete="off"
          spellCheck={false}
          autoFocus
        />
      </Field>

      {needsChatId && (
        <Field label={t("adminChannels.add.chatIdLabel")} hint={t("adminChannels.add.chatIdHint")}>
          <input
            className={INPUT_CLS}
            value={chatId}
            onChange={(event) => setChatId(event.target.value)}
            placeholder="-1001234567890"
            inputMode="numeric"
          />
        </Field>
      )}

      <Button
        type="submit"
        size="md"
        variant="primary"
        full
        icon={PlusCircle}
        loading={addChannel.isPending}
        disabled={!link.trim()}
        labelKey={addChannel.isPending ? "adminChannels.add.checking" : "adminChannels.add.submit"}
      />

      <div aria-live="polite">
        {result?.kind === "success" && (
          <div className="mt-3 flex items-start gap-2 rounded-xl border border-success/40 bg-success/10 p-3 text-[13px]">
            <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-success" aria-hidden="true" />
            <div className="min-w-0">
              <p className="font-semibold text-text">
                {result.data.channel.title || result.data.channel.username || result.data.channel.id}
              </p>
              <p className="text-[11px] text-success">{t("adminChannels.add.success.admin")}</p>
            </div>
          </div>
        )}
        {result?.kind === "error" && (
          <div className="mt-3 flex items-start gap-2 rounded-xl border border-danger/40 bg-danger/10 p-3 text-[13px] text-danger">
            <ShieldAlert size={15} className="mt-0.5 shrink-0" aria-hidden="true" />
            <p className="min-w-0">{t(result.message.key, result.message.vars)}</p>
          </div>
        )}
      </div>
    </form>
  );
}
