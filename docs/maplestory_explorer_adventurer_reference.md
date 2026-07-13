# 메이플스토리 모험가 직업군 참고 정리

작성일: 2026-07-02

이 문서는 Kaling-Bot RPG 데이터 설계를 위한 참고용 요약이다. 실제 메이플스토리의 스킬 계수, 재사용 대기시간, 지속시간, 히트 수는 패치마다 변하므로 여기서는 원문 수치를 그대로 옮기지 않고, "어떤 역할의 스킬인가"에 집중해 정리했다.

영문명은 GMS/Grandis Library 표기를 우선했다. 한국어명은 KMS 통용명을 우선하되, 정확한 공식 표기가 애매한 일부 스킬은 영문명을 병기하고 한국어 설명으로 보완했다.

## 참고 출처

- Grandis Library Explorer class pages: https://www.grandislibrary.com/explorers/
- Grandis Library Hero: https://www.grandislibrary.com/explorers/hero
- Grandis Library Paladin: https://www.grandislibrary.com/explorers/paladin
- Grandis Library Dark Knight: https://www.grandislibrary.com/explorers/dark-knight
- Grandis Library Arch Mage (Fire, Poison): https://www.grandislibrary.com/explorers/arch-mage-fire-poison
- Grandis Library Arch Mage (Ice, Lightning): https://www.grandislibrary.com/explorers/arch-mage-ice-lightning
- Grandis Library Bishop: https://www.grandislibrary.com/explorers/bishop
- Grandis Library Bowmaster: https://www.grandislibrary.com/explorers/bowmaster
- Grandis Library Marksman: https://www.grandislibrary.com/explorers/marksman
- Grandis Library Pathfinder: https://www.grandislibrary.com/explorers/pathfinder
- Grandis Library Night Lord: https://www.grandislibrary.com/explorers/night-lord
- Grandis Library Shadower: https://www.grandislibrary.com/explorers/shadower
- Grandis Library Dual Blade: https://www.grandislibrary.com/explorers/dual-blade
- Grandis Library Buccaneer: https://www.grandislibrary.com/explorers/buccaneer
- Grandis Library Corsair: https://www.grandislibrary.com/explorers/corsair
- Grandis Library Cannoneer: https://www.grandislibrary.com/explorers/cannoneer
- MapleStory Explorer overview, broad class tree reference: https://en.wikipedia.org/wiki/MapleStory

## 전직 트리 요약

일반 모험가는 초보자에서 1차 직업군을 고르고, 30/60/100레벨 구간에서 세부 직업으로 이어진다. 특수 모험가인 패스파인더, 듀얼블레이드, 캐논슈터는 같은 모험가 계열이지만 별도 전직 흐름을 가진다.

| 계열 | 1차 | 2차 | 3차 | 4차 최종 | 공식/통용 영문명 |
|---|---|---|---|---|---|
| 전사 | 검사 | 파이터 | 크루세이더 | 히어로 | Swordman -> Fighter -> Crusader -> Hero |
| 전사 | 검사 | 페이지 | 나이트 | 팔라딘 | Swordman -> Page -> White Knight -> Paladin |
| 전사 | 검사 | 스피어맨 | 버서커 | 다크나이트 | Swordman -> Spearman -> Berserker -> Dark Knight |
| 마법사 | 매지션 | 위자드(불,독) | 메이지(불,독) | 아크메이지(불,독) | Magician -> Wizard (Fire, Poison) -> Mage (Fire, Poison) -> Arch Mage (Fire, Poison) |
| 마법사 | 매지션 | 위자드(썬,콜) | 메이지(썬,콜) | 아크메이지(썬,콜) | Magician -> Wizard (Ice, Lightning) -> Mage (Ice, Lightning) -> Arch Mage (Ice, Lightning) |
| 마법사 | 매지션 | 클레릭 | 프리스트 | 비숍 | Magician -> Cleric -> Priest -> Bishop |
| 궁수 | 아처 | 헌터 | 레인저 | 보우마스터 | Archer -> Hunter -> Ranger -> Bowmaster |
| 궁수 | 아처 | 사수 | 저격수 | 신궁 | Archer -> Crossbowman -> Sniper -> Marksman |
| 궁수 특수 | 패스파인더 | 패스파인더 | 패스파인더 | 패스파인더 | Pathfinder |
| 도적 | 로그 | 어쌔신 | 허밋 | 나이트로드 | Rogue -> Assassin -> Hermit -> Night Lord |
| 도적 | 로그 | 시프 | 시프마스터 | 섀도어 | Rogue -> Bandit -> Chief Bandit -> Shadower |
| 도적 특수 | 듀얼블레이드 | 듀얼블레이드+ | 슬래셔 | 듀얼마스터 | Dual Blade progression |
| 해적 | 해적 | 인파이터 | 버커니어 | 바이퍼 | Pirate -> Brawler -> Marauder -> Buccaneer |
| 해적 | 해적 | 건슬링거 | 발키리 | 캡틴 | Pirate -> Gunslinger -> Outlaw -> Corsair |
| 해적 특수 | 캐논슈터 | 캐논슈터 | 캐논블래스터 | 캐논마스터 | Cannoneer |

