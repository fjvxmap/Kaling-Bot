# RPG Content

RPG 운영 데이터는 이 폴더에서 수정합니다.

- `settings.json`: 탐색 제한, 장착 수, 강화 최대치 같은 전역 설정
- `stats.json`: 스탯 표시 순서와 라벨
- `rarities.json`: 등급 라벨, 색상, 가격/강화 비용 계수
- `player.json`: 신규 유저 시작값
- `stat_allocation.json`: 스탯 포인트 투자 규칙과 선택지 이름
- `enhancement.json`: 강화 배율, 확률, 판매율
- `drop_rarity_weights.json`: 랭크별 랜덤 장비 등급 가중치
- `items.json`: 장비 목록
- `materials.json`: 제작 재료 목록
- `crafting_recipes.json`: 제작법 목록
- `jobs.json`: 직업/전직 데이터
- `skills.json`: 어빌리티 데이터
- `dungeons/*.json`: 던전, 몬스터, 탐색 보상
- `bosses/*.json`: 보스, 전조, CT, 보스 보상

보스나 던전을 추가할 때는 새 JSON 파일을 만들고 `id`를 고유하게 지정하세요. 화면 표시 순서는 `sort_order`가 낮을수록 먼저 나옵니다.
