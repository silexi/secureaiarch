import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://secureaiarch.com",
  trailingSlash: "never",
  build: { format: "file" },
  markdown: { shikiConfig: { themes: { light: "github-light", dark: "github-dark" } } },
});
