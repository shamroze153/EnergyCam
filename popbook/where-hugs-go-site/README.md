# Where Do Hugs Go?

An interactive 3D pop-up storybook where the child is the hero. Static site: plain HTML,
no build step and no server code. Three.js and the fonts load from public CDNs.

- `/` Where Do Hugs Go? (English, family voice)

## 1. Put it on GitHub

1. Go to github.com, click **New repository**, give it a name (for example `where-hugs-go`),
   keep it Public or Private, and click **Create repository**.
2. On the new repository page click **uploading an existing file**.
3. Drag in **everything inside this folder** (`index.html`, `favicon.svg`, `vercel.json`, `README.md`) and click **Commit changes**.

Or with git:

```
git init
git add .
git commit -m "First version"
git branch -M main
git remote add origin https://github.com/<you>/where-hugs-go.git
git push -u origin main
```

## 2. Deploy from GitHub to Vercel

1. Go to vercel.com and sign in with GitHub.
2. Click **Add New > Project**, find `where-hugs-go`, and click **Import**.
3. Framework Preset: **Other**. Leave Build Command and Output Directory empty.
4. Click **Deploy**. In about a minute the book is live at `https://<project>.vercel.app/`.

Every time you push a change to GitHub, Vercel publishes it again by itself.

## 3. After the first deploy

- **Your own domain:** in Vercel open the project > Settings > Domains and add it.

## How it works on your site

- **English / Urdu:** button at the top, or Aa > Language.
- **Family voice:** on your own site the microphone works, so each page has a Record button.
  Recordings are saved on the device that recorded them (in the browser's storage). For a
  child on another phone to hear them, the voices need online storage (for example
  Vercel Blob or Supabase); that is the next thing to add.
