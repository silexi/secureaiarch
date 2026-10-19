import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

const patterns = defineCollection({
  loader: glob({ pattern: "*/*.md", base: "./src/content/patterns" }),
  schema: z.object({
    title: z.string(),
    summary: z.string(),
    thesis: z.string(),
    order: z.number(),
    lab: z.string().url(),
    results: z.string(),
  }),
});

export const collections = { patterns };