## 공통 링크 스킬

| 계열 | 링크 스킬 영문명 | 요약 효과 |
|---|---|---|
| 전사 | Invincible Belief | HP가 낮아졌을 때 자동 회복. 모험가 전사 3종으로 중첩 강화. |
| 마법사 | Empirical Knowledge | 공격 시 약점 파악 디버프를 걸어 피해/방어 무시 보너스. 모험가 마법사 3종으로 중첩 강화. |
| 궁수 | Adventurer's Curiosity | 크리티컬 확률 및 몬스터 컬렉션 관련 보너스. 모험가 궁수 3종으로 중첩 강화. |
| 도적 | Thief's Cunning | 적에게 디버프를 걸면 일정 시간 피해 증가. 모험가 도적 3종으로 중첩 강화. |
| 해적 | Pirate's Blessing | 올스탯/HP/MP/피해 감소 계열 보너스. 장비 스탯 전환 기능이 있는 계열 링크. |

## 공통 1차 스킬 묶음

| 계열 | 주요 스킬 영문명 | 한국어 요약 |
|---|---|---|
| 전사 | War Leap, Iron Body, Warrior Mastery, Slash Blast | 이동기, 방어/체력 패시브, 무기 숙련 기반, 전방 범위 공격. |
| 마법사 | Mana Wave, Teleport, Magic Guard, MP Boost, Magic Armor, Energy Bolt | 수직 이동/텔레포트, MP 기반 생존, MP/마법 방어 패시브, 기본 마법 공격. |
| 궁수 | Double Jump, Archery Mastery, Critical Shot, Arrow Blow | 더블 점프, 궁술 숙련, 크리티컬 패시브, 기본 화살 공격. |
| 도적 | Flash Jump, Nimble Body, Haste, Dark Sight, Double Stab, Lucky Seven | 점프 이동, 회피/속도, 다크 사이트, 단검/표창 기본 공격. |
| 해적 | Pirate Leap, Bullet Time, Dash, Shadow Heart, Somersault Kick, Double Shot | 이동기, 명중/회피/크리 계열 패시브, 근접/원거리 기본 공격. |

## 전사 계열

### 히어로 (Hero)

컨셉: 콤보 오브를 쌓아 최종 피해와 보스 피해를 끌어올리는 순수 물리 딜러. 검/도끼 계열 무기를 사용한다.

