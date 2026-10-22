import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import { ensureDictionary } from "./i18n";
import { shouldRetryQuery } from "./lib/parseApiError";
import { currentLang } from "./store/lang";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    // No retry on 4xx/429 (the answer will not change and 429 would make it
    // worse); network errors and 5xx keep the default three attempts.
    queries: { retry: shouldRetryQuery },
  },
});

function render() {
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ErrorBoundary>
            <App />
          </ErrorBoundary>
        </BrowserRouter>
      </QueryClientProvider>
    </React.StrictMode>,
  );
}

// Load the persisted language's dictionary first so the first paint is not in uz.
void ensureDictionary(currentLang()).finally(render);
