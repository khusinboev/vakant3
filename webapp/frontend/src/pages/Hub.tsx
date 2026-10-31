import { ArrowRight, FileText, Layers3, Scale } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { useT } from "../i18n/useT";

export default function HubPage() {
  const navigate = useNavigate();
  const t = useT();

  return (
    <div className="space-y-4">
      <section className="card p-4">
        <div className="flex items-center gap-2">
          <Layers3 size={16} className="text-primary" />
          <h2 className="text-sm font-semibold text-text">{t("hub.title")}</h2>
        </div>
        <p className="mt-2 text-sm text-muted">{t("hub.subtitle")}</p>
      </section>

      <section className="card p-4">
        <div className="flex items-center gap-2">
          <FileText size={16} className="text-primary" />
          <h3 className="text-sm font-semibold text-text">{t("hub.resume")}</h3>
        </div>
        <p className="mt-2 text-sm text-muted">{t("hub.resumeDesc")}</p>
        <button
          type="button"
          className="tap-target mt-4 flex w-full items-center justify-center gap-2 rounded-2xl bg-primary px-4 py-3 text-sm font-semibold text-primaryFg"
          onClick={() => navigate("/hub/resume")}
        >
          {t("hub.resumeCta")}
          <ArrowRight size={15} />
        </button>
      </section>

      <section className="card p-4">
        <div className="flex items-center gap-2">
          <Scale size={16} className="text-primary" />
          <h3 className="text-sm font-semibold text-text">{t("hub.laws")}</h3>
        </div>
        <p className="mt-2 text-sm text-muted">{t("hub.lawsDesc")}</p>
        <button
          type="button"
          className="tap-target mt-4 flex w-full items-center justify-center gap-2 rounded-2xl border border-border bg-surfaceAlt px-4 py-3 text-sm font-semibold text-text"
          onClick={() => navigate("/hub/laws")}
        >
          {t("hub.lawsCta")}
          <ArrowRight size={15} />
        </button>
      </section>
    </div>
  );
}
