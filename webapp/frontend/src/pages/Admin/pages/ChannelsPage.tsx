import { Plus } from "lucide-react";

import AddChannelForm from "../channels/AddChannelForm";
import ChannelsList from "../channels/ChannelsList";
import GateInfoCard from "../channels/GateInfoCard";
import { Accordion, Sheet, useAdminHeader, useHistorySheet } from "../ui";

/**
 * Required subscription channels for the entry gate (CONTRACT_P12 §m006).
 * The auto-post destination channel is a separate concept and stays on the
 * Settings page — this page only owns the gate's channel list.
 *
 * v3 layout (spec §4/§4b): the list comes first, "Qo'shish" is the page's one
 * primary action (the header wires it to the Telegram MainButton on mobile)
 * and opens a history-backed sheet with the add form; the gate explainer is a
 * closed accordion item at the bottom instead of a card above the list.
 */
export default function ChannelsPage() {
  const addSheet = useHistorySheet("channels.add");

  useAdminHeader({
    titleKey: "adminChannels.title",
    primary: { labelKey: "adminChannels.add.submit", icon: Plus, onClick: () => addSheet.openSheet() },
  });

  return (
    <div className="space-y-3">
      <ChannelsList />

      <Accordion
        queryKey="info"
        items={[
          {
            id: "gate-info",
            titleKey: "adminChannels.info.title",
            content: <GateInfoCard />,
          },
        ]}
      />

      <Sheet name="channels.add" titleKey="adminChannels.add.title">
        <AddChannelForm />
      </Sheet>
    </div>
  );
}
