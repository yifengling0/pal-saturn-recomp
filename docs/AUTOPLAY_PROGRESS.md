# Legitimate autoplay checkpoint — 2026-10-10

All progress below uses the verified five-patch baseline, without input timing,
fast spell or CD-rate experiments. Controls are normal game button events;
observations do not edit guest state. This is early-game coverage, not a claim
that every mechanism or the whole story has passed.

## Current route

Inn → serving the meal and receiving wine → village/market → illness storyline
and island departure → Fairy Island shore/path → four island-path battle
victories → stone-statue/lily-pond maze, scene18.

The live controller was restarted from the verified first-victory **game backup**
when its previous process no longer existed. A fresh copy loaded the same
scene16 location and produced exactly the retained post-save frame. No runtime
snapshot, teleport, battle-forcing command or stat modification was used.

## Added coverage after the first fight

- A new blue enemy displayed a whirlwind-like spell and reduced playerHP149→91.
- Healing while damaged displayed59 recovery before the next enemy turn,
  matching the missing HP to the150 maximum. The described75-point spell
  amount was capped here; full75 recovery has not been measured.
- The later enemy normal attack dealt10, leavingHP140 andMP92 at the menu.
  Recovery and subsequent damage are separate observations.
- Four island-path encounters completed normally with victory/results and
  return to the field. Earlier first-battle attack, healing, enemy damage,
  reward and cross-process save/load details are inFIRST_BATTLE_ACCEPTANCE.md.

## Scene18 checkpoint

Normal game-menu save completed at live003VB11158, scene18, world(576,1152).

- Private backup: `build/autoplay-checkpoints/island-statue-maze-entry.bup`
- SHA256: `b21cc0ec1b69ea3b9b7fb041f078abbee84c5350ef83f6746f230ca8bd7f2cc3`
- Input-only replay: `build/autoplay-live-003/replay-to-maze-entry.txt`
- Starting backup for that replay: `island-first-battle-victory.bup`, SHA256
  `d5fb225425b5e33f165df7c0ff3b2915acfb504246d25f8c05602b866b99bcb6`
- Status screen atVB10786: experience12/15, level1, HP148/150, MP95/100.
- Representative actual rendered image: `frame-00011206-042.png` inlive003,
  world(720,1080), showing the lily pond, bridge and stone pillars.

No statue had yet been broken when this checkpoint/image was recorded. The
puzzle and later story are still being played. Commercial disc data and game
backups remain private test inputs and are excluded from source publication.

## Six statue puzzle checkpoint

Continuing the unchanged baseline, normal item use broke all six statues. The
last interaction explicitly says the sixth statue broke and the Heaven-Breaking
Hammer also broke (`autoplay-live-003/frame-00031078-145.png`). Lily platforms
transported the player in both directions during this route. This verifies the
observed puzzle/item script progression, not the next exit or later story.

At31546 the real save menu wrote a checkpoint in scene18, world(1760,832):
- `build/autoplay-checkpoints/island-six-statues-broken.bup`
- SHA256 `e08cadc8026fd018ab330f06a98e689a99079ac0e2e62703d57b9ab68ac05496`
- Replay `build/autoplay-live-003/replay-through-six-statues.txt`,510 pad events,
  starting from the first-victory checkpoint listed above.

An independent process loaded a separate copy with the original baseline SDL
executable in headless mode. At3401, its real image shows the player on the same
stone platform; diagnostic scene18 and coordinates(1760,832) match. Exit0,
original/copied backups unchanged. Evidence: `build/linux-six-statues-load-001`.
The central exit is still being navigated; puzzle completion is not yet asserted
as a successful scene transition.

### Puzzle exit and Fairy Cave bridge

At33904, stepping on the central plate after all six statues broke triggered
scene18→19; stone pillars rearranged into a usable route. The player then
walked out naturally into the Fairy Cave entrance/bridge, scene17. This closes
the puzzle's observed exit transition; there was no black-screen stall.

At35038 a real menu save recorded world(304,824), scene17:
- `build/autoplay-checkpoints/island-cave-bridge.bup`
- SHA256 `f6886653be573d73f173de108c260aba48803bbd47588be1e3e46b6bc0981cdf`
- `build/autoplay-live-003/replay-to-cave-bridge.txt`,570 pad events, same
  first-victory source checkpoint.
- Actual images:33904-155 (new pillar route),34318-157 (entrance narrative),
  34750-159 (bridge), all `frame-000`-prefixed PNGs in live003.

The fairy/medicine story is still being played; it is not counted as passed.

## Water Moon Palace medicine checkpoint

After an executor session was lost, a new process loaded the Fairy Cave bridge
backup; scene17, coordinates(304,824) and the first actual image matched the
previous saved scene exactly. Original executable and source backup hashes were
unchanged. This was an execution-session recovery, not a game FATAL.

The original-timing route continued through Ling'er's initial dialogue,
scene20 and the interior of Water Moon Palace (scene21). A fruit-tree
interaction granted one Mouse Fruit; the actual menu describes MP+36. It is
being retained until a safe, genuinely MP-depleted battle. No recovery effect or
combat use is claimed yet.

Ling'er subsequently gave the Purple Gold Pill in normal dialogue. The real
inventory explicitly shows the pill selected and its palace-medicine description
at `build/autoplay-live-004/frame-00023446-099.png`; Mouse Fruit remains present.
No item was consumed merely to force test coverage.

At23248 a real game-menu save recorded scene21, world(1152,960):
- `build/autoplay-checkpoints/island-purple-gold-pill.bup`
- SHA256 `fc339b62bbde8366645627a08814767dd155bc35c5a802b2608d2e66b68931dd`
- `build/autoplay-live-004/replay-to-purple-gold-pill.txt`,302 pad transitions.
- This replay starts from `island-cave-bridge.bup` (hash above), not the older
  village or first-battle checkpoint.

