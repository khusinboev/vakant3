import { useCallback, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, ExternalLink } from "lucide-react";

import client from "../api/client";
import BottomSheet from "../components/ui/BottomSheet";
import useToast from "../hooks/useToast";
import { clearBackInterceptor, setBackInterceptor } from "../hooks/useBackInterceptor";
import { useLang, useT } from "../i18n/useT";

interface ArticleSummary {
  id: string;
  category: string;
  title: string;
  summary: string;
  source_label: string;
}

interface ArticleDetail extends ArticleSummary {
  full_text: string;
  source_url: string;
}

interface LawsListResponse {
  categories: string[];
  articles: ArticleSummary[];
}

const ALL = "__all__";

/** The only URL schemes a link may use — mirrors `ALLOWED_HREF_SCHEMES` in
 * `webapp/routers/admin_content.py`. Anything else (`javascript:`, `data:`, a
 * relative path) is stored XSS the moment it reaches `dangerouslySetInnerHTML`. */
const ALLOWED_HREF_SCHEMES = ["http://", "https://", "tg://", "mailto:"];

/** Characters a browser skips while parsing a scheme (`java\tscript:`, NULs). */
// eslint-disable-next-line no-control-regex
const HREF_IGNORED = /[\u0000- \u007f]/g;

function isSafeHref(raw: string): boolean {
  // The server already refuses these on write; the API is still a remote input,
  // so the check is repeated here rather than assumed.
  const decoded = raw.replace(/&#(\d+);/g, (_, code: string) =>
    String.fromCharCode(Number(code)),
  );
  const collapsed = decoded.replace(HREF_IGNORED, "").toLowerCase();
  return ALLOWED_HREF_SCHEMES.some((scheme) => collapsed.startsWith(scheme));
}

function escapeAttribute(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}

/** Bot-formatting tags (<b>, <i>, <a>) are the only markup we allow through. */
function renderParagraph(text: string): string {
  return text
    .replace(/<b>(.*?)<\/b>/g, "<strong>$1</strong>")
    .replace(/<i>(.*?)<\/i>/g, "<em>$1</em>")
    .replace(/<a href="(.*?)">(.*?)<\/a>/g, (_match, href: string, label: string) =>
      isSafeHref(href)
        ? `<a href="${escapeAttribute(href)}" target="_blank" rel="noopener noreferrer" class="text-primary underline">${label}</a>`
        : // A link we will not follow still keeps its text, so the paragraph reads.
          label,
    );
}

export default function Laws() {
  const t = useT();
  const lang = useLang();
  const toast = useToast();

  const [activeCategory, setActiveCategory] = useState<string>(ALL);
  const [openId, setOpenId] = useState<string | null>(null);

  const list = useQuery<LawsListResponse>({
    queryKey: ["content", "laws", lang],
    queryFn: async () => {
      const { data } = await client.get<LawsListResponse>("/content/laws");
      return data;
    },
    staleTime: 10 * 60 * 1000,
  });

  const detail = useQuery<ArticleDetail>({
    queryKey: ["content", "laws", lang, openId],
    queryFn: async () => {
      const { data } = await client.get<ArticleDetail>(`/content/laws/${openId}`);
      return data;
    },
    enabled: Boolean(openId),
    staleTime: 10 * 60 * 1000,
  });

  useEffect(() => {
    if (detail.isError) toast.apiError(detail.error);
    // Only react to a new failure, not to a new toast identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detail.isError, detail.error]);

  const closeArticle = useCallback(() => setOpenId(null), []);

  // Telegram's BackButton closes the sheet first. The global interceptor slot
  // means we never touch show()/hide() and so never hide the route-level button.
  useEffect(() => {
    if (!openId) return;
    setBackInterceptor(() => {
      closeArticle();
      return true;
    });
    return () => clearBackInterceptor();
  }, [openId, closeArticle]);

  const data = list.data;
  const filteredArticles = !data
    ? []
    : activeCategory === ALL
      ? data.articles
      : data.articles.filter((a) => a.category === activeCategory);

  if (list.isLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (list.isError) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 px-6 text-center">
        <p className="text-sm text-muted">{t("laws.error")}</p>
        <button
          type="button"
          className="tap-target text-sm font-medium text-primary"
          onClick={() => void list.refetch()}
        >
          {t("common.retry")}
        </button>
      </div>
    );
  }

  const article = openId ? detail.data ?? null : null;

  return (
    <>
      <div className="pb-6">
        <div className="mb-4">
          <h1 className="text-xl font-bold text-text">⚖️ {t("laws.title")}</h1>
          <p className="mt-0.5 text-sm text-muted">{t("laws.subtitle")}</p>
        </div>

        {/* Category chips */}
        <div className="scrollbar-hide -mx-4 mb-4 flex gap-2 overflow-x-auto px-4 pb-2">
          {[ALL, ...(data?.categories ?? [])].map((cat) => (
            <button
              type="button"
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`tap-target flex-shrink-0 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                activeCategory === cat
                  ? "bg-primary text-primaryFg"
                  : "bg-surfaceAlt text-muted"
              }`}
            >
              {cat === ALL ? t("common.all") : cat}
            </button>
          ))}
        </div>

        {/* Article cards */}
        <div className="space-y-3">
          {filteredArticles.length === 0 && (
            <p className="card p-4 text-sm text-muted">{t("laws.empty")}</p>
          )}
          {filteredArticles.map((item) => (
            <button
              type="button"
              key={item.id}
              onClick={() => setOpenId(item.id)}
              className="card tap-target w-full p-4 text-left"
            >
              <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1">
                  <span className="mb-2 inline-block rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                    {item.category}
                  </span>
                  <h3 className="mb-1 text-sm font-semibold leading-tight text-text">{item.title}</h3>
                  <p className="text-xs text-muted line-clamp-2">{item.summary}</p>
                </div>
                <ChevronRight size={16} className="mt-1 flex-shrink-0 text-muted" />
              </div>
            </button>
          ))}
        </div>
      </div>

      <BottomSheet
        open={Boolean(openId)}
        onClose={closeArticle}
        title={article?.title ?? t("common.loading")}
        subtitle={article?.source_label}
        ariaLabel={t("laws.title")}
        footer={
          article && (
            <button
              type="button"
              onClick={() => {
                const tg = window.Telegram?.WebApp;
                if (tg?.openLink) tg.openLink(article.source_url);
                else window.open(article.source_url, "_blank", "noopener,noreferrer");
              }}
              className="tap-target flex w-full items-center justify-center gap-2 rounded-xl bg-primary py-3 text-sm font-medium text-primaryFg"
            >
              <ExternalLink size={16} />
              {t("laws.readFull")}
            </button>
          )
        }
      >
        {detail.isLoading || !article ? (
          <div className="flex h-32 items-center justify-center">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : (
          <div className="space-y-3">
            <span className="inline-block rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
              {article.category}
            </span>
            {article.full_text.split(/\n\n+/).map((para, i) => (
              <p
                key={i}
                className="whitespace-pre-line text-sm leading-relaxed text-text"
                dangerouslySetInnerHTML={{ __html: renderParagraph(para) }}
              />
            ))}
          </div>
        )}
      </BottomSheet>
    </>
  );
}
