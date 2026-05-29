import { ArrowRight, FileText, Layers3 } from "lucide-react";
import { useNavigate } from "react-router-dom";

export default function HubPage() {
  const navigate = useNavigate();

  return (
    <div className="space-y-4">
      <section className="card p-4">
        <div className="flex items-center gap-2">
          <Layers3 size={16} className="text-brand-600" />
          <h2 className="text-sm font-semibold text-slate-800">Markaz</h2>
        </div>
        <p className="mt-2 text-sm text-slate-600">
          Resume va keyinchalik boshqa foydali vositalar shu yerda bo'ladi.
        </p>
      </section>

      <section className="card p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <FileText size={16} className="text-emerald-600" />
              <h3 className="text-sm font-semibold text-slate-800">Resume Studio</h3>
            </div>
            <p className="mt-2 text-sm text-slate-600">
              Professional resume form, shablon previewlari va rang tanlash bilan resume yarating.
            </p>
          </div>
        </div>

        <button
          className="tap-target mt-4 flex w-full items-center justify-center gap-2 rounded-2xl bg-emerald-600 px-4 py-3 text-sm font-semibold text-white"
          onClick={() => navigate("/hub/resume")}
        >
          Resume yasash
          <ArrowRight size={15} />
        </button>
      </section>

      <section className="card p-4">
        <h3 className="text-sm font-semibold text-slate-800">Yaqinda qo'shiladi</h3>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-600">
          <li>Cover letter generator</li>
          <li>Interview savollari simulyatori</li>
          <li>Job match tavsiyalari</li>
        </ul>
      </section>
    </div>
  );
}
