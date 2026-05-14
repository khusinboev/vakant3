type Props = {
  refLink: string;
  count: number;
};

export default function ReferralCard({ refLink, count }: Props) {
  const share = async () => {
    if (navigator.share) {
      await navigator.share({ title: "Bandlik.uz", text: "Ish qidirish uchun bot", url: refLink });
      return;
    }
    await navigator.clipboard.writeText(refLink);
    alert("Havola nusxalandi");
  };

  return (
    <section className="card p-4">
      <h2 className="font-semibold">Referral havolangiz</h2>
      <p className="mt-2 rounded-xl bg-slate-100 p-3 text-sm break-all">{refLink}</p>
      <div className="mt-3 flex items-center justify-between">
        <p className="text-sm text-slate-600">Siz taklif qilgan odamlar: {count} ta</p>
        <button onClick={share} className="tap-target rounded-xl bg-brand-500 px-4 text-sm font-semibold text-white">
          Ulashish
        </button>
      </div>
    </section>
  );
}
