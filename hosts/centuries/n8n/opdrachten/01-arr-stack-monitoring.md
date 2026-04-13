# Opdracht 01 — Arr Stack Monitoring

## Doel
Bouw een n8n workflow die periodiek je arr stack en Plex controleert en je via Telegram waarschuwt als een service down is.

Als je deze opdracht afgerond hebt, heb je de basis gelegd voor een AI sysadmin die later automatisch kan ingrijpen.

---

## Wat je leert
- Schedule Trigger gebruiken
- HTTP Request node configureren
- IF node gebruiken voor conditionele logica
- Merge node gebruiken om meerdere checks samen te voegen
- Telegram notificaties versturen
- Error handling in n8n

---

## Services om te monitoren

| Service | URL | Health endpoint |
|---|---|---|
| Seerr | `https://verzoekjes.sqrd.link` | `/api/v1/status` |
| Sonarr | `https://sonarr.sqrd.link` | `/api/v3/health` (API key vereist) |
| Radarr | `https://radarr.sqrd.link` | `/api/v3/health` (API key vereist) |
| Plex | `http://plex.sqrd.link:32400` | `/identity` |

---

## Opdracht stappen

### Stap 1 — Schedule Trigger
Maak een nieuwe workflow aan in n8n met een **Schedule Trigger**.
- Interval: elke 5 minuten

**Tip:** De Schedule Trigger vind je onder `Trigger nodes`. Dit is het startpunt van je workflow — hij draait automatisch zonder dat jij iets hoeft te doen.

---

### Stap 2 — HTTP checks
Voeg voor elke service een **HTTP Request** node toe.

Configureer elke node:
- Method: `GET`
- URL: de health endpoint van de service
- Voor Sonarr en Radarr: voeg een header toe `X-Api-Key: jouw_api_key`
- Zet **"Continue On Fail"** aan — anders stopt de hele workflow als één service down is

**Tip:** API keys vind je in de instellingen van elke service onder `Settings → General`.

**Leervraag:** Waarom is "Continue On Fail" hier belangrijk?

---

### Stap 3 — Status bepalen per service
Voeg na elke HTTP Request een **IF** node toe die controleert of de service bereikbaar was.

Voorwaarde:
- Voor Seerr: check of `{{ $json.version }}` bestaat
- Voor Sonarr/Radarr: check of de HTTP status `200` is
- Voor Plex: check of `{{ $json.MediaContainer }}` bestaat

De IF node heeft twee outputs: `true` (service is up) en `false` (service is down).

**Leervraag:** Wat is het verschil tussen een HTTP 200 response en een lege response body?

---

### Stap 4 — Samenvoegen
Gebruik een **Merge** node om alle "down" outputs samen te voegen tot één lijst.

- Mode: `Combine` → `Append`
- Verbind alle `false` outputs van je IF nodes met deze Merge node

**Tip:** Als de Merge node geen input krijgt (alles is up), voert hij niets uit en stopt de workflow netjes — dat is precies wat je wilt.

---

### Stap 5 — Telegram notificatie
Voeg een **Telegram** node toe na de Merge node.

- Operation: `Send Message`
- Chat ID: jouw Telegram chat ID
- Message: maak een duidelijk bericht met welke services down zijn

Voorbeeld bericht:
```
🚨 Service alert!

De volgende services zijn niet bereikbaar:
{{ $json.service }}

Tijdstip: {{ $now.toISO() }}
```

**Tip:** Je Telegram bot token en chat ID sla je op als **Credentials** in n8n, niet als plain text in de workflow.

---

### Stap 6 — Testen
Test elke node apart met de **"Execute node"** knop. Probeer ook:
1. Stop een service tijdelijk en kijk of de alert werkt
2. Start de service weer en kijk of de volgende run geen alert stuurt

---

## Klaar?

Als de basis werkt, zijn dit goede uitbreidingen om te proberen:

- [ ] Voeg een **cooldown** toe zodat je niet elke 5 minuten een alert krijgt voor dezelfde service
- [ ] Stuur ook een "service is weer up" notificatie als een service hersteld is
- [ ] Sla de status op in n8n's ingebouwde **Static Data** zodat je de vorige status kunt vergelijken met de huidige
- [ ] Voeg Plex toe via de echte Plex API in plaats van alleen `/identity`

---

## Hints bij problemen

**HTTP Request faalt meteen:**
Check of de service bereikbaar is vanuit je n8n container. n8n draait op `centuries.sqrd.link` en moet via het interne netwerk bij `*.sqrd.link` kunnen.

**Telegram stuurt geen bericht:**
Check of je de bot hebt gestart in Telegram (stuur `/start` naar je bot) en of je chat ID correct is. Gebruik [@userinfobot](https://t.me/userinfobot) om je chat ID op te vragen.

**Merge node doet niks:**
Dat is correct gedrag als alle services up zijn — de `false` outputs zijn dan leeg en de Merge node heeft geen data om samen te voegen.

---

## Referentie

- [n8n HTTP Request node docs](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.httprequest/)
- [n8n Telegram node docs](https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.telegram/)
- [n8n Schedule Trigger docs](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.scheduletrigger/)
- [Sonarr API docs](https://sonarr.tv/docs/api/)
- [Radarr API docs](https://radarr.video/docs/api/)