The next grandmother/return-home story is still in progress. Receiving the
medicine does not establish that the aunt has been healed or later chapters
are playable.

A separate original-baseline process loaded a copied medicine checkpoint at3401:
scene21 and(1152,960) match, exit0 and source/copied BUP bytes unchanged. Evidence:
`build/linux-purple-pill-load-001`. That restart checked the saved scene, not an
additional interactive inventory-menu inspection.

## Aunt cured and night departure checkpoint

The unchanged original baseline completed the grandmother/overnight sequence,
returned to the village and reached the aunt's bedside. Using the Purple Gold
Pill from the wrong location first reported no effect and did not consume it.
At the correct bedside position/facing, normal item use administered the pill
(VB45094). The subsequent amnesia/collapse story and the aunt's recovery played
through without a FATAL. A normal standing-aunt dialogue is recorded at
`build/autoplay-live-004/frame-00047704-220.png`.

The inventory at49186 shows the Purple Gold Pill gone while Mouse Fruit remains.
This establishes the observed quest-item failure/success/consumption path. It
does not establish the untested battle use of Mouse Fruit.

The real game save at49924 records bedroom scene2, world(1280,288):
- `build/autoplay-checkpoints/aunt-cured-night-before-temple.bup`
- SHA256 `d94520bbb4caf5da39e3693bba280e182ee8974b09644e9a277f19e814aa4bff`
- `build/autoplay-live-004/replay-to-aunt-cured.txt`,738 pad transitions, source
  `island-cave-bridge.bup`.

An independent original-baseline process loaded another copy at3401: scene2 and
coordinates match, exit0, source/copied BUP unchanged. Evidence is in
`build/linux-aunt-cured-load-001`. The next sword-learning/temple story remains
in progress; no offensive spell or later boss victory is claimed yet.

## Night mountain, sword learning and new battle mechanisms

The normal night route used the bedroom passage, crossed the mountain path and
reached the temple. That uphill segment completed seven victories and three
successful escapes (separate from the earlier four island battles). Escape
confirmation led to visible running away, battleflag0 and the field without a
reward screen. Level-up1→2 increased HP cap150→160 and MP cap100→111. A bee fight
showed a poisoned portrait and per-turn damage; the later normal portrait alone
is not treated as a full proof of poison persistence/clearing rules.

The temple sword demonstration played through and the real menu then showed
Sword Technique, single-target attack, MP cost10. The first downhill battle
used two legitimate casts, each displaying77 and taking a42HP enemy to-35.
Victory awarded8 experience and8 money, returned to the field and saved at86433:
- `build/autoplay-checkpoints/downhill-first-sword-victory.bup`
- SHA256 `bf73e147d11453df32af5bcf739e5e3eefd714e725c7466c36390863df06442a`
- `build/autoplay-live-004/replay-through-first-sword-victory.txt`,1290 pad
  transitions, source `island-cave-bridge.bup`.

MP deducted10 per observed cast. The later field status is101/111, not the91
inferred by simply subtracting two casts: the game restores some resources
around victory. No general recovery formula is asserted.

In the next natural battle, after two needed attacks, Mouse Fruit was used
normally at MP81/111. The item name displayed, a green30 appeared, and the
command menu returned with MP111/111 and unchanged HP150. Reopening inventory
showed the fruit gone. This verifies consumption and a capped **actual+30**,
not an uncapped+36 recovery. Royal Jelly was also present from prior normal bee
fights; its displayed150HP/MP description is not an effect-use test.

See `BATTLE_TIMING.md` for independent exact Sword Technique timing. The main
route continues; these bounded encounters do not certify all skills, effects,
status conditions or subsequent chapters.

That fruit-use battle then completed normally (89337, experience3/money9) and
wrote a real save before a roaming enemy initiated another encounter:
`downhill-mouse-fruit-used.bup`, SHA256
`6b046819b7e1aa9c07a972f5e31e639f1cb524df761d8a65d1ce8c57ef94d069`.
Replay `build/autoplay-live-004/replay-through-mouse-fruit-victory.txt` contains
1372 pad transitions from the same bridge source. The subsequent bee encounter
does not invalidate the earlier confirmed save write.

After further normal downhill encounters, the player returned safely to the
inn and completed the aunt's morning dialogue. Another normal level-up reached
level3, HP175/175 and MP122/122. The real save at97249 records scene4(1056,1664):
`inn-morning-after-sword.bup`, SHA256
`5015a26e71be8cda0587d30aa1bead319eab446371c7bd7693cfd29d9610061f`.
Replay `build/autoplay-live-004/replay-to-inn-after-sword.txt` contains1526 pad
transitions from the bridge source. The large-sack/Miao guest story is next;
party combat and its later scripted fights are not yet established.

## First two-character Miao story battle

Opening the sack through the normal bedroom passage triggered the story battle
against two Miao enemies. Beforehand a real save was preserved as
`inn-before-sack-rescue.bup`, SHA256
`ecf8f53780c661e0132a6ed2fa27b98c323df311bd2769d4424cd927fc00d42e`.
Li began175/175HP,122MP; Ling'er was deliberately injured at28/240HP,10MP.

Normal ally-target selection let Li's healing restore Ling'er28→103, an
uncapped actual75. Ling'er then used Royal Jelly on herself: HP103→240 capped137,
MP10→160 full150. Subsequent enemy hits were logged separately. Choosing Li's
command advanced to Ling'er's command before execution; her action could execute
first. Her Wind Curse menu cost5 and dealt56; Li's Sword Technique then dealt77
to the separately selected enemy. Later Thunder Curse menu cost7 and dealt
observed85–87. No direct health, inventory or battle-state writes were used.

The story battle ended normally at111103 with experience52 and money96;
Ling'er's luck+2 reward appeared111235, and battleflag returned0 at111427 before
bedroom dialogue continued. Neither party member died. This verifies the tested
two-character fight, not every targeting rule or spell. The subsequent dialogue
and fresh post-battle save are still pending at this report checkpoint.

