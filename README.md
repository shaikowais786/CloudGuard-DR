# CloudGuard DR

Dark, responsive AWS disaster recovery readiness dashboard built with React 19, Vite, Tailwind CSS, React Router, Framer Motion, Recharts, Lucide, and React Hook Form.

## Run locally

```sh
npm install
npm run dev
```

## Frontend demo

This project contains UI and mock AWS inventory data only. It does not connect to AWS or send credentials anywhere. The scanner form and scan progress are local demonstrations; use a backend integration and short-lived, read-only role credentials before connecting a real account.

## Structure

- `src/app` — route shell and page views
- `src/components` — shared cards, headings, status chips, progress rings, and charts
- `src/data.js` — realistic sample resources, findings, readiness pillars, and scan history
- `src/styles.css` — responsive dark dashboard system
