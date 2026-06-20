# Sicherheit

## Auth und Rollen

- Admin-Rollen: `superadmin`, `support`
- Session-basiertes Admin-Login
- Session-Timeout ueber `SESSION_TIMEOUT_MINUTES`

## Brute-Force-Schutz

- Admin-Login:
- Zaehlt Fehlversuche pro Account
- Sperrt Account fuer `BRUTE_FORCE_LOCKOUT_MINUTES` nach `BRUTE_FORCE_MAX_ATTEMPTS`

- Lizenz-Login:
- Zaehlt Fehlversuche pro IP + E-Mail
- Blockiert bei Ueberschreitung (429)

## CSRF-Schutz

- Session-basierte CSRF-Tokens
- Alle sensitiven HTML-POST-Flows validieren CSRF

## Passwortsicherheit

- Komplexitaetsregel:
- mind. 10 Zeichen
- Gross-/Kleinbuchstaben
- Zahl
- Sonderzeichen
- Hashing mit bcrypt
- Legacy-SHA256 kann beim ersten erfolgreichen Login auf bcrypt migriert werden

## PayPal-Sicherheit

- Webhook-Signatur wird serverseitig verifiziert
- Untrusted Signaturen werden mit 400 abgelehnt

## Header/Proxy-Sicherheit

- `X-Forwarded-For` wird nur akzeptiert, wenn der direkte Client als trusted proxy gilt

## Session-Cookies

- `same_site=lax`
- `SESSION_COOKIE_SECURE` erzwungen oder automatisch aktiv in Produktion
