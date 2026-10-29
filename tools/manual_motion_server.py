"""Loopback-only fixtures for two real browser clients using production handlers."""
import asyncio
import json
from http import HTTPStatus
from urllib.parse import urlsplit, parse_qs
from websockets.asyncio.server import serve
import main
from session import Session

CARD = next(c['id'] for c in main.CARD_DATA if c['name'] == 'Wind Sprout')
WILL = next(c['id'] for c in main.CARD_DATA if c['type'] == 'persistent_will')


async def run():
    s = Session(card_rules=main.CARD_RULES, card_points=main.CARD_POINTS,
        manifestation_ids=main.CARD_MANIFESTATION_IDS, rules_beta=False)
    for seat, pid in enumerate(('p1','p2')): s.get_or_create_player(pid,pid,seat=seat)
    s.phase_tracker['turn'] = 2
    s.rules_engine.update(deckConfirmedPlayerIds=['p1','p2'],readyPlayerIds=['p1','p2'],firstManifestationComplete=True)
    main.sessions[s.code_player] = s

    async def request(connection, request):
        url = urlsplit(request.path)
        if url.path != '/__fixture': return await main.process_request(connection,request)
        pid = parse_qs(url.query).get('pid',['p1'])[0]
        seat = s.players[pid]['seat']
        for p in s.players.values():
            p['zones'] = {z:[] for z in p['zones']}
            p['zoneOwners'] = {z:{} for z in p['zones']}
        for zone in ('deck','hand','graveyard'):
            s.put_zone_card(pid,zone,CARD,pid)
        s.battlefield = [{'id':'motion-source','cardId':CARD,'ownerId':pid,'controllerId':pid,
            'x':445,'y':525 if seat else 800,'faceUp':True,'rotation':0,'counters':{}},
            {'id':'will-source','cardId':WILL,'ownerId':pid,'controllerId':pid,
            'x':610,'y':525 if seat else 800,'faceUp':True,'rotation':0,'counters':{}}]
        s.tokens=[]
        s.touch()
        await main.broadcast_state(s)
        return connection.respond(HTTPStatus.OK,json.dumps({'cardId':CARD,'willId':WILL}))

    async with serve(main.handler,'127.0.0.1',0,process_request=request) as server:
        print(json.dumps({'port':server.sockets[0].getsockname()[1],'code':s.code_player}),flush=True)
        await asyncio.Future()

if __name__ == '__main__': asyncio.run(run())
