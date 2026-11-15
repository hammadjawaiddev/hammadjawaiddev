# SEO Audit — hammad-developer.vercel.app

**Date:** 2026-11-15 · **Site checked:** https://hammad-developer.vercel.app/ (+ `/hire.html`)
**Note:** This repo (`hammadjawaiddev`) is your GitHub profile README, not the portfolio source.
The portfolio source is `hammadjawaiddev/hammadportfolio` (per its GitHub "About" website field),
which this session's GitHub token can't open — so fixes below are supplied as drop-in files in
[`seo/`](./seo) to copy into that repo. Nothing here changes the live site until they're deployed there.

## Verdict: ~45/100 — good content & titles, but not discoverable yet

The pages themselves read well. The problem is discovery: the site is effectively invisible to
search engines right now — no sitemap, no `robots.txt`, and it does not surface in search results
for its own name/domain.

## ✅ What's already good

| Check | Result |
|---|---|
| `<title>` (home) | `Hammad Jawaid — Full-Stack Developer` — unique, keyword-led, good length (~37 chars) |
| `<title>` (hire) | `Hire Hammad Jawaid — Full-Stack Developer` — unique per page ✅ |
| Content depth | Real, keyword-relevant copy: full-stack, HTML/CSS/JS, PHP, Node.js, MySQL, MongoDB, Karachi |
| Image alts | Project screenshots have descriptive alt text (`PhysioSync homepage`, …) |
| Internal linking | Home ↔ `/hire.html`, CV PDF, GitHub/LinkedIn all linked |
| HTTPS | Served over HTTPS on Vercel ✅ |
| CV PDF | Has a proper document title (`Hammad Jawaid - Full-Stack Developer CV`) |

## ❌ Critical (fix first)

1. **No `sitemap.xml`** — `GET /sitemap.xml` returns **404**. → drop in [`seo/sitemap.xml`](./seo/sitemap.xml)
2. **No `robots.txt`** — `GET /robots.txt` returns **404**. → drop in [`seo/robots.txt`](./seo/robots.txt)
3. **Not indexed / not ranking for its own name** — `site:hammad-developer.vercel.app` returns **0 results**;
   searching `Hammad Jawaid Full-Stack Developer Karachi` and `"Hammad Jawaid" developer` does **not**
   surface the portfolio (Linktree and other people do). After adding sitemap/robots:
   - Add the site to **Google Search Console** (URL-prefix property for `https://hammad-developer.vercel.app/`),
     submit the sitemap, and use *Request Indexing* for `/` and `/hire.html`.
   - Add the same URL to Bing Webmaster Tools (can import from Search Console).
   - Reason could also be a `noindex` tag or that the site is simply new with no backlinks — Search Console's
     URL Inspection tool will tell you which in one click. *(I could not inspect the raw `<head>` HTML:
     the portfolio repo isn't accessible to this session's GitHub token, and the connected Vercel token
     returned "Access denied" for project/deployment reads — worth checking its scopes.)*

## ⚠️ Important

4. **H1 doesn't carry your target keyword, and heading text runs together.**
   Crawler-extracted text shows the H1 as `HAMMADJAWAID` and H2s like
   `Ibuildmoderninterfacesandpowerfulbackends.` / `HI,I'MHAMMAD` — the per-word/letter `<span>`
   animation markup concatenates words for text-only crawlers (and screen readers).
   - Make the H1 literally `Hammad Jawaid — Full-Stack Developer` in HTML (style/animation can stay visual-only).
   - Keep real spaces in heading text nodes; if you split words into spans for animation, add spaces between spans or an `aria-label` on the heading with visually-hidden plain text.
   - Several H2s are full sentences; add keyword-bearing section headings (`Selected Work`, `Services`, `About` are fine — keep those, demote sentence-style lines to `<p>` where they're not real sections).
5. **Canonical / Open Graph / Twitter cards / structured data — unverified, likely missing.**
   No evidence of them from the crawl. Without OG tags, LinkedIn/WhatsApp shares show no title/image preview —
   important since you share this link for hiring. → paste [`seo/head-snippet.html`](./seo/head-snippet.html)
   into `<head>` (includes canonical, meta description, OG/Twitter, and `Person` JSON-LD). You'll need a
   1200×630 share image at `/og-image.png` — currently `GET /og-image.png` is **404**.
6. **Only 2 indexable pages.** Fine for a portfolio, but one keyword page (e.g. `/services` or project
   case-study pages) would give Google more to rank. Your hire-page FAQ content is a good candidate for
   `FAQPage` schema later.
7. **One outbound project link is plain HTTP:** `http://ctrlzone.infinityfreeapp.com/` (linked twice, home + hire).
   Use HTTPS if InfinityFree supports it; HTTP links look untrustworthy and can trigger mixed-content warnings.

## ℹ️ Minor

8. `karachi-skyline.png` is extracted with **empty alt text** — give it `alt="Karachi skyline"` (or keep empty only if purely decorative).
9. Favicon couldn't be verified from here (binary response) — confirm a favicon + `theme-color` exist in `<head>`; the snippet includes placeholders.
10. Anchor text is mostly good (`Hire Me`, `Résumé`); avoid adding any "click here" style links.
11. **GitHub-side discoverability:** the `hammadportfolio` repo has an empty description. Add one
    ("Portfolio of Hammad Jawaid — Full-Stack Developer (HTML, CSS, JavaScript, PHP, Node.js, MySQL, MongoDB)")
    and topics (`portfolio`, `full-stack`, `javascript`, `php`, `nodejs`). Your profile README itself is already
    well-optimised (descriptive banner alt, keyword-rich About, project table).
12. **Not tested:** Core Web Vitals / Lighthouse (no browser tooling in this environment) and raw `<head>`
    contents (see note in #3). Run PageSpeed Insights once after the fixes.

## Priority order

1. Copy `seo/robots.txt` + `seo/sitemap.xml` into the portfolio repo root → deploy.
2. Paste `seo/head-snippet.html` (home) and `seo/hire-head-snippet.html` (hire) into each page's `<head>`, upload `seo/og-image.png` (generated, 1200×630) to the site root.
3. Fix the H1 text + heading spacing (#4).
4. Search Console + Bing Webmaster Tools: verify, submit sitemap, request indexing.
5. HTTPS for CTRL ZONE link; Karachi image alt; fill in the GitHub repo description/topics.

## Done in this repo (2026-11-15, round 2)

- ✅ Profile README rebuilt for search: real H1 (`Hammad Jawaid — Full-Stack Developer in Karachi, Pakistan`),
  keyword-rich intro, **Web Development Services** section, descriptive project link anchors, and an
  **FAQ section** mirroring the hire page (the questions people actually search).
- ✅ `seo/sitemap.xml` upgraded to an **image sitemap** (all 5 project screenshots + Karachi skyline, with titles).
- ✅ `seo/head-snippet.html` upgraded: `ProfilePage` + `Person` + `WebSite` JSON-LD graph, geo tags,
  `max-image-preview:large`, longer keyword-led title.
- ✅ New `seo/hire-head-snippet.html`: hire-page title/meta/canonical + **FAQPage** and **ProfessionalService** schema matching the visible FAQ.
- ✅ New `seo/og-image.png` — ready-made 1200×630 social share image.
- ✅ New `seo/APPLY-CHECKLIST.md` — 15-minute step-by-step to apply everything + Search Console/Bing submission.
- ⛔ Repo description/topics could not be set from here (GitHub token: "Resource not accessible by
  integration", 403) — manual values are in the checklist, step 6.

**Supabase** is connected but switched off for this conversation — it isn't needed for SEO, so no action there.
