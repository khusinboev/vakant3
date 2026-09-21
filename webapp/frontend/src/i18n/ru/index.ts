/** Lazy-loaded ru dictionary (one chunk); merged namespaces mirror uz. */
import common from "./common";
import vacancy from "./vacancy";
import resume from "./resume";
import admin from "./admin";
import adminUsers from "./adminUsers";
import adminBroadcasts from "./adminBroadcasts";
import adminChannels from "./adminChannels";
import adminContent from "./adminContent";
import adminFinance from "./adminFinance";
import adminSystem from "./adminSystem";
import adminAutopost from "./adminAutopost";

const dict = {
  ...common,
  ...vacancy,
  ...resume,
  ...admin,
  ...adminUsers,
  ...adminBroadcasts,
  ...adminChannels,
  ...adminContent,
  ...adminFinance,
  ...adminSystem,
  ...adminAutopost,
};
export default dict;
