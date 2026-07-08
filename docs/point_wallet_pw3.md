# Point Wallet PW-3

PW-3 adds seats.aero watch snapshots and point-expiry dashboard alerts.

## seats.aero

- Uses the seats.aero Partner API only.
- Reads `SEATS_AERO_API_KEY` from the backend environment.
- Uses Cached Search (`GET https://seats.aero/partnerapi/search`) for Pro-compatible route/date/cabin searches.
- Does not use Live Search, scraping, booking, or credential storage.

Mac mini cron example:

```cron
30 */6 * * * cd /Users/kaichanghuang/Server/phistyle-capital-os && /usr/local/bin/docker-compose exec -T backend python -m backend.app.commands.fetch_award_watches >> /tmp/phistyle_award_watches.log 2>&1
```

## Expiry Alerts

Expiry alerts scan account expiry dates at 90 / 60 / 30 / 7 day thresholds.
Notifications are dashboard-only in this phase.

Mac mini cron example:

```cron
15 8 * * * cd /Users/kaichanghuang/Server/phistyle-capital-os && /usr/local/bin/docker-compose exec -T backend python -m backend.app.commands.scan_expiry_alerts >> /tmp/phistyle_expiry_alerts.log 2>&1
```