| 전직 | 추가 스킬 영문명 | 한국어 설명 및 효과 태그 |
|---|---|---|
| 2차 파이터 | Combo Attack, Brandish, Flash Blade, Final Attack, Spirit Blade, Weapon Mastery, Agile Arms | 콤보 오브 시스템 시작. 브랜디쉬/플래시 블레이드로 기본 공격 루프 형성. 파이널 어택은 추가타. 스피릿 블레이드는 공격력 버프. |
| 3차 크루세이더 | Intrepid Slash, Beam Blade, Rush, Scarring Sword, Combo Synergy, Chance Attack, Self Recovery, Endure | 주력 연계와 돌진. 스카링 소드는 디버프/표식 성격. 찬스 어택은 상태 이상 대상 피해 증가. |
| 4차 히어로 | Raging Blow, Enrage, Advanced Combo, Advanced Final Attack, Puncture, Combat Mastery, Magic Crash | 레이징 블로우가 주력기. 인레이지는 보스전 집중 모드. 어드밴스드 콤보로 콤보 효율 강화. 펑처는 피해 증가 디버프 성격. |
| 하이퍼/5차/6차 | Cry Valhalla, Rising Rage, Burning Soul Blade, Sword Illusion, Worldreaver, Instinctual Combo, Spirit Calibur | 버스트 버프, 광역기, 설치/추가타, 무적/강한 일격, 6차 바인드/극딜기로 구성. |

### 팔라딘 (Paladin)

컨셉: 성속성, 방어, 파티 보호, 무적에 강한 탱커형 전사. 검/둔기와 방패/로자리 계열 보조를 사용한다.

| 전직 | 추가 스킬 영문명 | 한국어 설명 및 효과 태그 |
|---|---|---|
| 2차 페이지 | Divine Swing, Close Combat, Vessel of Light, Final Attack, Weapon Mastery, Agile Arms | 빛의 힘 스택 기반 전투 시작. 디바인 스윙은 기본 공격기, 베슬 오브 라이트는 스택/피해 감소 축. |
| 3차 나이트 | Divine Charge, Divine Shield, Parashock Guard, Combat Orders, Rush, Noble Demand | 성속성 차지 공격, 보호막, 파티 방어 보조, 스킬 레벨 증가 버프. 노블 디맨드는 적 약화/도발 성격. |
| 4차 팔라딘 | Blast, Divine Mark, Divine Judgment, Heaven's Hammer, Divine Blessing, Guardian, Greater Vessel of Light | 블래스트는 보스 주력기. 헤븐즈 해머는 광역기. 가디언/디바인 블레싱으로 생존과 파티 보조 강화. |
| 하이퍼/5차/6차 | Smite Shield, Sacrosanctity, Grand Guardian, Divine Echo, Mighty Mjolnir, Sacred Bastion | 바인드, 긴 무적, 파티 공유/보호, 망치 투척형 극딜, 성역형 버스트. |

### 다크나이트 (Dark Knight)

컨셉: 창/폴암, 이블 아이, HP 기반 생존과 사망 방지/부활형 전투를 사용하는 전사.

| 전직 | 추가 스킬 영문명 | 한국어 설명 및 효과 태그 |
|---|---|---|
| 2차 스피어맨 | Hyper Body, Spear Sweep, Evil Eye Shock, Iron Will, Final Attack, Weapon Mastery, Agile Arms | 하이퍼 바디로 HP/MP 보조. 이블 아이 소환/충격 공격이 시작된다. |
| 3차 버서커 | Cross Surge, Lord of Darkness, Hex of the Evil Eye, Evil Eye of Domination, La Mancha Spear, Rush | HP/공격력 연동 버프, 흡혈/크리 보정, 이블 아이 강화, 라만차 스피어 채널링 공격. |
| 4차 다크나이트 | Gungnir's Descent, Dark Impale, Final Pact, Revenge of the Evil Eye, Dark Resonance, Barricade Mastery | 궁니르는 보스 핵심기. 파이널 팩트는 사망 방지/강화 상태. 이블 아이 반격과 다크 레조넌스로 지속딜 강화. |
| 하이퍼/5차/6차 | Nightshade Explosion, Dark Spear, Radiant Evil, Calamitous Cyclone, Dead Space | 광역 폭발, 창 투척/회전 극딜, 6차 어둠/공간계 버스트. |

