# Deployment

Everything runs on free tiers: Supabase (database), Render (API), Vercel (web app). Deploy in that order,
because each step needs a value from the one before.

## Environment variables

| Variable | Where it is set | Value |
|---|---|---|
| `DATABASE_URL` | Render | Supabase **Session pooler** connection string |
| `JWT_SECRET` | Render | long random string (the blueprint generates one) |
| `CORS_ORIGINS` | Render | the Vercel URL, no trailing slash |
| `CORS_ORIGIN_REGEX` | Render | `https://.*\.vercel\.app` (also allows Vercel preview URLs) |
| `ORG_TIMEZONE` | Render | IANA zone for shift times, e.g. `UTC` or `Asia/Kolkata` |
| `SEED_ON_STARTUP` | Render | `true` fills an *empty* database with demo data |
| `NEXT_PUBLIC_API_URL` | Vercel | the Render URL, no trailing slash and no `/api` |

For local development the same names go in `backend/.env` and `frontend/.env.local` (both git-ignored;
`.env.example` files show the shape).

## 1. Supabase (database)

1. Create a project at supabase.com and save the database password.
2. Open **Project Settings > Database > Connection string**, choose **Session pooler**, copy the URI and
   replace `[YOUR-PASSWORD]`. Use the pooler, not the "Direct connection": direct is IPv6-only and Render's
   free tier cannot reach it.
3. Nothing else to do. The API creates its tables, the append-only triggers and row level security on
   startup.

## 2. Render (API)

1. New > Blueprint, pick the GitHub repo. Render reads `render.yaml`.
2. Fill the prompted values: `DATABASE_URL` (from step 1) and `CORS_ORIGINS` (use a placeholder such as
   `http://localhost:3000` for now, update it after step 3).
3. Deploy. The first start also seeds the demo data. Check `https://<service>.onrender.com/health`.

## 3. Vercel (web app)

1. Add New > Project, import the repo, set **Root Directory** to `frontend`.
2. Add `NEXT_PUBLIC_API_URL` = the Render URL. Deploy.
3. Back in Render, set `CORS_ORIGINS` to the Vercel URL and let the service redeploy.

## Notes

- Render's free service sleeps after ~15 minutes idle; the first request can take up to a minute. A free
  UptimeRobot monitor on `/health` every 5 minutes keeps it awake for a demo.
- The seed only runs when the `users` table is empty, so redeploys never duplicate or reset data.
- To re-seed from your machine instead, set `DATABASE_URL` in `backend/.env` and run `python -m app.seed`.
