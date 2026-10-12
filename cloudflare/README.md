# Cloudflare migration

Target resources:

- Worker: `verum-competitions`
- D1: `verum-competitions-db`

The Telegram webhook must remain on the previous deployment until the D1 schema,
application data, API routes and secrets have been migrated and verified.
