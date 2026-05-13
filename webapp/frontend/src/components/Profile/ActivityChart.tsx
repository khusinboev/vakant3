import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis } from "recharts";

type Props = {
  savesCount: number;
  referralsCount: number;
};

export default function ActivityChart({ savesCount, referralsCount }: Props) {
  const data = [
    { name: "Saqlash", value: savesCount },
    { name: "Referral", value: referralsCount }
  ];

  return (
    <div className="card p-4">
      <h3 className="font-semibold">Faollik</h3>
      <div className="mt-3 h-48 w-full">
        <ResponsiveContainer>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <Tooltip />
            <Bar dataKey="value" fill="#0f766e" radius={8} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
