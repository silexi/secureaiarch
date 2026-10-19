import { getCollection } from "astro:content";
import { resultsFor } from "../results";
export async function GET() {
  const base = "https://secureaiarch.com";
  const urls = ["/en", "/tr", "/en/method", "/tr/method"];
  for (const e of await getCollection("patterns")) {
    if (!resultsFor(e.data.results)) continue; // taslaklar indekslenmez
    const [slug, lang] = e.id.split("/");
    urls.push(`/${lang}/patterns/${slug}`);
  }
  return new Response(urls.map((u) => base + u).join("\n") + "\n", { headers: { "Content-Type": "text/plain" } });
}
