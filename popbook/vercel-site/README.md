# The Fox of the First Snow (pop-up storybook)

A static site: no build step and no server code. Three.js and the fonts load from public CDNs.

## Put it on Vercel

1. Unzip this folder.
2. Go to vercel.com > Add New > Project, and drag the unzipped folder in
   (or run `npx vercel` inside the folder and accept the defaults).
3. Framework preset: **Other**. Build command: none. Output directory: `.` (the folder itself).
4. Deploy. Your book is at `https://<your-project>.vercel.app/`, and the Alice demo at `/alice/`.

## How it behaves on your own site

- **Make your own:** builds a child's book; the link is copied automatically and opens that
  child's book on any phone.
- **English / Urdu:** button at the top, or Aa > Language.
- **Family voice:** on your own site the microphone works, so each page has a Record button.
  Recordings are saved **on the device that recorded them** (in the browser's storage). To let a
  child on another phone hear them, the voices need online storage (for example Vercel Blob or
  Supabase); that is the next step to add.
