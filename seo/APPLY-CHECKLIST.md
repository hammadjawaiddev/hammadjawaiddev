# Apply this SEO kit to hammad-developer.vercel.app (≈15 minutes)

The live portfolio source is the `hammadportfolio` repo — that's where these files go.

## 1. Drop files into the portfolio repo root
- [ ] `seo/robots.txt` → `/robots.txt`
- [ ] `seo/sitemap.xml` → `/sitemap.xml`
- [ ] `seo/og-image.png` → `/og-image.png` (1200×630 share image, already generated)

## 2. Paste the head snippets
- [ ] `seo/head-snippet.html` → inside `<head>` of `index.html` (replace existing title/description if duplicated — never ship two `<title>` or two meta descriptions)
- [ ] `seo/hire-head-snippet.html` → inside `<head>` of `hire.html` (same de-dup rule)
- [ ] Fix the H1: real spaced text `Hammad Jawaid — Full-Stack Developer`, animated spans `aria-hidden` + `aria-label` on the heading
- [ ] Give `karachi-skyline.png` alt text: `Karachi skyline, Pakistan`
- [ ] Change the CTRL ZONE link to `https://ctrlzone.infinityfreeapp.com/` if HTTPS works there

## 3. Deploy, then verify live
- [ ] Open https://hammad-developer.vercel.app/robots.txt — should show the sitemap line
- [ ] Open https://hammad-developer.vercel.app/sitemap.xml — should list both pages
- [ ] Test share preview: https://www.opengraph.xyz/ (or paste the link into a WhatsApp/LinkedIn draft)

## 4. Get indexed (no way around this step — this is what actually ranks you)
- [ ] Google Search Console → Add property → URL prefix `https://hammad-developer.vercel.app/`
- [ ] Sitemaps → submit `sitemap.xml`
- [ ] URL Inspection → `/` → Request Indexing; repeat for `/hire.html`
- [ ] Bing Webmaster Tools → import from Search Console (gets you Bing + DuckDuckGo)

## 5. Free backlinks (biggest ranking lever after indexing)
- [ ] GitHub profile README (done — links to portfolio, hire page, CV)
- [ ] LinkedIn profile → Featured/Contact info → portfolio URL
- [ ] Linktree (you already rank there for your name — make the portfolio the first/top link)
- [ ] Portfolio URL in your CV PDF header (already there) and email signature

## 6. Repo metadata (GitHub search SEO)
Set on **both** this profile repo and `hammadportfolio` — Settings → About (gear icon):
- Description: `Hammad Jawaid — Full-Stack Developer in Karachi, Pakistan | HTML, CSS, JavaScript, React, PHP, Node.js, MySQL, MongoDB | Portfolio & hire page`
- Website: `https://hammad-developer.vercel.app/`
- Topics: `full-stack-developer`, `portfolio`, `web-developer`, `javascript`, `react`, `php`, `nodejs`, `mysql`, `mongodb`, `karachi`, `freelancer`
