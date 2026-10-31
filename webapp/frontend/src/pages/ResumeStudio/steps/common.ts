import type { ResumeDraft } from "../useResumeDraft";

/** Props shared by every wizard step. */
export type StepProps = {
  draft: ResumeDraft;
  /** Field name -> translated validation message for the current step. */
  errors: Record<string, string>;
};
