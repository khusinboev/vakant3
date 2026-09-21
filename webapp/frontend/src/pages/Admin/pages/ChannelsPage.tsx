import { Radio } from "lucide-react";

import { useT } from "../../../i18n/useT";
import AddChannelForm from "../channels/AddChannelForm";
import ChannelsList from "../channels/ChannelsList";
import GateInfoCard from "../channels/GateInfoCard";
import GroupCard from "../components/GroupCard";

/**
 * Required subscription channels for the entry gate (CONTRACT_P12 §m006).
 * The auto-post destination channel is a separate concept and stays on the
 * Settings page — this page only owns the gate's channel list.
 */
export default function ChannelsPage() {
  const t = useT();

  return (
    <div className="space-y-4 py-4">
      <div>
        <h1 className="text-lg font-bold text-text">{t("adminChannels.title")}</h1>
        <p className="mt-0.5 text-sm text-muted">{t("adminChannels.subtitle")}</p>
      </div>

      <GateInfoCard />

      <GroupCard icon={Radio} title={t("adminChannels.add.title")} divide={false}>
        <div className="py-3">
          <AddChannelForm />
        </div>
      </GroupCard>

      <ChannelsList />
    </div>
  );
}
