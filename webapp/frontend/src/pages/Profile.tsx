function labelize(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (s) => s.toUpperCase());
}

function valueToText(value: unknown): string {
  if (typeof value === "boolean") return value ? "Ha" : "Yo'q";
  if (value === null || value === undefined || value === "") return "-";
  return String(value);
}

function maskHash(hash: string | undefined): string {
  if (!hash) return "-";
  if (hash.length <= 16) return hash;
  return `${hash.slice(0, 8)}...${hash.slice(-8)}`;
}

export default function Profile() {
  const webApp = window.Telegram?.WebApp;
  const initData = webApp?.initDataUnsafe;
  const user = initData?.user;

  if (!webApp) {
    return (
      <div className="card p-6 text-center">
        <p className="text-base font-semibold text-slate-700">Profil</p>
        <p className="mt-2 text-sm text-slate-500">
          Profil ma'lumotlari Telegram ichida ochilganda ko'rinadi.
        </p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="card p-6 text-center">
        <p className="text-base font-semibold text-slate-700">Profil</p>
        <p className="mt-2 text-sm text-slate-500">
          Telegram user ma'lumotlari topilmadi. WebApp tugmasi orqali qayta ochib ko'ring.
        </p>
      </div>
    );
  }

  const fullName = [user.first_name, user.last_name].filter(Boolean).join(" ");
  const knownKeys = new Set([
    "id",
    "first_name",
    "last_name",
    "username",
    "language_code",
    "photo_url",
    "is_premium",
    "allows_write_to_pm",
    "added_to_attachment_menu",
    "is_bot",
  ]);
  const extraUserFields = Object.entries(user).filter(([k]) => !knownKeys.has(k));

  return (
    <div className="space-y-4">
      <section className="card p-4">
        <div className="flex items-center gap-3">
          <div className="h-14 w-14 overflow-hidden rounded-full border border-slate-200 bg-slate-100">
            {user.photo_url ? (
              <img src={user.photo_url} alt={fullName || "Avatar"} className="h-full w-full object-cover" />
            ) : null}
          </div>
          <div>
            <p className="text-base font-semibold text-slate-800">{fullName || "Telegram user"}</p>
            <p className="text-sm text-slate-500">{user.username ? `@${user.username}` : "@username yo'q"}</p>
          </div>
        </div>
      </section>

      <section className="card p-4">
        <h3 className="text-sm font-semibold text-slate-800">Asosiy ma'lumotlar</h3>
        <div className="mt-3 grid gap-2 text-sm">
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
            <span className="text-slate-500">Telegram ID</span>
            <span className="font-medium text-slate-800">{user.id}</span>
          </div>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
            <span className="text-slate-500">First Name</span>
            <span className="font-medium text-slate-800">{valueToText(user.first_name)}</span>
          </div>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
            <span className="text-slate-500">Last Name</span>
            <span className="font-medium text-slate-800">{valueToText(user.last_name)}</span>
          </div>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
            <span className="text-slate-500">Username</span>
            <span className="font-medium text-slate-800">{valueToText(user.username ? `@${user.username}` : "")}</span>
          </div>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
            <span className="text-slate-500">Til</span>
            <span className="font-medium text-slate-800">{valueToText(user.language_code)}</span>
          </div>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
            <span className="text-slate-500">Premium</span>
            <span className="font-medium text-slate-800">{valueToText(user.is_premium)}</span>
          </div>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
            <span className="text-slate-500">PM ruxsat</span>
            <span className="font-medium text-slate-800">{valueToText(user.allows_write_to_pm)}</span>
          </div>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
            <span className="text-slate-500">Attachment Menu</span>
            <span className="font-medium text-slate-800">{valueToText(user.added_to_attachment_menu)}</span>
          </div>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
            <span className="text-slate-500">Bot user</span>
            <span className="font-medium text-slate-800">{valueToText(user.is_bot)}</span>
          </div>
        </div>
      </section>

      <section className="card p-4">
        <h3 className="text-sm font-semibold text-slate-800">WebApp sessiya</h3>
        <div className="mt-3 grid gap-2 text-sm">
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
            <span className="text-slate-500">Platform</span>
            <span className="font-medium text-slate-800">{valueToText(webApp.platform)}</span>
          </div>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
            <span className="text-slate-500">Telegram versiya</span>
            <span className="font-medium text-slate-800">{valueToText(webApp.version)}</span>
          </div>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
            <span className="text-slate-500">Auth date</span>
            <span className="font-medium text-slate-800">{valueToText(initData?.auth_date)}</span>
          </div>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
            <span className="text-slate-500">Start param</span>
            <span className="font-medium text-slate-800">{valueToText(initData?.start_param)}</span>
          </div>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
            <span className="text-slate-500">Query ID</span>
            <span className="font-medium text-slate-800">{valueToText(initData?.query_id)}</span>
          </div>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
            <span className="text-slate-500">Chat type</span>
            <span className="font-medium text-slate-800">{valueToText(initData?.chat_type)}</span>
          </div>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
            <span className="text-slate-500">Chat instance</span>
            <span className="font-medium text-slate-800">{valueToText(initData?.chat_instance)}</span>
          </div>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
            <span className="text-slate-500">Hash</span>
            <span className="font-medium text-slate-800">{maskHash(initData?.hash)}</span>
          </div>
        </div>
      </section>

      {extraUserFields.length ? (
        <section className="card p-4">
          <h3 className="text-sm font-semibold text-slate-800">Qo'shimcha user maydonlari</h3>
          <div className="mt-3 grid gap-2 text-sm">
            {extraUserFields.map(([key, value]) => (
              <div key={key} className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
                <span className="text-slate-500">{labelize(key)}</span>
                <span className="font-medium text-slate-800">{valueToText(value)}</span>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