## 마법사 계열

### 아크메이지(불,독) (Arch Mage (Fire, Poison))

컨셉: 지속 피해, 독/화염 중첩, 도트 폭발을 이용하는 누적형 마법 딜러.

| 전직 | 추가 스킬 영문명 | 한국어 설명 및 효과 태그 |
|---|---|---|
| 2차 위자드(F/P) | Flame Orb, Poison Breath, Ignite, Meditation, Spell Mastery, MP Eater | 화염/독 공격, 도트 장판/추가 화염, 마력 버프와 MP 회수. |
| 3차 메이지(F/P) | Explosion, Poison Mist, Creeping Toxin, Burning Magic, Element Amplification, Elemental Decrease, Teleport Mastery | 독 안개/폭발, 독성 설치, 속성 저항 감소, 도트 대상 피해 증가. |
| 4차 아크메이지(F/P) | Flame Sweep, Mist Eruption, Flame Haze, Meteor Shower, Ifrit, Infinity, Arcane Aim | 도트 폭발이 핵심. 플레임 스윕/헤이즈로 도트 부여, 미스트 이럽션으로 누적 폭발. |
| 하이퍼/5차/6차 | Megiddo Flame, Inferno Aura, DoT Punisher, Poison Nova, Elemental Fury, Infernal Venom | 강한 단일 도트, 오라형 도트, 독성 구체/폭발, 6차 독화염 버스트. |

### 아크메이지(썬,콜) (Arch Mage (Ice, Lightning))

컨셉: 빙결 스택과 번개 공격의 상호작용, 광역 사냥과 바인드/무적 성능이 강한 마법사.

| 전직 | 추가 스킬 영문명 | 한국어 설명 및 효과 태그 |
|---|---|---|
| 2차 위자드(I/L) | Thunder Bolt, Cold Beam, Absolute Zero Aura, Freezing Crush, Meditation, Spell Mastery | 얼음 공격으로 스택을 쌓고 번개 공격으로 소모/증폭하는 기본 구조. |
| 3차 메이지(I/L) | Ice Strike, Thunder Sphere, Frost Ward, Shatter, Storm Magic, Teleport Mastery, Elemental Adaptation | 얼음 광역, 번개 구체, 방어막, 빙결 대상 방어 무시/피해 증가. |
| 4차 아크메이지(I/L) | Chain Lightning, Frozen Orb, Blizzard, Freezing Breath, Elquines, Infinity, Arcane Aim | 체인 라이트닝이 주력. 프로즌 오브/블리자드로 얼음 스택, 프리징 브레스는 바인드/무적 성격. |
| 하이퍼/5차/6차 | Lightning Orb, Bolt Barrage, Jupiter Thunder, Spirit of Snow, Frost Ark, Frozen Lightning | 번개 채널링, 다단히트 폭격, 설치/소환, 6차 빙뢰 버스트. |

### 비숍 (Bishop)

컨셉: 회복, 경험치/드롭 보조, 파티 보호, 부활, 강력한 성속성 공격을 모두 가진 지원형 마법사.

| 전직 | 추가 스킬 영문명 | 한국어 설명 및 효과 태그 |
|---|---|---|
| 2차 클레릭 | Heal/Angelic Wrath, Bless, Invincible, Holy Arrow, Spell Mastery, MP Eater | 회복과 축복 버프. 전투 모드에서는 엔젤릭 래스로 공격/방어 무시 디버프 역할. |
| 3차 프리스트 | Holy Symbol, Holy Fountain/Fountain of Vengeance, Mystic Door, Dispel/Triumph Feather, Shining Ray, Holy Magic Shell, Divine Protection | 홀리 심볼로 경험치/드롭 보조, 디스펠/쉘/문으로 파티 유틸. |
| 4차 비숍 | Angel Ray, Big Bang, Genesis, Resurrection, Advanced Blessing, Bahamut, Holy Water/Blood of the Divine, Infinity | 엔젤레이/제네시스 공격, 부활, 고급 축복, 바하뮤트 소환. |
| 하이퍼/5차/6차 | Righteously Indignant, Heaven's Door, Benediction, Angel of Balance, Peacemaker, Divine Punishment, Holy Advent | 딜 모드 전환, 파티 생존권, 대형 버프 장판, 평화/징벌형 극딜, 6차 성역. |

