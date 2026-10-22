/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Telegram username of the bot (no leading @). See src/lib/constants.ts. */
  readonly VITE_BOT_USERNAME?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
