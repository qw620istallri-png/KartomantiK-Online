# Inner Deserts integration

This directory extends the Beta card database with the 150 Inner Deserts cards.

- Keep stable, globally unique `id` values matching DeckomantiK exports.
- Card art uses the official `api.kartomantik.com` URLs, matching the Beta set.
- If `image` is empty, KKO automatically displays `Missing_Card_Image.png`.
- Supported imported rarities include `desert` and `desert-glitter`.

Both the browser and the game server load this file after `public/cards-data.json`.

The Desert mask, wind texture, and grain used by the rarity effect are local
copies of DeckomantiK's assets so masking also works from `file://` and on
browsers that reject cross-origin CSS masks. Official card art is served by
Kartomantik's API; only the missing-card fallback remains on DeckomantiK.