## 궁수 계열

### 보우마스터 (Bowmaster)

컨셉: 활, 연속 사격, 퀴버/환영 화살, 높은 공격 속도와 크리티컬 기반의 원거리 딜러.

| 전직 | 추가 스킬 영문명 | 한국어 설명 및 효과 태그 |
|---|---|---|
| 2차 헌터 | Wind Arrow, Covering Fire, Swift Surge, Final Attack, Soul Arrow, Bow Mastery, Agile Bows | 화살 공격 루프, 이동/엄호 사격, 화살 소모 제거, 숙련/공속 패시브. |
| 3차 레인저 | Arrow Blaster, Phoenix, Blink Shot, Speed Mirage, Reckless Hunt: Bow, Marksmanship, Mortal Blow | 설치/연속 사격, 피닉스 소환, 위치 이동, 환영 추가타, 사냥/보스 패시브. |
| 4차 보우마스터 | Hurricane, Arrow Stream, Enchanted Quiver, Sharp Eyes, Armor Break, Bow Expert, Illusion Step, Advanced Final Attack | 허리케인이 보스 주력. 샤프 아이즈는 크리티컬/크뎀 버프. 퀴버와 방어 파괴로 지속딜. |
| 하이퍼/5차/6차 | Concentration, Gritty Gust, Storm of Arrows, Quiver Barrage, Inhuman Speed, Silhouette Mirage, Ascendant Shade | 장판/폭풍 화살, 퀴버 강화, 고속 사격 버프, 생존 환영, 6차 그림자 화살. |

### 신궁 (Marksman)

컨셉: 석궁, 관통/저격, 거리 조건과 강한 단일 타격을 활용하는 원거리 딜러.

| 전직 | 추가 스킬 영문명 | 한국어 설명 및 효과 태그 |
|---|---|---|
| 2차 사수 | Piercing Arrow, Covering Fire, Swift Surge, Final Attack, Soul Arrow, Crossbow Mastery, Agile Crossbows | 관통 화살과 이동/엄호. 석궁 숙련과 공격 속도 패시브. |
| 3차 저격수 | Bolt Burst, Empowered Arrows, Frostprey, Blink Bolt, Aggressive Resistance, Reckless Hunt: Crossbow, Marksmanship, Pain Killer | 강화 화살, 냉기 소환, 위치 이동, 방어/저항 보정. |
| 4차 신궁 | Snipe, Piercing Arrow II, Arrow Illusion, Sharp Eyes, Greater Empowered Arrows, Bolt Surplus, Last Man Standing, Crossbow Expert | 스나이프가 보스 주력. 피어싱은 사냥/관통. 애로우 일루전은 유인/방어 무시 보조. |
| 하이퍼/5차/6차 | Bullseye Shot, High Speed Shot, Split Shot, Perfect Shot, Surge Bolt, Repeating Crossbow Cartridge, Final Aim | 보스 집중 버프, 화살 분열/차지, 석궁 탄창형 극딜, 6차 조준 사격. |

### 패스파인더 (Pathfinder)

컨셉: 고대의 활과 렐릭 게이지, 카디널/에인션트/인챈트 포스 스킬을 조합하는 특수 모험가 궁수.

