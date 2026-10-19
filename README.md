# secureaiarch.com

On-prem LLM, RAG ve agent sistemleri için yerel donanımda test edilmiş referans mimariler. Site EN/TR.

## Yapı

| Yol | Görev |
|---|---|
| `bench/` | Test aracı. Ollama'ya karşı çalışır, sadece standart kütüphane. |
| `bench/data/` | Elle etiketlenmiş sentetik girdiler. |
| `results/<pattern>.json` | Sitede görünen özet. Elle yazılmaz, `bench` üretir. |
| `results/raw/<pattern>/<model>.jsonl` | Her istek ve cevap. |
| `src/content/patterns/<slug>/{en,tr}.md` | Pattern metni. |
| `src/diagrams/` | Topoloji diyagramları (SVG, tema uyumlu). |

Sonuç dosyası olmayan pattern sitede taslak olarak görünür, `noindex` alır ve sitemap'e girmez.

## Sonuç üretmek (Mac Mini)

```sh
ollama pull qwen2.5:1.5b && ollama pull qwen2.5:3b && ollama pull qwen3:30b-a3b
BENCH_MACHINE="Mac mini" python3 -m bench run structured-output --models qwen2.5:1.5b,qwen2.5:3b,qwen3:30b-a3b
git add results && git commit -m "structured-output sonuçları" && git push
```

Push deploy'u tetikler. Mac Mini yalnızca dışarıya bağlanır (KS-1, MK-11).

## Geliştirme

```sh
npm ci
npm test        # python birim testleri + build + build kontrolleri
npm run dev
```
