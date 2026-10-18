# Rapport de certification des cartes KKO

Ce rapport est généré par `py tools/card_certification.py --write`. Il sépare les tests
comportementaux exécutables des contrôles structurels. Une preuve structurelle confirme
que la carte, ses règles compilées, ses capacités, ses références de tests et ses états
sandbox sont cohérents ; elle ne remplace pas encore un scénario dédié à son texte.

## Résumé

| Mesure | Résultat |
| --- | ---: |
| Cartes du catalogue | 450 |
| Cartes sans échec mécanique | 450 |
| Cartes en échec | 0 |
| Capacités explicites | 493 |
| Capacités exécutées par le smoke test | 493 |
| Chemins de comportement exécutés | 497 |
| Scripts exécutés | 323 |
| Étapes de scripts exécutées | 1292 |
| Scénarios comportementaux dédiés | 4 |
| Cartes simples exécutées de bout en bout | 47 |
| Cartes dont toutes les capacités sont exécutées isolément | 373 |
| Cartes à règles statiques exécutées | 24 |
| Preuve structurelle seulement | 0 |
| Automatisation partielle | 0 |
| Application manuelle | 2 |

## Interprétation

- `scénario comportemental` : un scénario écrit envoie de vrais messages au serveur et vérifie le résultat.
- `règles génériques exécutées` : tout le texte est composé de mots-clés génériques contrôlés et joués automatiquement.
- `capacités exécutées isolément` : chaque résultat, effet continu, passif ou permission déclaré par la carte a traversé son chemin moteur dans un état riche.
- `règles statiques exécutées` : la carte n'a pas de capacité déclarative ; ses états génériques et calculs de caractéristiques ont été exécutés.
- `preuve structurelle seulement` : les contrôles passent, mais il manque encore un scénario dédié à la carte.
- `partielle` ou `manuelle` : le registre documente une mécanique qui reste hors du moteur.

## Détail par carte

