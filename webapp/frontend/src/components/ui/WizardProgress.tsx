import { Fragment } from "react";
import { Check } from "lucide-react";

export type WizardStep = {
  id: string;
  label: string;
  done?: boolean;
};

export type WizardProgressProps = {
  steps: WizardStep[];
  /** Index of the step currently shown. */
  current: number;
  onStepClick: (index: number) => void;
};

/**
 * Horizontal numbered step indicator with connectors. A step is tappable once
 * it is behind the current one or already marked `done`.
 */
export default function WizardProgress({ steps, current, onStepClick }: WizardProgressProps) {
  return (
    <div className="scrollbar-hide flex items-center overflow-x-auto px-4 pb-2.5">
      {steps.map((step, index) => {
        const active = current === index;
        const clickable = index < current || step.done;
        return (
          <Fragment key={step.id}>
            <button
              type="button"
              aria-current={active ? "step" : undefined}
              className="flex min-w-[46px] shrink-0 flex-col items-center disabled:cursor-default"
              onClick={() => clickable && onStepClick(index)}
              disabled={!clickable}
            >
              <div
                className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold transition-all duration-200 ${
                  active
                    ? "bg-primary text-primaryFg shadow-md"
                    : step.done
                      ? "bg-success text-white"
                      : index < current
                        ? "bg-border text-muted"
                        : "border border-border bg-surfaceAlt text-muted/60"
                }`}
              >
                {step.done && !active ? <Check size={12} /> : index + 1}
              </div>
              <span
                className={`mt-0.5 whitespace-nowrap text-[9px] font-medium transition-colors ${
                  active ? "text-primary" : step.done ? "text-success" : "text-muted"
                }`}
              >
                {step.label}
              </span>
            </button>
            {index < steps.length - 1 && (
              <div
                className={`mx-0.5 h-0.5 min-w-[6px] flex-1 rounded-full transition-all duration-500 ${
                  step.done ? "bg-success" : "bg-border"
                }`}
              />
            )}
          </Fragment>
        );
      })}
    </div>
  );
}