| 전직 | 추가 스킬 영문명 | 한국어 설명 및 효과 태그 |
|---|---|---|
| 1차 | Cardinal Deluge, Forceful Shot, Double Jump, Archery Mastery | 카디널 델루지로 기본 사격 루프. 포스풀 샷은 크리티컬 보정 패시브 성격. |
| 2차 | Cardinal Burst, Swarm Shot, Relic Jet, Cardinal Deluge Amplification, Bountiful Deluge, Ancient Bow Mastery | 폭발형 카디널 버스트, 스웜 샷, 렐릭 기반 이동. 카디널 스킬 강화 시작. |
| 3차 | Cardinal Torrent, Triple Impact, Shadow Raven, Guidance of the Ancients, Bountiful Burst, Cursebound Endurance | 순간 이동/돌진형 공격, 까마귀 소환, 고대의 인도 버프, 저주/생존 보정. |
| 4차 | Combo Assault, Glyph of Impalement, Advanced Cardinal Force, Ancient Archery, Bountiful Torrent, Curseweaver, Sharp Eyes | 카디널 조합/고대 문양 공격, 고대 활 패시브, 샤프 아이즈. |
| 하이퍼/5차/6차 | Ancient Astra, Raven Tempest, Obsidian Barrier, Relic Unbound, Nova Blast, Forsaken Relic | 렐릭 해방, 방벽, 소환/폭풍, 고대 포스 버스트. |

## 도적 계열

### 나이트로드 (Night Lord)

컨셉: 표창, 높은 크리티컬, 표식/추가 표창, 짧은 폭딜에 강한 원거리 도적.

| 전직 | 추가 스킬 영문명 | 한국어 설명 및 효과 태그 |
|---|---|---|
| 2차 어쌔신 | Shuriken Burst, Gust Charm, Shadow Leap, Shadow Surge, Shadow Blink, Critical Throw, Claw Mastery, Agile Claws | 표창 광역/넉백, 그림자 이동, 크리티컬/클로 숙련. |
| 3차 허밋 | Triple Throw, Shuriken Challenge, Shadow Partner, Dark Flare, Spirit of the Star, Venom, Expert Throwing Star Handling | 섀도우 파트너로 타수 복제, 다크 플레어 설치, 표창 숙련/독. |
| 4차 나이트로드 | Quad Star, Showdown, Night Lord's Mark, Frailty Curse, Sudden Raid, Dark Harmony, Claw Expert, Nightfall Signet | 쿼드 스타 보스 주력. 쇼다운은 사냥/디버프. 표식과 취약 장판으로 추가타/피해 증가. |
| 하이퍼/5차/6차 | Bleed Dart, Death Star, Throwing Star Barrage, Throw Blasting, Dark Lord's Omen, Spread Throw, Life and Death | 표창 폭격, 투사체 분산, 설치기, 6차 생사 버스트. |

### 섀도어 (Shadower)

컨셉: 단검, 메소 폭발, 다크 사이트, 암살형 근접 딜러.

| 전직 | 추가 스킬 영문명 | 한국어 설명 및 효과 태그 |
|---|---|---|
| 2차 시프 | Savage Blow, Steal, Channel Karma, Shield Mastery, Critical Edge, Dagger Mastery, Agile Daggers | 새비지 블로우 다단히트, 스틸/카르마 버프, 방패/단검 숙련. |
| 3차 시프마스터 | Meso Explosion, Pick Pocket, Midnight Carnival, Phase Dash, Shadow Partner, Dark Flare, Meso Mastery, Venom | 픽파킷으로 메소 생성, 메소 익스플로전으로 폭발, 페이즈 대시/카니발 근접 공격. |
| 4차 섀도어 | Assassinate, Cruel Stab, Blood Money, Shadower Instinct, Smokescreen, Shadow Shifter, Dagger Expert, Sudden Raid | 암살 보스 주력. 부메랑/크루얼 스탭 사냥. 블러드 머니와 스모크스크린으로 딜/유틸 강화. |
| 하이퍼/5차/6차 | Flip of the Coin, Shadow Veil, Sonic Blow, Trickblade, Shadow Assault, Slash Shadow Formation, Halve Cut | 코인 버프, 베일 장판, 빠른 난무/순간 이동 베기, 6차 절단기. |

### 듀얼블레이드 (Dual Blade)

