# RPG Content

RPG 운영 데이터는 이 폴더에서 수정합니다.

- `settings.json`: 탐색 제한, 장착 수, 강화 최대치, 승리/패배 보상 배율 같은 전역 설정
- `stats.json`: 스탯 표시 순서와 라벨
- `rarities.json`: 등급 라벨, 색상, 가격/강화 비용 계수
- `level_curve.json`: 다음 레벨까지 필요한 누적 경험치 커브. `base + linear*n + quadratic*n^2 + cubic*n^3`이며 `n = 현재 레벨 - 1`
- `player.json`: 신규 유저 시작값
- `stat_allocation.json`: 예전 스탯 투자 규칙 호환용 파일. 현재 레벨업 스탯 성장은 자동 적용됩니다.
- `enhancement.json`: 강화 배율, 확률, 판매율
- `items.json`: 장비 목록
- `materials.json`: 제작 재료 목록
- `crafting_recipes.json`: 제작법 목록
- `jobs.json`: 직업/전직 데이터
- `skills.json`: 어빌리티 데이터
- `stack_effects.json`: 스택형 버프/디버프 정의
- `dungeons/*.json`: 던전, 몬스터, 탐색 보상
- `bosses/*.json`: 보스, 전조, CT, 보스 보상

보스나 던전을 추가할 때는 새 JSON 파일을 만들고 `id`를 고유하게 지정하세요. 화면 표시 순서는 `sort_order`가 낮을수록 먼저 나옵니다.

전투 특수 효과는 장비 `effects`, 스킬 `player_effects`/`enemy_effects`, 보스 전조 실패 효과의 `player_effects`/`boss_effects`에 설정합니다. `duration`을 `-1`로 두면 무한 지속입니다.
`invulnerability`는 지속 중 일반 피해와 방어 무시 무속성 피해를 모두 0으로 만듭니다. 예: `{"invulnerability": {"duration": 1, "undispellable": true}}`.
스킬의 `self_hp_cost`는 `max_hp_ratio`, `current_hp_ratio`, `set` 모드를 지원하며 `minimum_hp` 아래로는 소모하지 않습니다. 비용은 어빌리티 재발동 횟수와 무관하게 한 번만 지불합니다.
`hp_scaled_damage: true`인 스킬은 HP 비용을 지불한 뒤의 HP로 공격력·혼신·배수·데미지 증가를 계산하고, 여기에 스킬 데미지를 함께 적용합니다. 기존 스킬 공식은 기본값 `false`를 유지합니다.
스킬의 `hp_variants`는 `self_hp_cost`를 지불한 뒤의 HP 비율로 한 번만 선택합니다. `max_hp_ratio` 이하에서 `damage_multiplier`/`hits`를 교체하고, 스탯·특수 효과·즉시 효과를 기본 스킬에 더합니다. 선택된 변형은 같은 입력에서 발생한 모든 어빌리티 재발동에 동일하게 적용됩니다.
디스펠/클리어 올은 `effect_actions`에 설정하고, 전조는 `turns`로 제한 턴을 지정합니다.
스택형 버프/디버프는 `stack_effects.json`에 정의하고, 스킬/보스 패턴의 `effect_actions`에서 스택 증가, 감소, 지정, 제거, 최대화, 순환 액션으로 조작합니다. `stack_cycle`은 0에서 1로 시작해 최대 단계까지 오른 뒤 1로 돌아옵니다. 재발동에서 반복하면 안 되는 전환·소모 액션은 `repeat_on_recast: false`로 지정합니다.
`effect_actions`의 각 액션에는 `conditions`로 특정 스택의 최소/최대 조건을 붙일 수 있으며, 조건을 모두 만족할 때만 해당 액션이 실행됩니다.
스택 자동 조건은 전조 조건과 같은 이벤트 이름을 쓰며, `warning_success`/`warning_failure`로 전조 성공/실패도 처리할 수 있습니다. `turn_end`는 상대 행동이 끝나고 생존한 경우에만 발생하며 `min_hp_ratio`/`max_hp_ratio`로 해당 시점 HP를 제한할 수 있습니다.
전조 실패 효과에는 일반 배율 피해와 별도로 `plain_damage`를 둘 수 있습니다. `{"mode": "flat", "value": 500}`은 고정 무속성 데미지, `{"mode": "target_max_hp_ratio", "value": 0.1}`은 대상 최대 HP 10% 무속성 데미지입니다.
전조의 `failure_variants`는 스택 조건을 만족할 때 기본 실패 효과 대신 실행되는 조건부 실패 효과입니다.
보스의 `hp_effects`는 턴 시작 시 해당 HP 이하로 처음 내려갔을 때 즉시 실행되는 효과입니다. 한 효과에 `thresholds`로 여러 HP 임계값을 둘 수 있습니다. 한 번에 여러 조건을 넘기면 가장 낮은 HP 조건 하나만 실행되고, 나머지 넘긴 조건은 지나간 것으로 처리됩니다. `thresholds: [1]`은 보스전 시작 직후 실행됩니다.
보스의 `hp_locks`는 HP가 해당 비율 미만으로 내려가지 않게 막는 참전자별 기준선입니다. 예: `[0.8, 0.2]`는 각 참전자 기준으로 80%, 20%에서 한 턴 동안 HP를 멈추고 다음 턴부터 해당 락을 해제합니다.
하드 모드는 `hard_mode.warning_overrides`에서 전조 ID별 `objectives`, `turns`, `pattern`, `success_pattern`, `failure_variants`를 직접 덮어쓸 수 있습니다. `pattern_overrides`는 독립 패턴 ID를, `hp_effect_overrides`는 HP 즉시 효과의 패턴 ID를, `stack_effect_id_overrides`는 하드 전용 스택 효과 ID를 치환합니다. `hp_warnings`, `hp_effects`, `hp_locks`, `ct`, `stack_effects`도 하드 모드에 직접 지정할 수 있습니다. 공통 배율보다 보스별 `stats`, 전조 목표, 패턴 피해를 명시적으로 설계하고 `balance_notes`에 의도를 기록하세요.

`life_steal`은 입힌 실제 피해의 비율만큼 회복하는 생명력 흡수 스탯입니다. 생명력 흡수 스탯 효과나 직접 회복 스킬에는 `heal_cap`을 붙일 수 있습니다. 예: `{"mode": "flat", "value": 1000}` 또는 `{"mode": "max_hp_ratio", "value": 0.01}`.
직업도 장비처럼 `stat_effects`와 `effects`를 가질 수 있으며, 전투 시작 시 현재 직업 체인의 모든 영속 효과가 적용됩니다.
직업의 `initial_stack_effects`에는 전투 시작 스택 ID와 수량을 지정합니다. `low_hp_cooldown`은 저HP 턴 종료의 직업 어빌리티 추가 쿨타임 감소를 정의하며, `disabled_at_stack_effect_id`/`disabled_at_stacks`로 특정 위험 단계에서 가속을 막을 수 있습니다. 사용 횟수 제한은 이 쿨타임 감소로 복구되지 않습니다.
