from __future__ import annotations

import re
from typing import Any


_WSE_TOKENS = ("무기", "보조무기", "엠블렘", "앰블렘")


def summarize_equipment(
    equip_payload: dict[str, Any], character_name: str, requested_slots: tuple[str, ...] = ()
) -> list[str]:
    items = equip_payload.get("item_equipment", [])
    if not isinstance(items, list):
        return []

    indexed_items = [(idx, item) for idx, item in enumerate(items) if isinstance(item, dict)]
    indexed_items.sort(
        key=lambda pair: _slot_sort_key(
            str(pair[1].get("item_equipment_slot") or ""), pair[0]
        )
    )
    sorted_items = [item for _, item in indexed_items]
    normalized_requested = _normalize_requested_slots(requested_slots)
    filtered_items = [
        item for item in sorted_items if _matches_requested_slot(item, normalized_requested)
    ]
    if not filtered_items:
        return []

    main_stat, power_token = _pick_effective_stats(sorted_items)
    item_lines: list[str] = [
        f"{character_name} 장비 잠재 요약",
        f"유효 주스탯: {main_stat} / 유효 공마: {power_token}",
    ]

    for item in filtered_items:
        item_name = str(item.get("item_name") or "알 수 없는 장비")
        item_slot = str(item.get("item_equipment_slot") or "기타")
        slot_key = _normalize_slot_name(item_slot)
        starforce = str(item.get("starforce") or "0")
        is_wse = any(token in slot_key for token in _WSE_TOKENS)
        is_glove = slot_key == "장갑"

        upper_grade = str(item.get("potential_option_grade") or "-")
        lower_grade = str(item.get("additional_potential_option_grade") or "-")

        upper_options = [
            str(item.get("potential_option_1") or ""),
            str(item.get("potential_option_2") or ""),
            str(item.get("potential_option_3") or ""),
        ]
        lower_options = [
            str(item.get("additional_potential_option_1") or ""),
            str(item.get("additional_potential_option_2") or ""),
            str(item.get("additional_potential_option_3") or ""),
        ]

        if is_wse:
            upper_text = _format_wse_slots(_collect_wse_slots(upper_options, power_token))
            lower_text = _format_wse_slots(_collect_wse_slots(lower_options, power_token))
        else:
            upper_text = _format_normal_row(
                _collect_normal_row(upper_options, main_stat, power_token, is_glove),
                power_token,
                is_glove,
            )
            lower_text = _format_normal_row(
                _collect_normal_row(lower_options, main_stat, power_token, is_glove),
                power_token,
                is_glove,
            )

        line_parts = [f"- ({item_slot}) {item_name}"]
        if starforce != "0":
            line_parts.append(f"{starforce}성")
        if upper_grade != "-":
            line_parts.append(f"윗잠 {upper_grade}: {upper_text}")
        if lower_grade != "-":
            line_parts.append(f"아랫잠 {lower_grade}: {lower_text}")
        item_lines.append(" | ".join(line_parts))

    return item_lines


def _normalize_requested_slots(requested_slots: tuple[str, ...]) -> set[str]:
    return {_normalize_slot_name(slot) for slot in requested_slots if slot}


def _matches_requested_slot(item: dict[str, Any], requested_slots: set[str]) -> bool:
    if not requested_slots:
        return True
    slot_name = _normalize_slot_name(str(item.get("item_equipment_slot") or ""))
    return slot_name in requested_slots


def _normalize_slot_name(slot_name: str) -> str:
    normalized = slot_name.replace(" ", "")
    normalized = normalized.replace("(", "").replace(")", "")
    normalized = re.sub(r"\d+$", "", normalized)
    return normalized


def _slot_sort_key(slot_name: str, original_index: int) -> tuple[int, int]:
    order = {
        "무기": 0,
        "보조무기": 1,
        "엠블렘": 2,
        "앰블렘": 2,
        "모자": 3,
        "상의": 4,
        "하의": 5,
        "신발": 6,
        "망토": 7,
        "장갑": 8,
        "어깨장식": 9,
        "반지": 10,
        "귀고리": 11,
        "펜던트": 12,
        "얼굴장식": 13,
        "눈장식": 14,
        "벨트": 15,
        "기계심장": 16,
        "포켓아이템": 17,
        "훈장": 18,
        "뱃지": 19,
    }
    return (order.get(_normalize_slot_name(slot_name), 999), original_index)