컨셉: 단검+카타라, 짧은 쿨타임 공격기, 회피/무적/연속 베기에 강한 특수 모험가 도적.

| 전직 | 추가 스킬 영문명 | 한국어 설명 및 효과 태그 |
|---|---|---|
| 1차/1차+ | Bandit Slash, Tornado Spin, Katara Mastery, Self Haste | 기본 베기, 회전 돌진, 카타라 숙련, 자체 속도 버프. |
| 2차/2차+ | Slash Storm, Fatal Blow, Flying Assaulter, Flashbang, Katara Booster, Channel Karma, Venom | 폭풍 베기, 낙하/돌진, 섬광 디버프, 카타라 공속/공격력 버프. |
| 3차 | Bloody Storm, Blade Ascension, Chains of Hell, Mirror Image, Shadow Meld, Life Drain, Advanced Dark Sight | 미러 이미지로 공격 복제, 체인/승천 베기, 흡혈, 다크 사이트 강화. |
| 4차 | Phantom Blow, Blade Fury, Final Cut, Mirrored Target, Thorns, Sharpness, Katara Expert, Sudden Raid | 팬텀 블로우 보스 주력. 블레이드 퓨리 사냥. 파이널 컷은 버프/무적 성격. |
| 하이퍼/5차/6차 | Asura's Anger, Blade Clone, Blade Tempest, Haunted Edge, Blade Tornado, Karma Blade | 아수라 채널링, 칼날 분신, 토네이도/폭풍, 카르마 기반 6차 베기. |

## 해적 계열

### 바이퍼 (Buccaneer)

컨셉: 너클, 바다뱀/서펜트 에너지, 근접 난타와 변신형 버프를 사용하는 해적.

| 전직 | 추가 스킬 영문명 | 한국어 설명 및 효과 태그 |
|---|---|---|
| 2차 인파이터 | Static Thumper, Sea Serpent, Dark Clarity, Perseverance, HP Boost, Knuckle Mastery, Agile Knuckles | 정전기/서펜트 공격 시작, 공격력/체력/너클 숙련 패시브. |
| 3차 버커니어 | Turning Kick, Corkscrew Blow, Serpent Scale, Greater Sea Serpent I, Precision Strikes, Groggy Mastery, Roll of the Dice | 근접 타격과 돌진, 서펜트 강화, 보스/디버프 대상 크리 보정, 주사위 버프. |
| 4차 바이퍼 | Octopunch, Hook Bomber, Raging Serpent Assault, Sea Serpent's Rage, Speed Infusion, Crossbones, Time Leap, Double Down | 옥토펀치 보스 주력. 훅 봄버 사냥. 스피드 인퓨전/타임 리프로 파티 유틸. |
| 하이퍼/5차/6차 | Stimulating Conversation, Serpent Spirit, Lightning Form, Lord of the Deep, Howling Fist, Serpent Vortex, Liberate Neptunus | 서펜트/번개 변신, 심해 오라, 큰 한 방 펀치, 6차 해신 해방. |

### 캡틴 (Corsair)

컨셉: 총, 소환수 선원, 설치 포대, 빠른 사격과 소환 지속 시간에 특화된 해적.

| 전직 | 추가 스킬 영문명 | 한국어 설명 및 효과 태그 |
|---|---|---|
| 2차 건슬링거 | Rapid Blast, Swift Fire, Recoil Shot, Scurvy Summons, Wings, Infinity Blast, Gun Mastery, Agile Guns | 빠른 사격과 반동 이동, 선원 소환, 총 숙련/공속. |
| 3차 발키리 | Blunderbuster, Blackboot Bill, Siege Bomber, Cross Cut Blast, All Aboard, Outlaw's Code, Roll of the Dice | 산탄/포격, 설치 폭격, 선원 강화, 주사위 버프. |
| 4차 캡틴 | Rapid Fire, Brain Scrambler, Eight-Legs Easton, Broadside/Tempest Bombardment, Jolly Roger, Ahoy Mateys, Parrotargetting, Majestic Presence | 래피드 파이어/브레인 스크램블러 보스 주력. 브로드사이드 설치 포대와 선원 버프. |
| 하이퍼/5차/6차 | Whaler's Potion, Ugly Bomb, Bullet Barrage, Target Lock, Nautilus Assault, Death Trigger, The Dreadnought | 탄막, 조준 폭격, 노틸러스 강습, 드레드노트 6차 포격. |

