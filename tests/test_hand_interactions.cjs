const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const publicRoot = path.join(root, 'public');
const artifacts = path.join(root, '_A_NE_PAS_UPLOADER/tests/artifacts/hand-interactions');
const mime = { '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.html': 'text/html', '.webp': 'image/webp', '.png': 'image/png', '.svg': 'image/svg+xml' };

(async () => {
  fs.mkdirSync(artifacts, { recursive: true });
  const server = http.createServer((request, response) => {
    const relative = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
    const file = path.resolve(publicRoot, relative === '/' ? 'index.html' : relative.slice(1));
    if (!file.startsWith(publicRoot + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) return response.writeHead(404).end();
    response.writeHead(200, { 'Content-Type': mime[path.extname(file)] || 'application/octet-stream' });
    fs.createReadStream(file).pipe(response);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const errors = [];
  try {
    for (const touch of [false, true]) {
      const viewport = touch ? { width: 844, height: 390 } : { width: 1440, height: 1000 };
      const page = await browser.newPage({ viewport, hasTouch: touch, reducedMotion: 'reduce' });
      page.on('pageerror', error => errors.push(error.message));
      await page.goto(`http://127.0.0.1:${server.address().port}/`);
      await page.waitForFunction(() => cardsById.size === 450);
      await page.evaluate(() => {
        window.__sent = []; send = payload => window.__sent.push(payload);
        window.__drops = [];
        const resolveCostDrop = resolveRulesBoardCardDrop;
        resolveRulesBoardCardDrop = (ctx, target) => { __drops.push({ stage: pendingRulesBoardFlow?.stage, ctx, target: target?.id || target?.tagName }); return resolveCostDrop(ctx, target); };
        myPlayerId = 'p1'; isObserver = false;
        const manifestations = [...cardsById.values()].filter(card => card.type === 'manifestation' && card.power === 1 && card.colorKey === 'phlegmatic').slice(0, 2);
        const will = [...cardsById.values()].find(card => card.type === 'ephemeral_will');
        const grimoire = [...cardsById.values()].find(card => card.name === 'Grimoire');
        window.__cards = [...manifestations.map(card => card.id), will.id];
        window.__grimoire = grimoire.id;
        const player = (id, hand) => ({ id, name: id, seat: id === 'p1' ? 0 : 1, color: id === 'p1' ? '#3fc9a8' : '#d3654a', score: 0, sideboard: [], cardRarities: {}, zones: Object.fromEntries(['hand','deck','graveyard','exile','receptacle'].map(zone => [zone, { cards: zone === 'hand' ? hand : [], count: zone === 'hand' ? hand.length : 0 }])) });
        latestState = { mode: 'casual', status: 'active', ended: false, players: { p1: player('p1', __cards), p2: player('p2', []) }, battlefield: [], tokens: [], strokes: [], recentLog: [], phaseTracker: { enabled: true, advanced: true, index: ADVANCED_PHASES.findIndex(phase => phase.id === 'end_actions'), turn: 2, passedPlayerIds: [] }, rulesEngine: { enabled: true, readyPlayerIds: ['p1','p2'], priorityPlayerId: 'p1', priorityPasses: [], actionStack: [], ongoingEffects: [], playPermissions: [], pendingChoice: null, firstManifestationComplete: true } };
        window.__choiceSequence = 0;
        window.__seedChoice = (count = 1, upTo = false) => {
          closeRulesBoardFlow();
          latestState.rulesEngine.pendingChoice = { id: `grimoire-choice-${++__choiceSequence}`, kind: 'discard_from_hand', playerId: 'p1', sourceCardId: __grimoire, count, upTo, requireTypes: ['ephemeral_will','persistent_will'], destination: 'attached' };
          renderAll(); __sent.length = 0;
        };
        window.__seedPayment = (kind = 'stack_counter_payment') => {
          closeRulesBoardFlow();
          latestState.rulesEngine.pendingChoice = { id: 'payment-choice', kind, playerId: 'p1', sourceCardId: __grimoire, targetCardId: __cards[2], payment: '{G}{G}' };
          renderAll(); __sent.length = 0;
        };
        window.__seedAction = stage => {
          closeRulesBoardFlow(); latestState.rulesEngine.pendingChoice = null;
          const source = { cardId: __cards[2], zone: 'hand', handIndex: 2 };
          const draft = buildRulesActionDraft(source);
          if (stage === 'cost_card') draft.encodedAbility = { ...draft.encodedAbility, additionalCost: 'reveal_exile_hand_manifestation' };
          if (stage === 'extra_essence') {
            draft.optionalExtraEssenceMax = 0;
            draft.extraTributeCards = __cards.slice(0,2).map((cardId,index) => ({ cardId, index, power: 1 }));
          }
          pendingRulesBoardFlow = { mode: 'action', source, draft, selectedPaymentIndexes: new Set(), extraTributeIndexes: new Set(), stage };
          renderAll(); __sent.length = 0;
        };
        document.querySelector('#joinScreen').classList.add('hidden');
        document.querySelector('#gameScreen').classList.remove('hidden');
        window.uiBeta.setEnabled(true);
        __seedChoice();
      });
      await page.screenshot({ path: path.join(artifacts, `grimoire-${viewport.width}.png`) });
      const layers = await page.evaluate(() => {
        const panel = document.querySelector('#rulesChoicePanel').getBoundingClientRect();
        const card = document.querySelector('[data-hand-index="2"]').getBoundingClientRect();
        const x = Math.min(innerWidth - 1, Math.max(0, card.left + card.width / 2)), y = Math.min(innerHeight - 8, card.top + card.height / 2);
        return { bottom: panel.bottom, height: innerHeight, handHit: Boolean(document.elementFromPoint(x, y)?.closest('#myHandTray')) };
      });
      assert.ok(Math.abs(layers.bottom - layers.height) < 1, `Backdrop must reach the bottom: ${JSON.stringify(layers)}`);
      assert.ok(layers.handHit, 'The hand must be above the full-height backdrop');
      const cardPoint = async index => page.locator(typeof index === 'number' ? `#myHandTray [data-hand-index="${index}"]` : index).evaluate(el => {
        const r = el.getBoundingClientRect();
        for (const fractionX of [.15, .3, .5, .7]) for (const fractionY of [.2, .35, .5, .7]) {
          const point = { x: r.left + r.width * fractionX, y: Math.min(innerHeight - 12, r.top + r.height * fractionY) };
          if (document.elementFromPoint(point.x, point.y)?.closest('[data-hand-card],[data-ghost-card],[data-suspended-card],[data-rules-cost-card],[data-extra-tribute]') === el) return point;
        }
        throw new Error('No exposed part of hand card ' + el.dataset.handIndex);
      });
      const tap = async index => {
        const point = await cardPoint(index);
        if (touch) await page.touchscreen.tap(point.x, point.y); else await page.mouse.click(point.x, point.y);
      };
      const cdp = touch ? await page.context().newCDPSession(page) : null;
      const drag = async (index, target, cancel = false) => {
        const start = await cardPoint(index);
        if (touch) {
          await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ ...start, id: 1 }] });
          for (let step = 1; step <= 10; step++) await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: start.x + (target.x - start.x) * step / 10, y: start.y + (target.y - start.y) * step / 10, id: 1 }] });
          await cdp.send('Input.dispatchTouchEvent', { type: cancel ? 'touchCancel' : 'touchEnd', touchPoints: [] });
        } else {
          await page.mouse.move(start.x, start.y); await page.mouse.down();
          await page.mouse.move(target.x, target.y, { steps: 10 });
          if (cancel) await page.evaluate(() => window.dispatchEvent(new PointerEvent('pointercancel', { pointerId: 1 })));
          await page.mouse.up();
        }
      };
      const targetPoint = selector => page.locator(selector).evaluate(el => { const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; });
      const closeInspect = () => page.evaluate(() => document.querySelector('#inspectCloseBtn').click());

      // Grimoire, exact and multiple selections: taps inspect without selecting.
      await tap(2);
      assert.equal(await page.evaluate(() => __sent.length), 0);
      assert.equal(await page.locator('#inspectPanel').evaluate(el => el.classList.contains('hidden')), false);
      await closeInspect();
      await drag(2, await targetPoint('#rulesChoicePanel .rules-choice-source'), true);
      assert.equal(await page.evaluate(() => __sent.length), 0, 'Cancelling a drag must not choose a card');
      await drag(2, await targetPoint('#rulesChoicePanel .rules-choice-source'));
      assert.deepEqual(await page.evaluate(() => __sent.map(message => message.type)), ['resolve_rules_choice']);
      await page.evaluate(() => { __seedChoice(2, true); latestState.rulesEngine.pendingChoice.requireTypes = []; renderAll(); });
      await tap(0); await closeInspect();
      assert.equal(await page.evaluate(() => rulesHandDropSelected(rulesHandDropChoice()).length), 0);
      await drag(0, await targetPoint('#rulesChoicePanel .rules-choice-source'));
      await drag(1, await targetPoint('#rulesChoicePanel .rules-choice-source'));
      assert.equal(await page.evaluate(() => rulesHandDropSelected(rulesHandDropChoice()).length), 2);
      await page.locator('#rulesDiscardConfirm').click();
      assert.equal(await page.evaluate(() => __sent.at(-1).cardIds.length), 2);

      // All mandatory/conditional Tribute windows use the same real drop path.
      for (const kind of ['stack_counter_payment','effect_memory_payment','effect_payment','immediate_effect_payment']) {
        await page.evaluate(kind => __seedPayment(kind), kind);
        await tap(0); await closeInspect();
        assert.equal(await page.evaluate(() => pendingRulesBoardFlow.selectedPaymentIndexes.size), 0, kind);
        await drag(0, { x: 6, y: 6 });
        assert.equal(await page.evaluate(() => pendingRulesBoardFlow.selectedPaymentIndexes.size), 0, 'A drop outside the cost target must do nothing');
        await drag(0, await targetPoint('#rulesFloatingCardImg'), true);
        assert.equal(await page.evaluate(() => pendingRulesBoardFlow.selectedPaymentIndexes.size), 0, 'Cancelled payment');
        await drag(0, await targetPoint('#rulesFloatingCardImg'));
        assert.equal(await page.evaluate(() => pendingRulesBoardFlow.selectedPaymentIndexes.size), 1, kind);
        await tap(1); await closeInspect();
        assert.equal(await page.evaluate(() => pendingRulesBoardFlow.selectedPaymentIndexes.size), 1, 'A tap must not finish paying');
        await drag(1, await targetPoint('#rulesFloatingCardImg'));
        assert.equal(await page.locator('#rulesFlowPayBtn').isEnabled(), true);
        await page.locator('#rulesFlowPayBtn').click();
        assert.equal(await page.evaluate(() => __sent.at(-1).type), 'resolve_rules_choice');
      }
      await page.evaluate(() => __seedAction('cost_card'));
      await tap(0); await closeInspect();
      assert.equal(await page.evaluate(() => pendingRulesBoardFlow.costCardId), undefined);
      assert.equal(await page.locator('[data-rules-cost-card]').count(), 0);
      await drag(0, await targetPoint('#rulesFloatingCardImg'));
      await page.waitForFunction(() => __sent.some(message => message.costCardId === __cards[0]));

      await page.evaluate(() => __seedAction('extra_essence'));
      await tap(0); await closeInspect();
      assert.equal(await page.evaluate(() => pendingRulesBoardFlow.extraTributeIndexes.size), 0);
      await page.screenshot({ path: path.join(artifacts, `extra-cost-${viewport.width}.png`) });
      await drag(0, await targetPoint('#rulesFloatingCardImg'));
      assert.equal(await page.evaluate(() => pendingRulesBoardFlow.extraTributeIndexes.size), 1, JSON.stringify(await page.evaluate(() => __drops.slice(-3))));

      // Non-hand Tribute sources (Limbo) use draggable ghost cards too.
      await page.evaluate(() => {
        __seedPayment();
        latestState.players.p1.zones.graveyard.cards = [__cards[0]];
        pendingRulesBoardFlow.draft.manifestations.push({ cardId: __cards[0], power: 1, temperaments: ['phlegmatic'], zone: 'graveyard', selectionKey: 'graveyard:test' });
        renderRulesBoardFlow(); __sent.length = 0;
      });
      const paymentGhost = '#myHandTray [data-ghost-zone="payment"]';
      await tap(paymentGhost); await closeInspect();
      assert.equal(await page.evaluate(() => pendingRulesBoardFlow.selectedPaymentIndexes.size), 0);
      await drag(paymentGhost, await targetPoint('#rulesFloatingCardImg'));
      assert.equal(await page.evaluate(() => pendingRulesBoardFlow.selectedPaymentIndexes.has('graveyard:test')), true);

      // Cards on Grimoire and suspended cards also inspect on a plain tap.
      await page.evaluate(() => {
        closeRulesBoardFlow(); latestState.rulesEngine.pendingChoice = null;
        latestState.rulesEngine.suspendedCards = [{ id: 'suspended-test', cardId: __cards[2], playableByPlayerId: 'p1' }];
        latestState.battlefield = [{ id: 'grimoire-host', cardId: __grimoire, ownerId: 'p1', faceUp: true, x: 300, y: 300, fieldZone: 'field', counters: {}, attachedCards: [{ cardId: __cards[2] }] }];
        renderAll(); __sent.length = 0;
      });
      for (const selector of ['#myHandTray [data-ghost-zone="attached"]', '#myHandTray [data-suspended-card]']) {
        await tap(selector); await closeInspect();
        assert.equal(await page.evaluate(() => pendingRulesBoardFlow), null);
        assert.equal(await page.evaluate(() => __sent.length), 0);
      }
      for (const [selector, zone] of [['#myHandTray [data-ghost-zone="attached"]', 'attached'], ['#myHandTray [data-suspended-card]', 'suspended']]) {
        await drag(selector, await targetPoint('#ubZcMe'));
        assert.equal(await page.evaluate(zone => pendingRulesBoardFlow?.source.zone === zone || __sent.some(message => message.source?.zone === zone), zone), true, `Ghost must still play by drag: ${zone}`);
        await page.evaluate(() => { closeRulesBoardFlow(); __sent.length = 0; renderAll(); });
      }
      // Ordinary play also stays drag-only; First Manifestation is committed on drop.
      await page.evaluate(() => {
        closeRulesBoardFlow(); latestState.battlefield = [];
        latestState.rulesEngine.suspendedCards = [];
        latestState.rulesEngine.firstManifestationComplete = false;
        latestState.rulesEngine.firstManifestationItemIds = {};
        latestState.phaseTracker.index = ADVANCED_PHASES.findIndex(phase => phase.id === 'confrontation_choose');
        latestState.players.p1.zones.hand.cards = [[...cardsById.values()].find(card => card.type === "manifestation" && !String(card.effect || "").trim()).id];
        latestState.players.p1.zones.hand.count = 1;
        renderAll(); __sent.length = 0;
      });
      await tap(0); await closeInspect();
      assert.equal(await page.evaluate(() => __sent.length), 0);
      await drag(0, await targetPoint('#ubZcMe'));
      assert.equal(await page.evaluate(() => __sent.some(message => message.type === 'place_card')), true, JSON.stringify(await page.evaluate(() => ({ sent: __sent, drops: __drops.slice(-2), playable: handCardIsPlayable(latestState.players.p1.zones.hand.cards[0]), reason: handCardUnplayableReason(latestState.players.p1.zones.hand.cards[0]), flow: pendingRulesBoardFlow?.mode, phase: currentPhaseUi().phase?.id }))));
      console.log(`PASS ${viewport.width}px: full backdrop, inspect-only taps, exact/multiple hand choices, four payment flows, extra costs, Limbo/Grimoire/suspended ghosts, invalid and cancelled drops`);
      await page.close();
    }
    assert.deepEqual(errors, []);
  } finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
})().catch(error => { console.error(error); process.exitCode = 1; });
