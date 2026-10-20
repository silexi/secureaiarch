import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

const patterns = defineCollection({
  loader: glob({ pattern: "*/*.md", base: "./src/content/patterns" }),
  schema: z.object({
    title: z.string(),
    summary: z.string(),
    thesis: z.string(),
    order: z.number(),
    lab: z.string().url().optional(),
    // Extra setup before the bench runs (for example a database), shown in the reproduce block.
    setup: z.array(z.string()).optional(),
    results: z.string(),
  }),
});

export const collections = { patterns };