### 캐논슈터/캐논마스터 (Cannoneer)

컨셉: 핸드캐논, 느리지만 큰 범위와 강한 한 방, 원숭이 소환/보조가 특징인 특수 모험가 해적.

| 전직 | 추가 스킬 영문명 | 한국어 설명 및 효과 태그 |
|---|---|---|
| 1차 | Cannon Blaster, Cannon Strike, Cannon Leap, Cannon Jump, Blast Back, Cannon Boost | 핸드캐논 기본 공격, 포격 이동, 후퇴 이동, 공격력 패시브. |
| 2차 | Scatter Shot, Barrel Bomb, Cannon Crash, Monkey Magic, Cannon Mastery, Cannon Booster, Critical Fire, Pirate Training | 산탄/폭탄/충돌 공격, 원숭이 버프, 캐논 숙련/크리 패시브. |
| 3차 | Cannon Spike, Monkey Mortar, Monkey Fury, Cannon-Proof, Reinforced Cannon, Counter Crush, Roll of the Dice | 포탄 난사, 원숭이 박격포, 피해 증가 디버프, 방어/반격 패시브. |
| 4차 | Cannon Bazooka, Cannon Barrage, Support Monkey, Anchors Aweigh, Nautilus Strike, Mega Monkey Magic, Cannon Overload, Pirate's Spirit | 바주카 사냥, 배러지 보스, 원숭이 지원/닻 설치, 캐논 오버로드로 최종 강화. |
| 하이퍼/5차/6차 | Buckshot, Rolling Rainbow, ICBM, Poolmaker, Monkey Business, Cannon of Mass Destruction, Full Metal Jacket | 산탄화, 설치 레이저, 미사일, 보급 생성, 대형 캐논 6차 극딜. |

## Kaling-Bot 데이터화 제안

이 문서를 곧바로 데이터에 넣는다면 다음처럼 변환하는 것이 좋다.

1. 직업 트리는 `parent_id`로 연결한다.
2. 각 스킬은 "가장 낮은 기준 직업"에 매단다. 예를 들어 히어로 2차 스킬은 파이터 기준, 4차 스킬은 히어로 기준.
3. 스킬 효과는 원작 계수를 그대로 쓰지 말고 Kaling-Bot의 기존 효과 타입으로 환산한다.
4. 추천 매핑:
   - 주력 공격기: `damage_multiplier`, `hits`, `cooldown`
   - 추가타/분신/파이널 어택: `post_attack_ability_damage` 또는 별도 추격류 효과
   - 버프: `stat_effects`, `special effects`
   - 디버프: `enemy_stat_effects`, `effect_actions`
   - 보호/무적/가드: `damage_cut`, 별도 생존 버프
   - 소환/설치: 지속 턴이 있는 자동 피해 효과로 별도 모델링 권장
5. 원작의 5차/6차는 강한 쿨기와 특수기 중심이라, Kaling-Bot에서는 초반에는 하이퍼 이후 확장 컨텐츠로 빼는 편이 안전하다.

## 빠른 구현 우선순위

1. 초보자, 1차 공통, 2차 대표 직업만 먼저 구현한다.
2. 히어로, 비숍, 나이트로드, 바이퍼처럼 역할이 뚜렷한 4개 직업을 먼저 샘플 완성한다.
3. 이후 같은 계열 직업을 복제/변형한다.
4. 원작명은 flavor로 남기되, 실제 밸런스는 Kaling-Bot 전투 시스템 기준으로 새로 잡는다.
