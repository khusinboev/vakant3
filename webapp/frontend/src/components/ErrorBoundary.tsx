import { Component, type ErrorInfo, type ReactNode } from "react";
import { RotateCcw } from "lucide-react";

import { useT } from "../i18n/useT";

function DefaultFallback({ onReset }: { onReset: () => void }) {
  const t = useT();
  return (
    <div className="card mx-auto mt-6 max-w-md p-6 text-center">
      <p className="text-base font-semibold text-text">{t("app.errorTitle")}</p>
      <p className="mt-2 text-sm text-muted">{t("app.errorBody")}</p>
      <button
        type="button"
        className="tap-target mt-4 inline-flex items-center justify-center gap-2 rounded-2xl bg-primary px-4 py-2.5 text-sm font-semibold text-primaryFg"
        onClick={onReset}
      >
        <RotateCcw size={15} />
        {t("app.reload")}
      </button>
    </div>
  );
}

type Props = {
  children: ReactNode;
  /** Custom fallback. `reset` re-renders the subtree without a full page reload. */
  fallback?: (error: Error, reset: () => void) => ReactNode;
};

type State = { error: Error | null };

/**
 * Catches render errors in a subtree and shows a translated recovery card.
 * Wrap `<Routes>` and any lazily-loaded page that can fail on its own.
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Surfacing in the console is the only reporting channel we have here.
    console.error("ErrorBoundary caught", error, info.componentStack);
  }

  reset = () => {
    this.setState({ error: null });
  };

  reload = () => {
    this.setState({ error: null });
    window.location.reload();
  };

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    if (this.props.fallback) return this.props.fallback(error, this.reset);
    return <DefaultFallback onReset={this.reload} />;
  }
}