The post-battle dialogue then completed and a real save at112897 retained
Ling'er as a companion, scene2/world(1296,264):
`inn-miao-victory-ling-er-party.bup`, SHA256
`9322e888aeaba2f3cfc615c22b4c9e99ef50e5fc7e4db9ed5f8ca67a3b3ae333`.
Full legal replay `build/autoplay-live-004/replay-through-miao-victory-party.txt`
contains1806 pad transitions from the bridge checkpoint.

An independent original-baseline process loaded a copy at3401. The rendered
room shows both Li and Ling'er, scene2 and coordinates match, exit0, and the
source/copied BUP hash remains identical. Evidence is under
`build/linux-miao-party-load-001`. The next objective is the normal return boat
to the island; that later chapter is still in progress.

## Return island and Miao leader victory

Following the aunt's normal permission dialogue, the boat returned both party
members to the island. The solved statue route remained open. The grandmother's
last request/farewell and return trip completed without a new battle or FATAL.
Back at the inn, a pre-leader save preserved the next encounter:
`inn-return-before-miao-leader.bup`, SHA256
`f5a79c5e65753486589bd21a14ac54fb51570db2ca3bc655e208377bc3e261c9`.

The leader battle began naturally at151243 with three enemies HP350/800/350.
The player used ordinary targeted attacks and healing to remove the guards.
After Li's MP fell to2, he selected Defense while Ling'er alternated Thunder
Curse and Guanyin healing. An uncapped Guanyin recovery57→207 (+150) and
MP169→159 were observed separately from subsequent enemy damage. Defense was
actually selected and the next turns proceeded; observed1-point hits do not
establish a universal damage-reduction formula.

At184165 the leader's HP83→0 led to Li's level-up3→4, HP189/189 and MP133/133.
Nobody fell, no reload was used, and no state was modified. The experience/cash
reward page was not observed at the coarse final sampling interval, so its
amount is not invented. Subsequent hostage/aunt-intervention scenes are
post-battle story, not a hidden claim that the fight had been lost.

At188923 a real save retained the post-story bedroom scene2/world(720,328),
with Ling'er resting:
- `inn-miao-leader-victory.bup`
- SHA256 `4e6392dd7e1a2cbab2840dc59771c0c59256b2d9c1327ed0efa3450cd95f1683`
- `build/autoplay-live-004/replay-through-miao-leader-victory.txt`,3004 pad
  transitions from the original `island-cave-bridge.bup` source.

An independent baseline process loads the save correctly. A separate private
checkpoint archive was then extracted and its own save copied into another
new process: scene/coordinates, BUP hash and3401 PNG all match the direct load,
exit0. Evidence: `build/linux-leader-victory-load-001` and
`build/linux-private-bundle-restore-001`. The private BUP/input archive is kept
separate from the publishable source package and is not committed to GitHub.

Detailed26-round observations are in `build/early-route-analysis-001/REPORT.md`.
The next chapter remains in progress; no full-game completion is asserted.

## Departure equipment and scroll learning

The normal next-morning aunt dialogue grants a bundle; opening it through the
item menu shows500 coins, a scroll, medicine, embroidered shoes, a jade bracelet
and the father's iron sword. The500 grant is supported by its text; unsampled
prior battle money is not reconstructed backwards from the later balance1542.

Observed equipment changes in actual before/after status pages:
- Li, wooden sword→iron sword: martial48→56, defense52→55, agility38→35.
- Ling'er, cloth boots→embroidered shoes: defense41→42, agility61→59.
- Ling'er, sachet→jade bracelet: defense42→47, spirit72→64, a tradeoff.
The three replaced pieces return to inventory. The bracelet's Li entry is grey
and confirmation has no effect; it equips normally on Ling'er. These are the
observed restrictions, not a full equipment compatibility matrix.

Reading the scroll through ordinary input learns Flying Dragon Cloud Hand and
Ice Heart, with menu MP costs9 and7. Their actual stealing/status-removal effects
are not yet tested merely because the menu shows them.

The real save at209677 is scene3/world(1440,720):
`village-departure-equipped-scroll-learned.bup`, SHA256
`cf2378ab5220aa56a9ca3f77963fadd92efa4bc289a07d5e5191aa9c4cf7b218`.
Replay `build/autoplay-live-004/replay-to-village-departure-equipped.txt` contains
3332 pad transitions from the bridge source. Normal travel is continuing.

## Suzhou arrival, first Yue Ru battle and failed steal

The normal free passage on Fang's cargo boat reaches scene22 outside Suzhou.
The arrival is preserved as `suzhou-arrival-with-ling-er.bup`, SHA256
`c744d36946105b547b8a5f6b2980104745b45808007ffe80b26db977de1e7a2f`.
Intervening in Yue Ru's servant dialogue naturally triggers the next story
battle, one600HP enemy. Both allies are at full combat HP/MP at entry; no
restoration rule is inferred from that script-specific setup.

Li legitimately casts Flying Dragon Cloud Hand once and spends9MP. An
independent full original-input replay resolves its result: **this attempt
fails to obtain money or an item**. All13 same-VBlank main-route images match;
551 consecutive screenshots and execution evidence from the real steal function
show the forward/return action. The failure branch itself has no failure text.
The money field has no writes in the checked window, balance remains1542, and
the enemy's stealable money field remains1000. There was no second steal attempt.
Successful stealing is still untested. Evidence:
`build/first-steal-audit-001/REPORT.md`.

The ten-round battle then wins normally, nobody falls and no reload is used.
Observed rewards:200 experience and500 coins. Li advances4→5 (HP204/MP146),
Ling'er5→6 (HP251/MP249). A normal Golden Wound Medicine use restored Ling'er
93→240, actual capped147; the later inventory verifies quantity2→1. End balance
1542→2042 agrees with the500 battle reward, not a stolen-money grant.

