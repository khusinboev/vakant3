/**
 * Miniature of what each PDF template looks like.
 *
 * These colours are deliberately literal, not semantic tokens: the card is a
 * picture of a printed white A4 page, so it must stay light in dark mode too.
 */
export default function TemplatePreview({ id, color }: { id: string; color: string }) {
  // Derive a dark blended variant of the accent color for dark-header templates
  const r = parseInt(color.slice(1, 3), 16) || 30;
  const g = parseInt(color.slice(3, 5), 16) || 58;
  const b = parseInt(color.slice(5, 7), 16) || 95;
  const dr = Math.max(10, Math.min(80, Math.round(r * 0.35 + 15)));
  const dg = Math.max(10, Math.min(80, Math.round(g * 0.35 + 15)));
  const db = Math.max(30, Math.min(120, Math.round(b * 0.45 + 40)));
  const dark = `rgb(${dr},${dg},${db})`;

  const Row = ({ w, thin }: { w: string; thin?: boolean }) => (
    <div className={`${thin ? "h-px" : "h-[3px]"} rounded-sm bg-slate-200`} style={{ width: w }} />
  );
  const AccRow = ({ w }: { w: string }) => (
    <div className="h-[3px] rounded-sm" style={{ width: w, backgroundColor: color, opacity: 0.55 }} />
  );

  switch (id) {
    case "clean":
      return (
        <div className="w-full h-[108px] bg-white rounded-xl overflow-hidden border border-slate-100">
          <div className="h-9 w-full px-2.5 flex flex-col justify-center gap-0.5" style={{ backgroundColor: color }}>
            <div className="h-2 w-16 rounded-sm bg-white/80" />
            <div className="h-[3px] w-10 rounded-sm bg-white/50" />
            <div className="h-[3px] w-20 rounded-sm bg-white/35" />
          </div>
          <div className="px-2.5 pt-2 space-y-1">
            <AccRow w="40%" />
            <Row w="100%" /><Row w="80%" /><Row w="100%" /><Row w="65%" /><Row w="90%" />
          </div>
        </div>
      );
    case "modern":
      return (
        <div className="w-full h-[108px] bg-white rounded-xl overflow-hidden border border-slate-100 flex">
          <div className="w-14 h-full flex flex-col items-center pt-2.5 gap-1.5 shrink-0" style={{ backgroundColor: color }}>
            <div className="w-7 h-7 rounded-full bg-white/25 border-2 border-white/40" />
            <div className="h-[3px] w-8 rounded-sm bg-white/65" />
            <div className="h-[2px] w-6 rounded-sm bg-white/45" />
            <div className="mt-1 h-[2px] w-8 rounded-sm bg-white/40" />
            <div className="h-[2px] w-7 rounded-sm bg-white/30" />
            <div className="h-[2px] w-8 rounded-sm bg-white/30" />
            <div className="h-[2px] w-6 rounded-sm bg-white/30" />
          </div>
          <div className="flex-1 p-2 space-y-1.5">
            <AccRow w="70%" />
            <Row w="100%" /><Row w="80%" /><Row w="100%" thin />
            <AccRow w="55%" />
            <Row w="100%" /><Row w="70%" /><Row w="90%" />
          </div>
        </div>
      );
    case "compact":
      return (
        <div className="w-full h-[108px] bg-white rounded-xl overflow-hidden border border-slate-100 p-2.5">
          <div className="h-2.5 w-20 rounded-sm bg-slate-800" />
          <div className="h-[3px] w-12 rounded-sm bg-slate-500 mt-0.5" />
          <div className="h-px w-full bg-slate-800 mt-1.5" />
          <div className="mt-1 space-y-[3px]">
            {["100%","80%","100%","60%","100%","75%","90%","55%"].map((w, i) => (
              <div key={i} className="h-[3px] rounded-sm bg-slate-300" style={{ width: w }} />
            ))}
          </div>
        </div>
      );
    case "executive":
      return (
        <div className="w-full h-[108px] bg-white rounded-xl overflow-hidden border border-slate-100">
          <div className="h-10 w-full px-2.5 flex flex-col justify-center gap-0.5" style={{ backgroundColor: dark }}>
            <div className="h-2.5 w-16 rounded-sm bg-white/75" />
            <div className="h-[3px] w-11 rounded-sm bg-white/45" />
          </div>
          <div className="h-[3px] w-full" style={{ backgroundColor: color }} />
          <div className="px-2.5 pt-1.5 space-y-1">
            <AccRow w="45%" />
            <div className="flex gap-2">
              <div className="flex-1 space-y-[3px]">
                <Row w="100%" /><Row w="80%" /><Row w="100%" />
              </div>
              <div className="flex-1 space-y-[3px]">
                <Row w="100%" /><Row w="70%" /><Row w="90%" />
              </div>
            </div>
          </div>
        </div>
      );
    case "timeline":
      return (
        <div className="w-full h-[108px] bg-white rounded-xl overflow-hidden border border-slate-100">
          <div className="h-7 w-full" style={{ backgroundColor: color }} />
          <div className="px-2.5 pt-2 flex gap-2">
            <div className="w-px self-stretch rounded-full" style={{ backgroundColor: color, opacity: 0.65, minHeight: 70 }} />
            <div className="flex-1 space-y-2">
              {[0, 1, 2].map((i) => (
                <div key={i} className="relative pl-1.5">
                  <div className="absolute -left-[7px] top-0.5 w-[5px] h-[5px] rounded-full" style={{ backgroundColor: color }} />
                  <div className="h-2 w-16 rounded-sm bg-slate-300" />
                  <div className="h-[2px] w-12 rounded-sm bg-slate-200 mt-0.5" />
                </div>
              ))}
            </div>
          </div>
        </div>
      );
    case "minimal":
      return (
        <div className="w-full h-[108px] bg-white rounded-xl overflow-hidden border border-slate-100 p-2.5">
          <div className="h-4 w-20 rounded-sm bg-slate-800" />
          <div className="h-[3px] w-14 rounded-sm bg-slate-500 mt-0.5" />
          <div className="h-px w-full bg-slate-200 mt-2" />
          <div className="mt-1.5 space-y-1">
            <div className="h-[2px] w-10 rounded-sm bg-slate-400" />
            <Row w="100%" /><Row w="80%" />
            <div className="h-px w-full bg-slate-200 mt-1" />
            <div className="h-[2px] w-8 rounded-sm bg-slate-400 mt-0.5" />
            <Row w="100%" /><Row w="70%" />
          </div>
        </div>
      );
    case "creative":
      return (
        <div className="w-full h-[108px] bg-white rounded-xl overflow-hidden border border-slate-100 flex">
          <div className="w-3 h-full shrink-0" style={{ backgroundColor: color }} />
          <div className="flex-1 p-2 space-y-1">
            <div className="h-3 w-16 rounded-sm bg-slate-800" />
            <AccRow w="55%" />
            <div className="h-px w-full bg-slate-200" />
            <Row w="100%" /><Row w="80%" /><Row w="100%" />
            <div className="flex gap-1 flex-wrap pt-0.5">
              {[18, 14, 20, 12, 16].map((w, i) => (
                <div key={i} className="h-3 rounded-sm" style={{ width: w, backgroundColor: color, opacity: 0.25 }} />
              ))}
            </div>
          </div>
        </div>
      );
    case "photo_classic":
      return (
        <div className="w-full h-[108px] bg-white rounded-xl overflow-hidden border border-slate-100">
          <div className="h-10 w-full px-2.5 flex items-center gap-2" style={{ backgroundColor: color }}>
            <div className="flex-1 space-y-0.5">
              <div className="h-2 w-14 rounded-sm bg-white/80" />
              <div className="h-[3px] w-9 rounded-sm bg-white/50" />
              <div className="h-[3px] w-16 rounded-sm bg-white/35" />
            </div>
            <div className="w-8 h-8 rounded-lg border-2 border-white/60 bg-white/20 flex items-center justify-center shrink-0">
              <span className="text-white/70 text-[11px]">📷</span>
            </div>
          </div>
          <div className="px-2.5 pt-1.5 space-y-1">
            <AccRow w="40%" />
            <Row w="100%" /><Row w="80%" />
            <div className="flex gap-1 pt-0.5 flex-wrap">
              {[16, 12, 18, 14].map((w, i) => (
                <div key={i} className="h-3 rounded-sm" style={{ width: w, backgroundColor: color, opacity: 0.25 }} />
              ))}
            </div>
          </div>
        </div>
      );
    case "photo_sidebar":
      return (
        <div className="w-full h-[108px] bg-white rounded-xl overflow-hidden border border-slate-100 flex">
          <div className="w-[58px] h-full flex flex-col items-center pt-2 gap-1 shrink-0" style={{ backgroundColor: color }}>
            <div className="w-9 h-9 rounded-full border-2 border-white/55 bg-white/20 flex items-center justify-center">
              <span className="text-white/70 text-[11px]">📷</span>
            </div>
            <div className="h-[3px] w-9 rounded-sm bg-white/65 mt-0.5" />
            <div className="h-[2px] w-7 rounded-sm bg-white/45" />
            <div className="mt-1 h-[2px] w-9 rounded-sm bg-white/40" />
            <div className="h-[2px] w-8 rounded-sm bg-white/30" />
            <div className="h-[2px] w-9 rounded-sm bg-white/30" />
          </div>
          <div className="flex-1 p-2 space-y-1.5">
            <AccRow w="70%" />
            <Row w="100%" /><Row w="80%" /><Row w="100%" thin />
            <AccRow w="55%" />
            <Row w="100%" /><Row w="70%" />
          </div>
        </div>
      );
    case "europass":
      return (
        <div className="w-full h-[108px] bg-white rounded-xl overflow-hidden border border-slate-100">
          <div className="h-8 w-full px-2.5 flex items-center gap-2" style={{ backgroundColor: color }}>
            <div className="flex-1 space-y-0.5">
              <div className="h-2 w-14 rounded-sm bg-white/80" />
              <div className="h-[3px] w-9 rounded-sm bg-white/50" />
            </div>
            <div className="w-6 h-6 border border-white/50 bg-white/15 rounded-sm flex items-center justify-center shrink-0">
              <span className="text-white/65 text-[9px]">📷</span>
            </div>
          </div>
          {["60%", "90%", "75%"].map((cw, i) => (
            <div key={i} className="flex border-b border-slate-100 px-2">
              <div className="w-10 py-1">
                <div className="h-[3px] rounded-sm" style={{ width: "80%", backgroundColor: color, opacity: 0.55 }} />
              </div>
              <div className="flex-1 py-1 pl-1 space-y-[3px]">
                <div className="h-[3px] rounded-sm bg-slate-200" style={{ width: cw }} />
                {i === 0 && <div className="h-[2px] rounded-sm bg-slate-100 w-4/5" />}
              </div>
            </div>
          ))}
          <div className="h-3 w-full flex items-center px-2" style={{ backgroundColor: color, opacity: 0.85 }}>
            <div className="h-[3px] w-14 rounded-sm bg-white/70" />
          </div>
        </div>
      );
    case "infographic":
      return (
        <div className="w-full h-[108px] bg-white rounded-xl overflow-hidden border border-slate-100">
          <div className="h-11 w-full relative" style={{ backgroundColor: dark }}>
            <div className="absolute left-0 top-0 bottom-0 w-1.5" style={{ backgroundColor: color }} />
            <div className="pl-4 pt-2.5 space-y-0.5">
              <div className="h-2.5 w-16 rounded-sm bg-white/70" />
              <div className="h-[3px] w-10 rounded-sm bg-white/40" />
            </div>
          </div>
          <div className="h-[3px] w-full" style={{ backgroundColor: color }} />
          <div className="px-2.5 pt-1.5 space-y-1">
            <AccRow w="40%" />
            {["55%", "85%"].map((fill, i) => (
              <div key={i} className="flex items-center gap-1.5">
                <div className="h-[3px] w-12 rounded-sm bg-slate-300" />
                <div className="flex-1 h-1.5 rounded-sm bg-slate-100 overflow-hidden">
                  <div className="h-full rounded-sm" style={{ width: fill, backgroundColor: color, opacity: 0.65 }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      );
    default:
      return (
        <div className="w-full h-[108px] bg-white rounded-xl overflow-hidden border border-slate-100 flex items-center justify-center">
          <div className="w-10 h-10 rounded-full" style={{ backgroundColor: color, opacity: 0.25 }} />
        </div>
      );
  }
}
