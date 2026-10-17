import Field, { INPUT_CLS } from "../../../components/ui/Field";
import { useT } from "../../../i18n/useT";
import type { StepProps } from "./common";

export default function BasicStep({ draft, errors }: StepProps) {
  const t = useT();
  const { profile, patchProfile } = draft;
  const optional = `(${t("common.optional")})`;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <Field label={t("resume.field.fullName")} required error={errors.full_name}>
          <input
            className={INPUT_CLS}
            placeholder={t("resume.ph.fullName")}
            value={profile.full_name}
            onChange={(event) => patchProfile({ full_name: event.target.value })}
          />
        </Field>
        <Field label={t("resume.field.position")} required error={errors.position}>
          <input
            className={INPUT_CLS}
            placeholder={t("resume.ph.position")}
            value={profile.position}
            onChange={(event) => patchProfile({ position: event.target.value })}
          />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Field label={t("resume.field.phone")} error={errors.contact}>
          <input
            className={INPUT_CLS}
            type="tel"
            placeholder={t("resume.ph.phone")}
            value={profile.phone}
            onChange={(event) => patchProfile({ phone: event.target.value })}
          />
        </Field>
        <Field label={t("resume.field.email")}>
          <input
            className={INPUT_CLS}
            type="email"
            placeholder={t("resume.ph.email")}
            value={profile.email}
            onChange={(event) => patchProfile({ email: event.target.value })}
          />
        </Field>
      </div>

      <Field label={t("resume.field.location")}>
        <input
          className={INPUT_CLS}
          placeholder={t("resume.ph.location")}
          value={profile.location}
          onChange={(event) => patchProfile({ location: event.target.value })}
        />
      </Field>

      <Field label={t("resume.field.website")} hint={optional}>
        <input
          className={INPUT_CLS}
          placeholder={t("resume.ph.website")}
          value={profile.website}
          onChange={(event) => patchProfile({ website: event.target.value })}
        />
      </Field>
    </div>
  );
}