At237157 a real save records scene22/world(928,1024):
`suzhou-first-yueru-victory.bup`, SHA256
`7132da03581f66f6f3c84ba28a6cc735b572af1504ac5199e6b6b969943023d3`.
Full replay `build/autoplay-live-004/replay-through-first-yueru-victory.txt`
contains3734 pad transitions from the bridge source. The route continues into
Suzhou; shops and successful steal/status-clear outcomes are still pending.

## Yue Ru rescue and scripted recovery

The return after the gate-side cries triggers a separate two-bandit battle,
420HP each. Six normal rounds end in victory at253941 with45 experience and95
coins; battle state clears at254325. Yue Ru then wounds Li during the following
story script. This occurs after the proven victory, rather than being a battle
loss or crash. Ling'er's normal rescue dialogue completes and field control
returns; no state editing or reload bypass is used.

A real save at260175 records scene22/world(880,1016):
`suzhou-yueru-rescued-li-recovered.bup`, SHA256
`139765aa1381a8ce8a28175861c4707350293337317f82b5d4dde82c7d2ec3fc`.
The bridge-source replay `replay-through-yueru-rescue-recovery.txt` contains4088
pad transitions. The route continues into the city for ordinary story and
shop/mechanism coverage. The detailed round table is in
`build/early-route-analysis-001/REPORT.md`.

An independent original-build process loads this recovery save normally, exits0
and leaves the source unchanged. The3401 PNG shows both characters standing
in the field (SHA256`d2283078f8b96dcc200c78b1b315a7867e79332fb743340d75c1d21a87c1ad3f`).
Evidence: `build/linux-yueru-recovered-load-001/summary.json`.

Reward correction: the rescue-bandit coin figure is95, confirmed against the
original253941 result image and the balance change2042→2137. The earlier
small-font reading93 was incorrect; source recovery packagev7 predates this
correction. No game logic was changed.

## First shop purchase, equipment and pawn sale

Normal city travel reaches scenes23/24, the blacksmith32 and pawnshop30.
The blacksmith buy confirmation spends400 coins on exactly one rattan armor:
2137→1737, owned0→1. Equipping it on Li changes defense59→63, matching the
old robe's+3 versus armor's+7; other displayed stats are unchanged and the old
robe returns to inventory. This is an actual purchase/equip, not just browsing.

At the pawnshop, the already replaced wooden sword is offered for25 coins.
After the normal Yes confirmation, exactly one sword disappears and coins
1737→1762. The currently equipped iron sword and armor are retained. No plot
item is sold. The buy, sell, quantity, money and equipment changes were checked
on their actual game menus and the money field.

The real save at267117 is scene30/world(864,544):
`suzhou-first-sale-wooden-sword.bup`, SHA256
`2624cf1dfe7773d496bee59cbb3c65ad2d31085a9c593c349097fa178a181d5e`.
Bridge-source `replay-through-first-sale.txt` contains4260 pad transitions.
The earlier buy/equipment save is also retained as
`suzhou-first-shop-rattan-armor.bup`, SHA256
`6b428c69cb8012299e913cf3ba2040665cdaecfbd0a41f92d6f8b669a7c721a9`.

## Liu Jin Yuan rescue: successful stealing and three-enemy victory

The apparently full inn is a normal story step. Its side door leads to the
rescue encounter in scene29; no dialogue or game state was skipped. A real
pre-fight save is retained as `suzhou-before-casino-rescue.bup`, SHA256
`42037d3fa130e50f3170179aa74bbcd2dd4517f4166dd227e89c3d8fbd11995a`.

This separate Flying Dragon Cloud Hand attempt succeeds. Li's selected action
at273003 executes after the final party confirmation273123. At273555 the
actual message says a sleeve sword was obtained; the target's item154/count1
field changes009A0001→009A0000. Back at the command menu, Li's MP146→137
confirms the9MP cost and money remains1762. There was only one attempt in this
fight and no reload. Ling'er actually cast Wind, with white whirlwind and52
damage, MP249→244; this is not labelled Thunder based on prior cursor memory.

Fourteen normal rounds defeat all three enemies (500/540/500HP) without an
ally KO or reload. Li levels5→6 and reaches full216HP/156MP. Money increases
1762→1875, observed+113; the reward page was not captured, so experience is
not inferred. The grateful scholar's dialogue and banquet are actually reached
in scene27. After the banquet, normal free control returns. This checkpoint
does not by itself prove the later overnight/wake-up story has completed.

The post-battle inventory at294591 confirms one sleeve sword, completing the
steal→retained item check. Its description says170HP damage, but it has not
yet been thrown and that number is not reported as measured damage.

A real save at295041 records scene27/world(640,464):
`suzhou-casino-victory-stolen-sword.bup`, SHA256
`11eddbd2f487d5593824f7368b4f4608c5987576fd91b199b66f372a3676f4d0`.
Bridge-source `replay-through-casino-victory-banquet.txt` contains4700 pad
transitions. All of this route uses the unchanged original-timing executable;
input-response, quick-spell and rejected frame-preview experiments are off.

## Overnight, restored party and tournament victory

Review of the actual292989 narrator frame confirms that Liu's conversation
lasted through the night. The earlier provisional report withheld this claim
until checking that image. Li then normally wakes Ling'er and she resumes
following. A real save at297231 records scene27/world(672,352),
`suzhou-morning-ling-er-rejoined.bup`, SHA256
`8a654016cfac227001a1d77a5e8ccb4d49c114cd37fe6c6d9e66dca1c0178f16`.
The next automatic fortune-teller conversation deducts no money; balance1875
is retained. Normal entry reaches the Lin-family tournament in scene33.

The pre-entry safe save is `suzhou-before-lin-mansion-tournament.bup`, SHA256
`b74d7892a8c12ef8832a35a58717d1cb926cd29751457edae8bc7e1e00161b96`,
scene24/world(816,472). This is the single-party tournament fight against
Yue Ru450HP, distinct from the earlier two-party600HP encounter.