def _pick_effective_stats(items: list[Any]) -> tuple[str, str]:
    stat_order = ("str", "dex", "int", "luk")
    stat_values: dict[str, int] = {key: 0 for key in stat_order}
    for item in items:
        if not isinstance(item, dict):
            continue
        total = item.get("item_total_option")
        if not isinstance(total, dict):
            continue
        for key in stat_order:
            raw = str(total.get(key, "0")).replace(",", "")
            try:
                stat_values[key] += int(raw)
            except ValueError:
                continue

    main_key = max(stat_order, key=lambda key: stat_values[key])
    power_token = "마력" if main_key == "int" else "공격력"
    return main_key.upper(), power_token


def _collect_normal_row(
    options: list[str], main_stat: str, power_token: str, is_glove: bool
) -> dict[str, int]:
    row = {"crit_dmg_pct": 0, "stat_pct": 0, "power_pct": 0, "power_flat": 0}
    for line in options:
        if not line:
            continue
        if is_glove:
            row["crit_dmg_pct"] += _extract_percent(line, "크리티컬 데미지")
        row["stat_pct"] += _extract_percent(line, main_stat)
        row["stat_pct"] += _extract_percent(line, "올스탯")
        row["power_pct"] += _extract_percent(line, power_token)
        row["power_flat"] += _extract_flat(line, power_token)
    return row


def _collect_wse_slots(options: list[str], power_token: str) -> list[tuple[str, str]]:
    slots: list[tuple[str, str]] = []
    for line in options:
        slots.append(_classify_wse_option(line, power_token))
    while len(slots) < 3:
        slots.append(("X", "X"))
    return slots[:3]


def _extract_percent(line: str, token: str) -> int:
    match = re.search(rf"{re.escape(token)}\s*\+\s*(\d+)\s*%", line)
    return int(match.group(1)) if match else 0


def _extract_flat(line: str, token: str) -> int:
    match = re.search(rf"{re.escape(token)}\s*\+\s*(\d+)(?!\s*%)", line)
    return int(match.group(1)) if match else 0


def _format_wse_slots(slots: list[tuple[str, str]]) -> str:
    codes = "/".join(code for code, _ in slots)
    values = "/".join(value for _, value in slots)
    return f"{codes} <{values}>"


def _classify_wse_option(line: str, power_token: str) -> tuple[str, str]:
    if not line:
        return ("X", "X")
    normalized = line.replace(" ", "")

    boss = re.search(r"보스몬스터데미지\+(\d+)%", normalized)
    if boss:
        return ("보", boss.group(1))

    ied = re.search(r"몬스터방어율무시\+(\d+)%", normalized)
    if ied:
        return ("방", ied.group(1))

    power_pct = re.search(rf"{re.escape(power_token)}\+(\d+)%", normalized)
    if power_pct:
        return (("마" if power_token == "마력" else "공"), power_pct.group(1))

    dmg = re.search(r"데미지\+(\d+)%", normalized)
    if dmg:
        return ("뎀", dmg.group(1))

    return ("X", "X")


def _format_normal_row(row: dict[str, int], power_token: str, is_glove: bool) -> str:
    parts: list[str] = []
    if is_glove and row.get("crit_dmg_pct", 0) > 0:
        parts.append(f"크뎀 {row['crit_dmg_pct']}%")
    if row["stat_pct"] > 0:
        if is_glove:
            parts.append(f"주스탯 {row['stat_pct']}%")
        else:
            parts.append(f"{row['stat_pct']}%")
    if row["power_pct"] > 0:
        parts.append(f"{power_token} {row['power_pct']}%")
    if row["power_flat"] > 0:
        parts.append(f"{power_token} +{row['power_flat']}")
    return ", ".join(parts) if parts else "없음"
