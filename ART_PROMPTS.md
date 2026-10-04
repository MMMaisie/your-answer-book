# 六十四象 · 画面制作记录

使用内置图像生成制作四幅4×4图集，每格对应一卦，按文王卦序从左到右、从上到下排列。

## 共同风格与布局提示

Create a production website illustration atlas, EXACT 4 columns x 4 rows edge-to-edge, 16 equally sized portrait paintings. Overall canvas portrait ratio 2:3 so each cell is portrait 2:3. No gutters, borders, lettering, numbers, hexagram symbols, UI, captions, watermark. Each cell is a distinct classical Chinese Song dynasty landscape / meticulous gongbi painting, fine ink strokes, mineral azurite, malachite green, cinnabar accents, antique gold light on textured silk, calm atmospheric depth, dignified restrained composition. The paintings must be separate scenes and strictly in row-major order as listed. These are symbolic art for I Ching cards, not factual predictions. Each scene has a clear focal subject and does not spill into neighbors. 

## 图集 1（1—16卦）

ROW 1: 1 Qian creative heaven: golden dragon ascending into luminous sky above clouds; 2 Kun receptive earth: vast fertile fields and nurturing earth under soft mist; 3 Zhun beginning difficulty: tender shoot emerging among wet rocks in thunderstorm; 4 Meng youthful learning: young scholar with lantern at foot of misty mountain. ROW 2: 5 Xu waiting: traveler resting on riverbank while clouds gather; 6 Song conflict: two scholars on opposite banks facing a divided stream; 7 Shi disciplined army: orderly ancient banners and soldiers crossing plain; 8 Bi union: villagers joining hands by water surrounding earth. ROW 3: 9 Xiao Xu small restraint: breeze carrying clouds above terraced fields, rain withheld; 10 Lu careful treading: lone traveler stepping carefully beside calm tiger; 11 Tai harmony: heaven and earth joining over open flowing bridge; 12 Pi obstruction: towering cliff dividing low earth from distant sky, blocked gateway. ROW 4: 13 Tong Ren fellowship: companions meeting in broad bright countryside; 14 Da You abundance: bronzed vessel filled with harvest under high sun; 15 Qian humility: mountain peak hidden below low cloud amid plain; 16 Yu enthusiasm: spring thunder awakening music and dancing villagers.

## 图集 2（17—32卦）

ROW 1: 17 Sui following: travelers following a lantern along winding river; 18 Gu repairing decay: artisan repairing old timber ancestral hall; 19 Lin approach: noble guide approaching villagers beside marsh; 20 Guan contemplation: sage atop watchtower surveying fields. ROW 2: 21 Shi He biting through: bronze blade cleanly cutting a tied knot under lightning; 22 Bi grace: elegantly painted pavilion at foot of mountain with evening firelight; 23 Bo stripping away: weathered tower shedding outer tiles leaving foundation; 24 Fu return: first green sprout rising after winter beside homeward path. ROW 3: 25 Wu Wang innocence: wild crane in unspoiled field beneath clear thundercloud; 26 Da Xu great restraint: strong horse resting behind mountain gate; 27 Yi nourishment: bowl of grain and careful hands beneath mountain; 28 Da Guo great excess: heavy wooden roof beam visibly bending over lotus lake. ROW 4: 29 Kan repeated water: deep successive rapids between sheer dark gorges; 30 Li radiance: two lamps illuminating scroll in luminous hall; 31 Xian attraction: mountain reflected in lake, two cranes approaching; 32 Heng endurance: old pine standing steady through wind and thunder.

## 图集 3（33—48卦）

ROW 1: 33 Dun retreat: sage withdrawing along distant mountain path; 34 Da Zhuang great strength: powerful ram stopped at a fence below thundercloud; 35 Jin progress: rising sun illuminating advancing steps toward pavilion; 36 Ming Yi hidden light: lamp sheltered beneath cloak in dark valley. ROW 2: 37 Jia Ren family: warm courtyard household tending shared hearth; 38 Kui divergence: two figures facing different horizons, fire above lake; 39 Jian difficulty: traveler before flooded mountain pass; 40 Jie release: storm clouds opening and knotted rope coming loose. ROW 3: 41 Sun decrease: hand setting down an extra vessel to lighten burden by lake; 42 Yi increase: fresh water nourishing young grove and fields; 43 Guai decisive breakthrough: clear river breaking through worn embankment under sun; 44 Gou encounter: unexpected elegant figure arriving beneath wind-bent trees. ROW 4: 45 Cui gathering: many small boats converging around ancestral temple; 46 Sheng ascent: young tree rising through earth toward stone staircase; 47 Kun exhaustion: dry well and weary traveler under sparse reeds; 48 Jing the well: ancient well drawing clear water for nearby community.

## 图集 4（49—64卦）

ROW 1: 49 Ge transformation: old red robe exchanged for new beneath autumn sky; 50 Ding the cauldron: ancient bronze tripod steaming over steady fire; 51 Zhen awakening thunder: lightning awakening startled traveler and swaying trees; 52 Gen still mountain: seated sage between two unmoving mountains. ROW 2: 53 Jian gradual progress: geese advancing in measured formation along shore toward hillside; 54 Gui Mei uncertain marriage: bridal sedan waiting off-center outside grand closed gate; 55 Feng fullness: midday festival lanterns and full granary beneath brief eclipse; 56 Lu the traveler: lone traveler with small pack at mountain inn. ROW 3: 57 Xun gentle wind: bamboo bending softly beside open windows; 58 Dui joyful lake: two bright lakes with friends sharing tea on shore; 59 Huan dispersal: wind scattering mist over river, boats freed; 60 Jie limits: water contained in measured stone channels among bamboo. ROW 4: 61 Zhong Fu inner sincerity: two cranes reflected faithfully in still lake beside open courtyard; 62 Xiao Guo small exceeding: little bird flying low beneath mountain clouds; 63 Ji Ji after completion: boat safely moored across river beside contained hearth; 64 Wei Ji not yet completion: small fox at river edge with wet tail, distant shore still ahead.


## 2026-10-04 画意修订
内置 image_gen 生成三张独立替代图，接入 static/art/hexagram-15.webp、hexagram-23.webp、hexagram-26.webp。

共同提示：单幅2:3竖画，宋代青绿山水与工笔、古绢肌理；墨青黛绿赭石淡金；无文字边框水印。
- 谦：厚土平原包容低矮山脉，收敛而有内在力量；避免高耸尖峰。
- 剥：古屋仍直立，外墙逐渐剥蚀，老人加固基脚；避免全塔崩塌与爆炸。
- 大畜：健康骏马昂首静立山门内，门向远天敞开，石案书卷；体现积学蓄力，避免门外低头马。

64卦均已核对上下卦顺序，并加入《象传》原典取象（参考 https://zh.wikisource.org/zh-hans/周易/大象 ）。原典、现代卦义与画面借喻分开呈现。随、临、复、离等保留艺术转译，并补说明以免误读为盲从、权威、旧人回头或财富。