The stolen sleeve sword is legitimately thrown once. Confirmed312051,
independent damage170 appears312243 and enemyHP450→280. After the action,
LiMP156 is unchanged, and the312693 inventory no longer contains that item.
Thus the previously descriptive170 is now measured, with consumption of one
item and no MP cost. It is not combined with a later sword-spell hit.

Four subsequent Sword Technique casts deal86/85/84/85. EnemyHP sequence is
280→194→109→25→−60. Five total rounds win on the first attempt without healing,
KO or reload. The314961 result image explicitly shows200 experience and0
coins. Post-victory dialogue is continuing; a later safe save is not inferred
from the reward screen alone.

The post-tournament family-hall dialogue completes normally and the guestroom
becomes controllable: a real save at326829 records scene39/world(1536,1072),
`lin-tournament-victory-guestroom.bup`, SHA256
`2d743ff464005f548101de409abece0e492040f4371a67e2e9d3c605654dbb86`.
Bridge-source `replay-through-tournament-victory-guestroom.txt` contains5124
pad transitions. A transient image/exec transport error during the dialogue
was resolved by read-only access to the same controller and matching image;
no duplicate action, new gameplay instance or reload was required. The game
log has no FATAL. The original first-attempt victory evidence is preserved.

## Yue Ru joins the active party

Following the normal garden/hall conversations and the report from the western
room, Ling'er is absent and Yue Ru volunteers to accompany Li. At344163 both
characters stand in scene37/world(1088,496). Her actual344265 status panel
shows level3, HP220/220, MP80/80, attack58, spirit22, defense22, speed60,
luck37 and her own equipment. This is an observed party change, not a claim
that the next reported snake event is already a completed battle.

True save344661: `lin-yueru-joined-before-snake-room.bup`, SHA256
`b83756155800160fc4c952ed2fd926f6ad66165c547f054366ee883122c2c837`.
The bridge-source replay `replay-to-yueru-joined-snake-room.txt` contains5508
pad transitions. An independent original-build process loads it normally,
exits0 and leaves the source unchanged; both characters appear in the field.
Evidence: `build/linux-yueru-party-load-001/summary.json`.

## Departure toward Hidden Dragon Cave

The western-room snake-form event and wall escape play as normal scripted
scenes; no actual combat occurs there. Following the family dialogue and Li's
departure, Yue Ru catches up by the river and offers to guide the route. She
becomes the visible party leader through that story script, not a tested manual
party-order command. Both then reach the new wooden-bridge map, scene43.

A real bridge-head save at355741 is
`hidden-dragon-road-yueru-leading.bup`, SHA256
`312b158b3fe53547ab8f0015f1a2ed419c5ee7c846739eefcde6464f4bccd6be`.
The bridge-source `replay-to-hidden-dragon-road.txt` contains5696 pad
transitions. The route continues toward the cave; Yue Ru's own combat skills
and the upcoming dungeon are not yet marked as tested from this travel alone.

## Yue Ru group spell and cave entry

The first natural mountain-road encounter has three32HP wooden rats. Yue Ru
casts the actually available group skill while Li defends, isolating the spell:
all three receive52/53/53 and the one-round victory grants6 experience/6 coins.
An independent original-prefix replay resolves7MP spent and3 restored after
victory, detailed in BATTLE_TIMING.md. The true post-fight save is
`hidden-dragon-first-qijianzhi-victory.bup`, SHA256
`2c8b0f4e4bc5d577c5cd18842d04cddef3c42572fca1f636213c5ab34d2e03ff`,
scene43/world(1152,1488) at357995.

A later two-enemy fight visibly shows three horizontal sword-energy streaks,
independent50/50 damage, followed separately by Li's physical attack. The next
command menu still in battle confirms Yue Ru's MP79→72. After one enemy falls,
the remaining60HP is subsequently represented by two30HP enemies; the normal
second round clears them. This is recorded as an observed apparent split,
not an unverified formal name or a claim about every enemy AI feature.

Five natural road encounters are completed without intentional encounter
farming. The cave is actually entered as scene45, with Li automatically back
at the front. A real save at365399 records
`hidden-dragon-cave-entry.bup`, SHA256
`773362fa921314f94901650b6a129217ba7a2be04beaf84769bf0f042fc775a1`.
The bridge-source `replay-to-hidden-dragon-cave-entry.txt` has5908 pad events.
The cave route and its later boss are still in progress.

The original route has also cleared the first cave layer via scene45 door665,
reaching scene47/world(1504,1376). Six natural battles occurred in that layer;
Yue Ru's level-up panel shows3→4, HP234/MP88. No medicine was consumed and no
ally fell. The real379197 save is `hidden-dragon-first-layer-cleared.bup`,
SHA256`3a2c2e43420bbc47f84df442f83b420a270a75ea5474816e2eb1c904557a52eb`.
`replay-to-first-cave-layer-cleared.txt` contains6308 bridge-source pad events.
The deeper cave route is still in progress. The separately verified quick
Yue Ru spell uses its own branch and is not substituted into this main route.

## Second cave layer: new talisman and Yue Ru healing

The original-timing route reaches Li's level7 and the actually available
Tian Shi Fu Fa (天師符法), costing18MP. In a natural encounter with an ordinary
650HP large snake, Yue Ru defends to isolate the first cast: the circular
paper-talisman effect appears, the enemy receives150 damage (650→500), and
Li's MP167→149 is confirmed at the following command menu. The visual sampling
is only every60VB here, so this is not a precise first-effect latency result.
This ordinary enemy is not the later story Snake Man.

During that same fight, Yue Ru uses Ning Shen Gui Yuan (凝神歸元) on herself.
The visible green127 restores her HP107→234, reaching her current maximum;
MP80→62 confirms the18MP charge. A subsequent enemy hit leaves214HP at the
next menu. The observed127 is the capped actual recovery, not a claim about
the uncapped healing formula. Li's subsequent talisman cast is separately
observed alongside that healing action.

