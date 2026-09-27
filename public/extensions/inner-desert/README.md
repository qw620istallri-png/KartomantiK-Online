# Inner Deserts integration slot

This directory is intentionally isolated from the Beta card database.

- Replace the 150 placeholder records in `cards.json` as final card data arrives.
- Keep stable, globally unique `id` values matching DeckomantiK exports.
- Prefer absolute GitHub Pages `image` URLs so each client downloads art
  directly and Render never proxies card images.
- If `image` is empty, KKO automatically displays `Missing_Card_Image.png`.
- Supported imported rarities include `desert` and `desert-glitter`.

The application loads this file after `public/cards-data.json`, so Beta remains unchanged while the extension is being prepared.

The Desert mask, wind texture, and grain used by the rarity effect are local
copies of DeckomantiK's assets so masking also works from `file://` and on
browsers that reject cross-origin CSS masks. Card art and the missing-card
fallback remain hosted on the DeckomantiK GitHub Pages site.
