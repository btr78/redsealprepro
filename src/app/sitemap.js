import { TRADES_SEO } from "./trades-seo";

export default function sitemap() {
  const base = "https://www.redsealprep.pro";
  const now = new Date();
  return [
    { url: base, lastModified: now, changeFrequency: "weekly", priority: 1 },
    ...TRADES_SEO.map((t) => ({ url: `${base}/${t.slug}`, lastModified: now, changeFrequency: "weekly", priority: 0.9 })),
    { url: `${base}/privacy`, lastModified: now, changeFrequency: "yearly", priority: 0.2 },
    { url: `${base}/terms`, lastModified: now, changeFrequency: "yearly", priority: 0.2 },
  ];
}