The fight ends normally after four rounds, with55 experience/52 coins and a
later Li defense+1 panel. The route leaves scene46 through door689 and reaches
scene47/world(800,1632); money is2112 and the run has no FATAL. The real save at
394817 is `hidden-dragon-second-layer-talisman-heal.bup`, SHA256
`3744206d23db96333754ff4d45cb0e28346eadadbe454a61aad8407336faa662`.
The original bridge-source `replay-to-second-cave-layer-talisman-heal.txt`
contains6658 pad transitions. Deeper exploration continues toward the story
boss; the new spell and self-heal do not establish all spells or status cures.

An independent original-build process loads this second-layer save normally,
exits0 and leaves the source/input unchanged. Its3401 field PNG is SHA256
`1f3b6cd82d60b07995d6263a013618d0010e24aa49be4be0e33b6e96c1eb0a48`;
evidence is `build/linux-second-cave-layer-load-001/summary.json`.

## Third cave layer cleared

Scene41 is traversed through door600 into scene47/world(1664,1696). Thirteen
natural encounters occur along its narrow winding route, including several
moving enemies reaching the party immediately after another victory. These
are not deliberately farmed encounters. All end normally, with no medicine
used or ally falling; the final ordinary650HP snake takes four rounds. Yue Ru
has reached level5 with252HP/101MP maxima, and money is2325.

The real418941 save `hidden-dragon-third-layer-cleared.bup` has SHA256
`f9f05c9db98df413e0d4eb0fc23c360d4a4715c914e29a988ace081458461bb3`.
`replay-to-third-cave-layer-cleared.txt` contains7236 transitions from the same
original island bridge source. The route now continues through scene42's
outer corridor toward the story boss, which is still pending.

An independent original-build load exits0 with source/input unchanged, field
PNG SHA256`0360a999353fa2c62267f17683418f963c4eecca29c9b97e7c013eb179d6ec8b`.
Evidence: `build/linux-third-cave-layer-load-001/summary.json`.

## High-damage ordinary hydra encounter

Scene42's outer corridor contains a red multi-headed500HP snake. This remains
an ordinary encounter, not the story Snake Man. Its first round hits both
characters for138, leaving Li93HP and Yue Ru90HP. Normal self-healing on round2
and Yue Ru's ally-target Ning Shen Gui Yuan on Li in round3 stabilize the party;
talisman and group sword-energy attacks finish the fourth round. The result
at425433 awards110 experience/53 coins. No ally falls, no medicine is used,
and there is no retreat, reload or state edit. Yue Ru subsequently reaches
level6, with264HP/113MP maxima. This is an observed successful defensive
response to one high-damage enemy, not a claim about all boss AI.

The safe426255 save in scene42/world(432,824),
`hidden-dragon-red-hydra-victory.bup`, has SHA256
`02f5ed25f56b0a5750a34502dab954d1c271c21175e457e8320e1a7ccc46e15d`.
`replay-to-red-hydra-victory.txt` contains7374 original-bridge pad transitions.
The outer-corridor traversal and later story-boss encounter remain in progress.

The independent original-build reload exits0 with source/input unchanged;
3401 field PNG SHA256 is
`8fa7e9011ceac3ee8bebfe4e94068357515b15f866220b77f539de673d8cac5b`.
Evidence: `build/linux-red-hydra-victory-load-001/summary.json`.

## Before the story Snake Man

The inner-side scene42 save at437021/world(1152,944) is
`hidden-dragon-before-snake-man.bup`, SHA256
`41528363a49447a2625bd67aa232e4cbcdf61c84203a4a56c6720614aa34a5dd`.
The corresponding original-bridge replay has7642 transitions. Li is level7,
HP232/232 and MP126/167 after a normal field Qi Liao cast restores195→232
while spending6MP. Yue Ru is level6, HP264/264 and MP98/115 at this checkpoint.
The observed pack has3 hemostatic herbs,1 wound medicine,2 spirit pills
(described as+50MP),3 beehives and1 royal jelly (described as+150HP/MP), with
2479 coins; no antidote or revival medicine is present. Description values
are not substituted for unperformed item-use measurements.

An independent original-build load exits0 and preserves source/input, PNG
SHA256`cf12d12d19690dbe49d542c8ab2d9a6979d1afd0cdbc1a3c3f2de69cfa77cfc5`.
The story Snake Man is then actually encountered with2200HP at438377. This
section records entry and preparation only; its outcome is pending.

## Story Snake Man: first-attempt victory

The2200HP Snake Man is defeated in15 normal rounds with original timing and
all optional switches off. The last talisman does147, taking84→−63 at454535;
the454655 result screen explicitly grants250 experience and1100 coins.
No character dies and no save is reloaded. Normal healing and MP recovery
are required during the long fight, with the following actual consumptions:

- Royal jelly1→0: Li's MP18→167 restores149 to the cap. HP is also restored,
  but a later enemy hit is not conflated with the item's immediate amount.
- Spirit pill2→1: Yue Ru's MP16→66 restores exactly50, confirmed at the next
  menu. The item name is visible at447923 and the result at448463.
- Beehive3→2: its bee animation plays at444299/444359, but enemy HP remains
 1315 before Li's separate talisman. This test establishes consumption and
  presentation, not direct damage or a successful poison status on this boss.

The enemy's later dialogue/action change and damage are recorded in the
per-round evidence, without claiming a fully reverse-engineered AI threshold.
After victory Li reaches level8 (243HP/176MP maxima), Yue Ru level7
(281HP/126MP), and each receives an additional defense+2 panel. Both have
full resources after the level-up sequence. Money2479→3579 matches the reward;
the battle flag returns to0 at455855 and the map is visible again.

