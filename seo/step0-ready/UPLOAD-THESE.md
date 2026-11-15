# Step 0 — ready-to-upload bundle (2 minutes, no editing needed except step 3)

Everything in this folder is final. File names and locations are exactly as they must go live.

## 1. Upload the root files
Go to the `hammadportfolio` repo → **Add file → Upload files** → upload everything in `root/`:
- `robots.txt`   → serves at hammad-developer.vercel.app/robots.txt
- `sitemap.xml`  → serves at hammad-developer.vercel.app/sitemap.xml
- `og-image.png` → serves at hammad-developer.vercel.app/og-image.png

Commit the upload.

## 2. Wait for the deploy, then verify
Open both URLs — you should see text/XML, NOT a 404 page:
- https://hammad-developer.vercel.app/robots.txt
- https://hammad-developer.vercel.app/sitemap.xml

## 3. Paste the head inserts (the only editing step)
- `head-inserts/index-head-insert.html` → paste inside `<head>` of `index.html`,
  just below the existing `<meta charset>` / viewport lines.
  If an old `<title>` or meta description already exists, DELETE it first (never two titles).
- `head-inserts/hire-head-insert.html` → same, inside `<head>` of `hire.html`.

Commit, wait for deploy.

## 4. Done with Step 0
Continue with Google Search Console verification + sitemap submission + Request Indexing
(full click-by-click guide: conversation history / APPLY-CHECKLIST.md in the parent `seo/` folder).
