/** Lazy-loaded en dictionary (one chunk); merged namespaces mirror uz. */
import common from "./common";
import vacancy from "./vacancy";
import resume from "./resume";
import admin from "./admin";

const dict = { ...common, ...vacancy, ...resume, ...admin };
export default dict;