The normal456173 save in scene42/world(864,800) is
`hidden-dragon-snake-man-victory.bup`, SHA256
`bb161f1239e858dcd3c112a8a3aafbd966c012617319a5bceb0e023d02c3f5ca`.
`replay-to-snake-man-victory.txt` contains7938 transitions from the same
original island-bridge save. The cave's subsequent story is still in progress.

An independent original-build process loads the victory save normally, exits0
and preserves the source/input. Evidence:
`build/linux-snake-man-victory-load-001/summary.json`.

## Fox Woman: single-target skill, hypnosis cure and summons

The next ordinary story path enters the cave dwelling, scene48. Before the
Fox Woman, a normal459489 save at(1312,272) preserves full post-level resources:
`hidden-dragon-before-fox-woman.bup`, SHA256
`be8f0a28ded2276b8053c088537c7d50767508df55717610ca5f73d1b3ade735`.
Its original-bridge replay has8024 pad transitions. Independent original-build
load exits0 and preserves the source/input (PNG0532ea5c3c2796ac31bbfd29f92c35a123de3612b8f0e2101848d08c100d28eb).

The Fox Woman begins with1500HP. Yue Ru's newly available Yi Yang Zhi (一陽指)
is tested while Li defends: final confirmation462939, first observed column
of energy463131, enemy1500→1370 by463191, and the next menu confirms
MP126→108. Thus independent damage130 and18MP charge are observed. The
60VB image sampling does not establish an exact first-visible latency.

At round5 Yue Ru is naturally hypnotized, with the visible「眠」status and
crouched posture. Li selects Bing Xin Jue (冰心訣) on her at468075. Its star
effect appears at468267; she stands by468387, before the enemy's next hit at
468507. The468867 menu has no「眠」and Li's MP104→97 confirms7MP spent.
Yue Ru's MP stays36. An additional19 enemy-HP change after waking is preserved
as unexplained here, not assigned as damage from the cure spell. This establishes
one actual hypnosis cure; poison and every other status remain unverified.

The boss also summons additional enemies. The resulting extra target-selection
step causes one originally single-enemy command sequence to strike a summon
and Yue Ru to use a physical attack; actual HP/MP and target slots identify
this input mistake rather than a spell malfunction. Explicit selection then
finishes the remaining targets. The ninth round ends with talisman148,
Fox HP130→−18 at471855. The result grants188 experience and358 coins, with a
beehive drop; money3579→3937 confirms358. An initial quick visual read of338
was corrected against the enlarged result, inventory money and the next menu.

Stone key item289 is acquired with quantity1. After the story dialogue ends,
a real474429 save in scene48/world(1376,304) is made:
`hidden-dragon-fox-woman-victory.bup`, SHA256
`0679f9c7cb1638bc258204fc1f37e55a29739b6f7ebf95d5f5316142ca266808`.
`replay-to-fox-woman-saved.txt` has8232 original-bridge transitions. An earlier
save attempt made during dialogue was still the old prebattle BUP and is
explicitly labelled as such in local evidence; it is not this accepted save.

The accepted victory save loads normally in an independent original-build
process, exit0 with source/input unchanged. Evidence:
`build/linux-fox-woman-victory-load-001/summary.json`.

## Stone key consumed and cave rescue completed

The rear stone door first reports that it is locked at476001. The inventory
shows the stone key's matching door description at476409. Normal use opens
the door at476601 and item289 quantity1→0 confirms consumption. Scene49 is
entered at476805/world(464,1672); the rescued girls thank the party, and their
subsequent dialogue points toward Bai He Village. This is a real story/quest
item transition, with no guest-state writes.

After the dialogue, the normal478617 save is
`hidden-dragon-exit-rescue-complete.bup`, SHA256
`3a296d4360cec6dd54baead9d30dc8884723cd67fccc978bbce799bae0190621`.
`replay-to-cave-exit-rescue.txt` contains8336 original-bridge pad transitions.
The run reports no FATAL and continues toward Bai He Village; later chapters
and endings remain outside the verified play coverage.

An independent original-build process loads this rescue-complete save, exits0
and preserves source/input. Evidence:
`build/linux-cave-exit-rescue-load-001/summary.json`.

## Bai He Village medicine quest

The normal cave exit path reaches Bai He Village (scene50), then the physician's
courtyard and home (53/54). The actual reunion with Ling Er and physician
conversation starts at483849. A Bao lists the six medicines, and Yue Ru
accepts the ginseng/snow-lotus/He Shou Wu part while Li is assigned ginkgo,
deer antler and carp. The subsequent physician/Ling Er cutscene returns
normally to field control. This records the quest opening, not completed
medicine collection or treatment.

Yue Ru leaves through the story and Li is alone at the real490563 save,
scene53/world(896,896): `baihe-medicine-quest-split-party.bup`, SHA256
`5a59115aa6e858a6f4aeefcd04193e5144b6ca81a593cb162827b5d19393acd6`.
`replay-to-baihe-medicine-quest.txt` has8602 original-bridge transitions.
The run has no FATAL and continues along the normal ingredient quest.

Independent original-build fresh load succeeds (exit0), preserving source and
input. Evidence: `build/linux-baihe-medicine-quest-load-001/summary.json`.

## Fishing, returning the rod and catching the deer

Li normally picks ginkgo fruit281 from the courtyard tree. The borrowed
fishing rod284 is used from scene50/world(272,1400), facing down: the actual
fishing animation appears at497679, followed by a caught-carp message at
498279. Inventory confirms fruit281, rod284 and carp282 each quantity1.
The real498831 save `baihe-ginkgo-and-carp.bup` has SHA256
`bdd07799c74e1dfb98c2cefe7a97ffa8c7a5eea087a35451e1d9f5af6198cd1d`;
its original-bridge replay has8790 transitions. Independent fresh load exits0,
source/input unchanged (PNG2ce7c9463085090e25571cf3108c7c0aada2226236b8bf7770c91a644a928572).

