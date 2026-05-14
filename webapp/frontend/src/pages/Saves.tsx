export default function Saves() {
  const tgUser = window.Telegram?.WebApp?.initDataUnsafe?.user;
  const displayUser = tgUser?.first_name || (tgUser?.id ? `ID: ${tgUser.id}` : null);

  return (
    <div className="card flex flex-col items-center gap-3 p-8 text-center">
      <p className="text-base font-semibold text-slate-700">Saqlangan ishlar</p>
      <p className="text-sm text-slate-500">Bu bo'lim hozircha mavjud emas.</p>
      {displayUser ? (
        <p className="text-xs text-slate-400">Tez orada, {displayUser}</p>
      ) : (
        <p className="text-xs text-slate-400">Tez orada.</p>
      )}
    </div>
  );
}