| Nº | Carte | Extension | Statut déclaré | Niveau de preuve | Capacités | Scripts | Étapes | Résultat |
| ---: | --- | --- | --- | --- | ---: | ---: | ---: | --- |
| 1 | Wind Sprout | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 2 | Sated Swineheart | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 3 | Merciful Pago | Beta | automated | règles statiques exécutées | 0 | 1 | 4 | OK |
| 4 | Tiptup, the Whistler | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 5 | Slumber Planner | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 6 | Tidying Torment | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 7 | World Spore | Beta | automated | règles génériques exécutées | 0 | 3 | 12 | OK |
| 8 | Graceful Petal | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 9 | The Slumberer | Beta | automated | capacités exécutées isolément | 5 | 1 | 4 | OK |
| 10 | Amiable Blockhead | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 11 | First Stone | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 12 | Sprawling Tentacle | Beta | automated | règles statiques exécutées | 0 | 0 | 0 | OK |
| 13 | Flower Tender | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 14 | Pinpia Psychobulb | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 15 | Floating Dancer | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 16 | Echo of the Wilds | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 17 | Stoic Snoozer | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 18 | Guart, the Slinger | Beta | automated | capacités exécutées isolément | 2 | 1 | 4 | OK |
| 19 | Jondo, the Pure Heart | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 20 | Pan Zuto, the Beckoner | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 21 | Spontaneous Incubator | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 22 | Urocione, the Anarchist | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 23 | Lady of the Humps | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 24 | Stampeding Brood | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 25 | Agrupol, Ponderer of Fields | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 26 | Prospero of the Bushes | Beta | automated | règles statiques exécutées | 0 | 1 | 4 | OK |
| 27 | Advocate of Catharsis | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 28 | Mobile Sanctuary | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 29 | Herbaceous Whisperer | Beta | automated | règles statiques exécutées | 0 | 1 | 4 | OK |
| 30 | Rinq, Shameless Slacker | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 31 | Forest Guide | Beta | automated | règles génériques exécutées | 0 | 4 | 15 | OK |
| 32 | Mazzolong, the Log-chief | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 33 | Tong, the Expansive | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 34 | Peropero, the Spirophant | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 35 | Gargullo, King of the Woods | Beta | automated | règles statiques exécutées | 0 | 1 | 4 | OK |
| 36 | Unite Impulses | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 37 | Plea for Generosity | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 38 | Armored Husk | Beta | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 39 | Intoxicating Blossom | Beta | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 40 | Entrust | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 41 | Compensating Orchard | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 42 | Altruistic Inflorescence | Beta | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 43 | Cozy Bunk | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 44 | Rally | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 45 | Reap What You’ve Sown | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 46 | Heartening Monument | Beta | automated | règles statiques exécutées | 0 | 0 | 0 | OK |
| 47 | Atavic Welcome | Beta | automated | capacités exécutées isolément | 3 | 0 | 0 | OK |
| 48 | Concealed Manta | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 49 | Artificial Thinker | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 50 | Isolated Wordsmith | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 51 | Scrutinizing Figure | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 52 | Keen-eyed Seeker | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 53 | Witty Scribe | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 54 | Hurlon, Thought-implanter | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 55 | Chitinous Repeller | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 56 | Refrain Repeater | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 57 | Reliable Ammonite | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 58 | Chiff and Chaff | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 59 | Rigid Omen | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 60 | Venerable Viper | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 61 | Gar Fild, the Malleable | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 62 | Arcane Teapot | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 63 | Inspired Nimbus | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 64 | Ohmom, the Azure | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 65 | Coral Skull | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 66 | Skysailing Triad | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 67 | Inert Anchorstone | Beta | automated | capacités exécutées isolément | 2 | 1 | 4 | OK |
| 68 | Shababba, Divining Cube | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 69 | Jurat, the Strategist | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 70 | Hermeto, the Observer | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 71 | Ju Lien, the Provocateur | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 72 | Tipson, the Mediator | Beta | automated | règles statiques exécutées | 0 | 1 | 4 | OK |
| 73 | Expansive Ponderer | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 74 | Dew Invoker | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 75 | Gomeran, Echo Mistress | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 76 | Shymon, the Mastermind | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 77 | Callus, the Thought-stirrer | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 78 | Pigon, the Apprentice | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 79 | Rajas, Great Aegis | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 80 | Blue Entity | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 81 | Malaleuco, the Will-shaper | Beta | automated | capacités exécutées isolément | 2 | 1 | 4 | OK |
| 82 | Freenya, Heartless Songstress | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 83 | Glimpse the Omens | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 84 | Defer | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 85 | Mirror the Impulse | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 86 | Imitate | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 87 | Nullifying Hat | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 88 | Consult | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 89 | Persist | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 90 | Scrambling Beacon | Beta | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 91 | Suspend Judgment | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 92 | Dominate the Aspects | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 93 | Banish | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 94 | Atavic Introspection | Beta | automated | capacités exécutées isolément | 3 | 0 | 0 | OK |
| 95 | Little Abhorrence | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 96 | Timid Brain | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 97 | Repudiated Orphan | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 98 | Mourning Offal | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 99 | Skin-shifting Tearer | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 100 | Ridiculous Persecutor | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 101 | Yurfuq, Sad Lily | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 102 | Tenebro, Night Assailant | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 103 | Forgotten Pile | Beta | automated | règles statiques exécutées | 0 | 1 | 4 | OK |
| 104 | Dark Apparition | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 105 | Filth-eater | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 106 | Underground Snail | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 107 | Soul-borer | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 108 | Solenero, the Contrite | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 109 | Possessed Pyramid | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 110 | Zombieswing | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 111 | Diabolical Giant | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 112 | Mind Parasite | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 113 | Shuk, the Bile-filled | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 114 | Lament, Thought-nullifier | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 115 | Forfog, the Hanged | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 116 | Lerxur, the Black Moon | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 117 | Ehgog, the Livid | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 118 | Zrutrug, the Indebted | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 119 | Reviving Cage | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 120 | Repelling Urn | Beta | automated | règles statiques exécutées | 0 | 1 | 4 | OK |
| 121 | Carcass Devourer | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 122 | Armored Pachywyrm | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 123 | Red Plague | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 124 | Otranth, the Bloodthirsty | Beta | automated | capacités exécutées isolément | 4 | 1 | 4 | OK |
| 125 | Urolong, Rueful Necromancer | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 126 | Pale Entity | Beta | automated | capacités exécutées isolément | 2 | 1 | 4 | OK |
| 127 | Quasimillenary | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 128 | Ergorath, Scribe of the Limbo | Beta | automated | capacités exécutées isolément | 2 | 1 | 4 | OK |
| 129 | Half Han, the Renegade | Beta | automated | capacités exécutées isolément | 2 | 1 | 4 | OK |
| 130 | Disfigure | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 131 | Claim the Forsaken | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 132 | Twist the Soul | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 133 | Cognitive Fog | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 134 | Punish the Winners | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 135 | Shattering the Self | Beta | automated | scénario comportemental | 1 | 1 | 4 | OK |
| 136 | Reforging Fate | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 137 | Parasitic Drill | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 138 | Flaying Jaw | Beta | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 139 | Traumatize | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 140 | Revive | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 141 | Atavic Oppression | Beta | automated | capacités exécutées isolément | 3 | 0 | 0 | OK |
| 142 | Auriwings | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 143 | Absent Trinket | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 144 | Roly-polymancer | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 145 | Exalted Jester | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 146 | Yzzit, the Gambler | Beta | automated | règles statiques exécutées | 0 | 0 | 0 | OK |
| 147 | Peevish Sapling | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 148 | Pok, the Teaser | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 149 | Incoherent Pard | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 150 | Unpredictable Loudmouth | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 151 | Static Scuttler | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 152 | Loop, the Insistent | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 153 | Cimba, the Boisterous | Beta | automated | règles statiques exécutées | 0 | 0 | 0 | OK |
| 154 | Mimer | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 155 | Rogue Tadpole | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 156 | Juggling Amphora | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 157 | Gnarlipuff, the Slimy | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 158 | Wandering Outcast | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 159 | Knobbly Colossus | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 160 | Soup, the Graceful | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 161 | Ranba, Silent Abductor | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 162 | Sallow Thief | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 163 | Unruly Flail | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 164 | Bloatuba | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 165 | Planar Beak | Beta | automated | règles statiques exécutées | 0 | 1 | 4 | OK |
| 166 | Obtrusive Mass | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 167 | The Stomper | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 168 | Thought Saboteur | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 169 | Starkaz, the Brilliant | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 170 | Jigon, the Trap Setter | Beta | automated | capacités exécutées isolément | 2 | 1 | 4 | OK |
| 171 | Zaguor, Greedy Pedal | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 172 | Vexing Thorn | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 173 | Logos, the Lost | Beta | automated | capacités exécutées isolément | 2 | 1 | 4 | OK |
| 174 | Worm Bomb | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 175 | Katun, the Inconsistent | Beta | automated | capacités exécutées isolément | 2 | 1 | 4 | OK |
| 176 | Bratto, Tyrannical Scoundrel | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 177 | Trim the Excess | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 178 | Equalize | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 179 | Neutralize | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 180 | Annihilating Nectar | Beta | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 181 | Salvage the Fragments | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 182 | Wheel of Retribution | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 183 | Pin Down | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 184 | Deviate | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 185 | Invert Emotions | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 186 | Hot Potato | Beta | automated | capacités exécutées isolément | 3 | 0 | 0 | OK |
| 187 | Manipulate Intellect | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 188 | Atavic Volatility | Beta | automated | capacités exécutées isolément | 3 | 0 | 0 | OK |
| 189 | Candle Serpent | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 190 | Ancient Bicep | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 191 | Tigrolione | Beta | automated | règles statiques exécutées | 0 | 1 | 4 | OK |
| 192 | Shimmering Seaguide | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 193 | Twin-headed Druid | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 194 | Blunt Leaf | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 195 | Fiery Furybeast | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 196 | Perfidious Baranchio | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 197 | Wandering Veteran | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 198 | Skapus, the Vile | Beta | automated | règles statiques exécutées | 0 | 0 | 0 | OK |
| 199 | Titan of the Blazing Womb | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 200 | Glabron, the Oppressing | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 201 | Bullyboo | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 202 | Fintus, the Spectacular | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 203 | Thornmaster | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 204 | Pimbo | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 205 | Piercing Lover | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 206 | Gorb, the Musclebound | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 207 | Lucerco the Reckless | Beta | automated | règles statiques exécutées | 0 | 1 | 4 | OK |
| 208 | Numbi, the Irritating | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 209 | Tardigramo | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 210 | Borombo, the Mad | Beta | automated | scénario comportemental | 1 | 2 | 9 | OK |
| 211 | Quorum, the Untouchable | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 212 | Rude Exterminator | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 213 | Vengeful Vilupera | Beta | automated | règles statiques exécutées | 0 | 1 | 4 | OK |
| 214 | Bell, Ardent Fanatic | Beta | automated | règles statiques exécutées | 0 | 1 | 4 | OK |
| 215 | Grudge Weaver | Beta | automated | capacités exécutées isolément | 2 | 1 | 4 | OK |
| 216 | Solar Apparition | Beta | automated | règles statiques exécutées | 0 | 1 | 4 | OK |
| 217 | Bolbakazim, the Cursed | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 218 | Friendly Presence | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 219 | Migmomirf | Beta | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 220 | Gornagor, the Magnificent | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 221 | Imgurd, Flame Craver | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 222 | Jija, Matron Bomb | Beta | automated | capacités exécutées isolément | 2 | 1 | 4 | OK |
| 223 | Sermon, Obscene Quadrumane | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 224 | Nullify Reason | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 225 | Incinerate | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 226 | Corrode | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 227 | Damage | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 228 | Oppress | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 229 | Incite to Sacrifice | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 230 | Repress the Self | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 231 | Honor and Respect | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 232 | Rematch! | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 233 | Life Sustainer | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 234 | Wretched Arena | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 235 | Atavic Fury | Beta | automated | capacités exécutées isolément | 3 | 0 | 0 | OK |
| 236 | Soul-devouring Dunes | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 237 | Hermetic Hourglass | Beta | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 238 | Everspring | Beta | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 239 | Obelisk of Friendship | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 240 | Conflux of Catastrophe | Beta | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 241 | Alchemical Press | Beta | automated | capacités exécutées isolément | 3 | 0 | 0 | OK |
| 242 | Melancholic Mirror | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 243 | Greed Trap | Beta | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 244 | Extortionist Womb | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 245 | Watchtower | Beta | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 246 | Brabataba, the Unambitious | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 247 | Ononok, Chaotic Scatterer | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 248 | Kox, the Amoral | Beta | automated | capacités exécutées isolément | 4 | 0 | 0 | OK |
| 249 | Karma Bro | Beta | manual | application manuelle | 0 | 0 | 0 | OK |
| 250 | Qu Lom, Haphazard Martyr | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 251 | Buddhan the Transcended | Beta | automated | capacités exécutées isolément | 5 | 1 | 4 | OK |
| 252 | Zum, the Manifold | Beta | automated | capacités exécutées isolément | 3 | 1 | 4 | OK |
| 253 | Zizek, the Immolated | Beta | automated | règles statiques exécutées | 0 | 0 | 0 | OK |
| 254 | Gorte, Timeless | Beta | automated | capacités exécutées isolément | 2 | 1 | 4 | OK |
| 255 | Orator of the Absurd | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 256 | Pluff | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 257 | Rocky Heartcrystal | Beta | automated | règles statiques exécutées | 0 | 1 | 4 | OK |
| 258 | Granite Mass | Beta | automated | règles génériques exécutées | 0 | 3 | 11 | OK |
| 259 | Kaos Bro | Beta | manual | application manuelle | 0 | 0 | 0 | OK |
| 260 | Plinius, Risk-taker | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 261 | Mirrorbeast | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 262 | Worn Old Shape | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 263 | Hogma, the Petty | Beta | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 264 | Gummo | Beta | automated | capacités exécutées isolément | 2 | 1 | 4 | OK |
| 265 | Buddhan the Dark | Beta | automated | capacités exécutées isolément | 2 | 1 | 4 | OK |
| 266 | Strengthen | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 267 | Ponder | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 268 | Essence Forager | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 269 | Reveal the Hidden | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 270 | Recover from the Abyss | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 271 | Nullify | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 272 | Weaken | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 273 | Deny Fate | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 274 | Mutate Uncontrollably | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 275 | Accentuate | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 276 | Deny | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 277 | Recall | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 278 | Help! | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 279 | Duel Honorably | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 280 | Censor | Beta | automated | scénario comportemental | 1 | 1 | 6 | OK |
| 281 | Pray the Ether | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 282 | Exile | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 283 | Destroy | Beta | automated | scénario comportemental | 1 | 1 | 4 | OK |
| 284 | Martyrize | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 285 | Ignore | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 286 | Abandon | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 287 | Purifying Ritual | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 288 | Nullifying Radiance | Beta | automated | capacités exécutées isolément | 3 | 0 | 0 | OK |
| 289 | Empathic Mask | Beta | automated | capacités exécutées isolément | 5 | 0 | 0 | OK |
| 290 | Unreachable Pillar | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 291 | Trap | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 292 | Humiliate | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 293 | Remove by Chance | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 294 | Essence Cauldron | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 295 | Eliminate the Profane | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 296 | Karmapult | Beta | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 297 | Grimoire | Beta | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 298 | Will-punishing Cannon | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 299 | Protect | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 300 | Volcano | Beta | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 301 | Flem | Inner Deserts | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 302 | Buuz, the Helicoidal | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 303 | Zam-za, the Prosperous | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 304 | Quper, the Bestower | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 305 | Manibirbo | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 306 | Faroc-Ko, the Insipid | Inner Deserts | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 307 | Eorthoda, the Limpid | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 308 | Larman Doz, the Upright | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 309 | Berta, the Peaceful | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 310 | Gusted Nebula | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 311 | Chobariki, of the Shiny Muscles | Inner Deserts | automated | capacités exécutées isolément | 4 | 0 | 0 | OK |
| 312 | Mukkabell | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 313 | Ycar, the Fleeting Flow | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 314 | Lombriculpop | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 315 | Zborh, the Eternal | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 316 | Linoleus, the Verdant | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 317 | Mamelath, the Polymancer | Inner Deserts | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 318 | Paciphint, the Pious | Inner Deserts | automated | capacités exécutées isolément | 3 | 1 | 4 | OK |
| 319 | Dissolve and Coagulate | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 320 | Healing Bond | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 321 | Convert the Pain | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 322 | Psychowall | Inner Deserts | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 323 | Simulacrum of Clemency | Inner Deserts | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 324 | Caress the Dawn | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 325 | Viter | Inner Deserts | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 326 | Denblew, the Puritan | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 327 | Glob-glob | Inner Deserts | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 328 | Alakazim, the Magician | Inner Deserts | automated | règles statiques exécutées | 0 | 1 | 4 | OK |
| 329 | Bivalv, the Circumspect | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 330 | Philfer, the Sharp | Inner Deserts | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 331 | Brioski, the Aerial | Inner Deserts | automated | règles génériques exécutées | 0 | 3 | 11 | OK |
| 332 | Poopom, the Hydromancer | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 333 | Gladionimbus | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 334 | Bonzai, the Unexpected | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 335 | Phimosino | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 336 | Looj, Cautious Agitator | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 337 | Tut, Rhythmic Whirlwind | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 338 | Referen-Doom, the Dreamer | Inner Deserts | automated | capacités exécutées isolément | 2 | 1 | 4 | OK |
| 339 | Denegath, the Regulator | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 340 | Ippokridal, of Icy Fervor | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 341 | Timidette, the Elusive | Inner Deserts | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 342 | Ababash, the Ambassador | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 343 | Obscure | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 344 | Veer the Will | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 345 | Hyperuranic Tower | Inner Deserts | automated | capacités exécutées isolément | 4 | 0 | 0 | OK |
| 346 | Pass Judgment | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 347 | Dissect | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 348 | Wish Upon the Stars | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 349 | Mal | Inner Deserts | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 350 | Tombloom | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 351 | Bakato, the Obsessive | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 352 | Kanopo, the Headless | Inner Deserts | automated | règles statiques exécutées | 0 | 1 | 4 | OK |
| 353 | Manymaws | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 354 | Quasimolg, the Hunched | Inner Deserts | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 355 | Nghoul-ong, the Tormented | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 356 | Makaboon | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 357 | Sangen, the Relic | Inner Deserts | automated | capacités exécutées isolément | 4 | 1 | 4 | OK |
| 358 | Leadenshroud | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 359 | Nameless Arcane | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 360 | Tebebe, Taken by the Dunes | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 361 | Dol, the Aching | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 362 | Gigabonblade | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 363 | Memento, the Fallen | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 364 | Kanon, the Deathdealer | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 365 | Jesterina, the Decadent | Inner Deserts | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 366 | Mejik, the Labyrinther | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 367 | Regurgitating Catacomb | Inner Deserts | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 368 | Eviscerate Morality | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 369 | Tax of the Malignant | Inner Deserts | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 370 | Cradle the Putrescence | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 371 | Walk the Oblivion | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 372 | Recall the Consumed | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 373 | Capry | Inner Deserts | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 374 | Sly Frog | Inner Deserts | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 375 | Ozzit, the Unwary | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 376 | Nubilung, the Elder | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 377 | Swindley, the Festive | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 378 | Proboscidon, the Boor | Inner Deserts | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 379 | Pegasso | Inner Deserts | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 380 | Cirrocumulus | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 381 | Mollino, the Repeller | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 382 | Gorlok, the Blinded Indiscreet | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 383 | Auction Profiteer | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 384 | Chabak, the Ungrateful | Inner Deserts | automated | capacités exécutées isolément | 2 | 1 | 4 | OK |
| 385 | Fee-fee, the Afflicted | Inner Deserts | automated | capacités exécutées isolément | 3 | 1 | 4 | OK |
| 386 | Thoughtcutter | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 387 | Moaning Consul | Inner Deserts | automated | capacités exécutées isolément | 2 | 1 | 4 | OK |
| 388 | Gobres, the Collector | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 389 | Silem, the Magnetic | Inner Deserts | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 390 | Pescojolero, the Ringing King | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 391 | Embottle | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 392 | Discombobulator | Inner Deserts | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 393 | Bizarre Mechanism | Inner Deserts | automated | capacités exécutées isolément | 4 | 0 | 0 | OK |
| 394 | Pontificate Heresy | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 395 | Mock Fate | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 396 | Lunar Liturgy | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 397 | Chol | Inner Deserts | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 398 | Crickelob, the Vile | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 399 | Palgonphio | Inner Deserts | automated | règles statiques exécutées | 0 | 1 | 4 | OK |
| 400 | Juggernut, the Overwhelming | Inner Deserts | automated | capacités exécutées isolément | 3 | 1 | 4 | OK |
| 401 | Sticky Fasces-fly | Inner Deserts | automated | capacités exécutées isolément | 2 | 1 | 4 | OK |
| 402 | Orzo, the Greatmace | Inner Deserts | automated | règles génériques exécutées | 0 | 2 | 8 | OK |
| 403 | Punitive Tripod | Inner Deserts | automated | capacités exécutées isolément | 2 | 1 | 4 | OK |
| 404 | Dulfer, the Touchy | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 405 | Stormmace | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 406 | Kelona, the Anchorite | Inner Deserts | automated | règles statiques exécutées | 0 | 1 | 4 | OK |
| 407 | Lugione, the Hungry | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 408 | Horned Augustus | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 409 | Rah-kio, the Flyswatter | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 410 | Solitary Combhand | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 411 | Phalanx Tower | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 412 | Kazadur, the Fiery | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 413 | Lilitha, the Dismemberer | Inner Deserts | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 414 | Sandokaron, Banners Bearer | Inner Deserts | automated | capacités exécutées isolément | 6 | 1 | 4 | OK |
| 415 | Extinguish Nostalgia | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 416 | Kiss of the Myrmillo! | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 417 | Spiked Pit | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 418 | Inflate the Ego | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 419 | Drain the Substance | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 420 | Overwhelming Persuasion | Inner Deserts | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 421 | Donmo, the Truth-Bender | Inner Deserts | automated | capacités exécutées isolément | 2 | 1 | 4 | OK |
| 422 | Jeovak, the Illusory | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 423 | Sacred Mountain | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 424 | Tuxnu, the Transparent | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 425 | Haltan, the Favored | Inner Deserts | automated | capacités exécutées isolément | 2 | 1 | 4 | OK |
| 426 | Jodorosk, the Psychomage | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 427 | Bibi, the Confused | Inner Deserts | automated | capacités exécutées isolément | 3 | 0 | 0 | OK |
| 428 | Pillarpede | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 429 | Powerful Pidue | Inner Deserts | automated | capacités exécutées isolément | 5 | 1 | 4 | OK |
| 430 | Zozok, the Void | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 431 | Drildrill | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 432 | Losers' Chariot | Inner Deserts | automated | capacités exécutées isolément | 2 | 1 | 4 | OK |
| 433 | Tricephalous Oil-Dog | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 434 | BOB | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 435 | Asciugoth, the Absorbent | Inner Deserts | automated | capacités exécutées isolément | 1 | 1 | 4 | OK |
| 436 | Shattered Memory | Inner Deserts | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 437 | Balance of the Spirit | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 438 | Multicastigate | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 439 | Hermetic Threshold | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 440 | Subjugate | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 441 | Explosive Rancor | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 442 | Flower of Evil | Inner Deserts | automated | capacités exécutées isolément | 2 | 0 | 0 | OK |
| 443 | Temperamental Splendor | Inner Deserts | automated | capacités exécutées isolément | 3 | 0 | 0 | OK |
| 444 | Palm Coercer | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 445 | Cleanse | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 446 | Wall off | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 447 | Float | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 448 | Induce Desertion | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 449 | Compensate | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
| 450 | Sever the Ascent | Inner Deserts | automated | capacités exécutées isolément | 1 | 0 | 0 | OK |