The rod is then returned through the owner's dialogue at499761; quantity284
becomes0. Li collects trap285 in the forest and makes a pre-trap save at
502671, scene49/world(784,1032): `baihe-before-deer-trap.bup`, SHA256
`4e909d2d5cf8789db13b07338f837d3b08f6c63517c175a8f25c320cfbac7395`.
The corresponding original-bridge replay has8898 transitions.

Normal inventory use places the trap at scene49/world(1184,560) at504675,
removing it from the pack. Through ordinary walking/herding the deer reaches
that position at505791 and is visibly caught by505941. A normal interaction
at506163 yields antler283, quantity1, and the subsequent text explicitly
says the deer is released after obtaining the antler. No event-state edits
or forced captures are used. This verifies one complete fishing and one
trap-placement/capture quest sequence, not every map-interaction mechanic.

The three assigned ingredients are each quantity1 at the real507219 save,
scene49/world(1184,544): `baihe-deer-caught-three-ingredients.bup`, SHA256
`d11f72d10bf24c8308842acae697062effc4f2b575fd5aca5c7f2499a9ae013b`.
`replay-to-three-ingredients.txt` has9002 original-bridge transitions. The
next step is delivery to the physician; treatment is not yet declared complete.

This three-ingredient save also loads in an independent original-build process,
exit0 with source/input unchanged. Evidence:
`build/linux-three-ingredients-load-001/summary.json`.

## Pause for Windows testing handoff

At the user's request, further story input is paused after a real save at
VB509937, scene50/world(1008,936), outside the Bai He rice shop. Li remains
alone; fruit281, carp282 and antler283 each have quantity1, the fishing rod
has been returned and the trap has been consumed normally. Ingredients have
not yet been delivered and Liu Shen Dan has not been obtained. Battle flag0,
all buttons released and FATAL count0.

`baihe-three-ingredients-delivery-pending-windows-handoff.bup` SHA256:
`1bdcc46b9f46eb78e640fcf10811583098b825c73e91a5077066591df3aa515c`.
`replay-to-windows-handoff-509937.txt` has9104 original-bridge pad events, SHA256
`47c8bbc83794cb7bcf662946e9c18019ba43dd41535745156c104e08b49e8412`.
This is a normal game save, not a forced runtime state or story skip.

After the two verified source commits were published, the old controller
handle was unavailable. No input was sent through that unknown handle. A new
controlled process loads an independent copy of the pause BUP normally;
VB3401 restores scene50/world(1008,936), battle0, with source save and original
executable hashes unchanged. Further `live005` replay records use this pause
BUP as their source, not the much earlier island bridge. All `live004` evidence
is preserved. This recovery is not evidence that the old underlying process
was definitely dead, nor a replay reset to change a battle result.

## Liu Shen Dan and first three-character party

In the independently restored `live005` route, Li delivers the three medicines
normally: fruit281, carp282 and antler283 are consumed and Liu Shen Dan286 is
received, quantity1. A Bao explicitly asks for it to be taken while hot. The
pre-treatment normal save `baihe-six-god-pill-acquired.bup` has SHA256
`f1e99258796a798e1e06154a0d1b099e988f648f118bcccebc4dd840d3340387`.
Its `live005/replay-to-six-god-pill.txt` contains83 pad events and starts from
the Windows-handoff BUP1bdcc46b… above, not the original island bridge.

Ling Er actually takes the medicine at8455; item286 quantity1→0 is confirmed.
The physician says she can get out of bed at9271; she does so at9643 and joins
the subsequent normal conversation. This treatment does not automatically
refill everyone's resources. The actual status menus after the dialogue show:
Li level8 HP243/243 MP103/176; Ling Er level6 HP229/251 MP198/249; Yue Ru level7
HP219/281 MP77/126. This is the first three-person party on this route, not yet
a verified three-person battle.

After hearing the Jade Buddha Temple lead, a real15259 save in scene54,
world(1424,600), is `baihe-ling-recovered-three-party.bup`, SHA256
`32f8b7a8f84c59261ffdbb907be0328052951f23e9b636b171bd0aa1c72ae9ee`.
The `live005/replay-to-ling-recovered.txt` has229 events, from the same handoff
save. The source hash remains unchanged and no FATAL occurs.

The three-party save independently reloads in the original build, exit0 with
source/input unchanged; field PNG SHA256
`c3b92dc9af29913a1b2efc495d2ab2c37b8ce4c9ba3867172f784dfb614f1456`.
Evidence: `build/linux-baihe-three-party-load-001/summary.json`.

## 2026-10-11: first three-party combat and safe video handoff

Ling's recovery and rejoining were followed by normal northern-bridge travel.
The first natural three-person fight completed in three rounds against three
bee-like enemies, awarding6XP/6coins and returning to scene55. Observed actions
include Wind (5MP, zero damage against the selected enemy, resistance not yet
independently identified), Cleanse (7MP on Yue, abnormal HUD bar disappears) and
Yue's whip hitting all three targets. Do not infer every poison type or every
multi-target weapon from this bounded example.

A following900HP tiger fight completed in three rounds,30XP/0coins. The original
mainline is safely saved at scene55/world544,624, mainline VB29343 after its
normal reload from the prior handoff save. Its BUP SHA256 is
`c705b04ede94081304ee5905a2bbfd1c13577ed34bbb7cfcebc2f94342099e2a`.
An independent original-timing process loads it normally, exits0 and leaves the
source/test BUP unchanged; screenshot SHA256
`09fdd637c3dbc4e10e09ed472b41d7734f3d61bda447b9fd5f1220e469121859`.
Mainline is paused here while the requested input/spell videos are made.

The separate Thunder video branch starts from the first-three-party-victory
save, loads normally and navigates to a tiger. Li/Yue defend and Ling uses an
actually learned7MP Thunder spell. Ordinary preparation yields60 damage;
quick preparation's three animation-speed reference runs yield59. These are
separate controlled branches, not silently substituted mainline progress.
