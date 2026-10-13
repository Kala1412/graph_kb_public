import datetime
import json
import re
from collections import OrderedDict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    MedicalProfileRecordSource,
    MedicalProfileRecordType,
    UserMedicalProfileRecord,
)


# 统一医疗档案分类、模型输出解析、去重写入与提示词摘要。


# 保持分类顺序稳定，供前端标签和医疗画像摘要复用。
MEDICAL_PROFILE_RECORD_TYPE_LABELS = OrderedDict(
    [
        (MedicalProfileRecordType.ALLERGY, "过敏史"),
        (MedicalProfileRecordType.DISEASE, "疾病"),
        (MedicalProfileRecordType.SYMPTOM, "症状"),
        (MedicalProfileRecordType.HISTORY, "既往史"),
        (MedicalProfileRecordType.CONSTITUTION, "体质"),
        (MedicalProfileRecordType.MEDICATION, "用药"),
        (MedicalProfileRecordType.OTHER, "其他"),
    ]
)


# 合法来源集合：
# - manual: 用户在个人中心里手动维护
# - chat_import: 系统从聊天内容中自动抽取并导入
# - migration: 旧版本数据迁移过来
MEDICAL_PROFILE_RECORD_SOURCES = {
    MedicalProfileRecordSource.MANUAL,
    MedicalProfileRecordSource.CHAT_IMPORT,
    MedicalProfileRecordSource.MIGRATION,
}


MEDICAL_PROFILE_RECORD_TYPES = set(MEDICAL_PROFILE_RECORD_TYPE_LABELS.keys())


def normalize_record_type(value: str | None) -> str:
    # 4. 如果不是合法分类，自动降级为 other
    # 比如大模型偶尔输出了未知分类，不至于让整次病状抽取失败。
    raw = str(value or "").strip().lower()
    return raw if raw in MEDICAL_PROFILE_RECORD_TYPES else MedicalProfileRecordType.OTHER


def normalize_record_source(value: str | None) -> str:
    # 如果来源不合法，默认回退成 manual，保证数据仍可落库。
    raw = str(value or "").strip().lower()
    return raw if raw in MEDICAL_PROFILE_RECORD_SOURCES else MedicalProfileRecordSource.MANUAL


def split_legacy_medical_facts(text: str | None) -> list[str]:
    # 按分号或换行拆分旧 medical_facts 字段，供迁移和兼容使用。
    parts = re.split(r"[；;\n\r]+", str(text or ""))
    return [part.strip() for part in parts if part and part.strip()]


def parse_extracted_medical_profile_records(raw_text: str) -> list[dict[str, str]]:
    # 解析模型输出为 record_type/content 列表，校验并去重。

    cleaned = str(raw_text or "").strip()
    # 模型明确返回 NONE，表示这轮对话里没有值得长期保存的病状信息。
    if not cleaned or cleaned.upper() == "NONE":
        return []

    payload: Any = None
    try:
        payload = json.loads(cleaned)
    except Exception:
        # 现实里模型有时会输出“说明文字 + JSON”。
        # 所以这里尝试从整段文本中把中间那段数组抠出来再解析。
        match = re.search(r"(\[[\s\S]*\])", cleaned)
        if match:
            payload = json.loads(match.group(1))

    if not isinstance(payload, list):
        return []

    results: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue

        content = str(item.get("content") or "").strip()
        if not content:
            continue

        record_type = normalize_record_type(item.get("record_type"))
        pair = (record_type, content)

        # 对单次抽取结果内部先做一轮去重，
        # 防止模型自己输出两条完全相同的病状事实。
        if pair in seen:
            continue

        seen.add(pair)
        results.append({"record_type": record_type, "content": content})

    return results


async def upsert_medical_profile_record(
    db: AsyncSession,
    user_id: int,
    record_type: str,
    content: str,
    source: str,
) -> tuple[UserMedicalProfileRecord, bool]:
    # 按用户、分类、内容去重写入；返回最终记录与是否新建的标记。
    normalized_type = normalize_record_type(record_type)
    normalized_source = normalize_record_source(source)
    normalized_content = str(content or "").strip()

    # 三元组唯一性允许同一用户维护多条不同事实。
    stmt = select(UserMedicalProfileRecord).where(
        UserMedicalProfileRecord.user_id == user_id,
        UserMedicalProfileRecord.record_type == normalized_type,
        UserMedicalProfileRecord.content == normalized_content,
    )
    existing_records = (await db.execute(stmt)).scalars().all()

    if existing_records:
        # 兼容历史重复数据，保留最近更新的记录。
        existing_records = sorted(
            existing_records,
            key=lambda item: (
                getattr(item, "updated_at", None) or getattr(item, "created_at", None) or datetime.datetime.min,
                getattr(item, "id", 0),
            ),
            reverse=True,
        )

        # 保留最近更新的一条作为主记录。
        primary = existing_records[0]

        # 命中已有事实时仍更新来源，以本次写入为准。
        primary.source = normalized_source
        primary.updated_at = datetime.datetime.utcnow()

        # 其余重复项全部删掉，避免脏数据继续留在库里。
        for duplicate in existing_records[1:]:
            await db.delete(duplicate)

        return primary, False

    record = UserMedicalProfileRecord(
        user_id=user_id,
        record_type=normalized_type,
        content=normalized_content,
        source=normalized_source,
    )
    db.add(record)

    # flush 提前取得记录 ID，供调用方写审计日志。
    await db.flush()
    return record, True


def aggregate_medical_profile_records(records: list[UserMedicalProfileRecord]) -> str:
    # 按分类聚合结构化记录，为 Agent 提供紧凑的长期画像摘要。
    grouped: OrderedDict[str, list[str]] = OrderedDict(
        (record_type, []) for record_type in MEDICAL_PROFILE_RECORD_TYPE_LABELS.keys()
    )

    # 先按最近更新时间倒序，让最近维护过的病状信息优先出现。
    sorted_records = sorted(
        records,
        key=lambda item: (
            getattr(item, "updated_at", None) or getattr(item, "created_at", None) or datetime.datetime.min
        ),
        reverse=True,
    )

    seen: set[tuple[str, str]] = set()
    for record in sorted_records:
        # 再做一遍归一化和空值清洗，防止脏数据污染最终提示词。
        record_type = normalize_record_type(getattr(record, "record_type", None))
        content = str(getattr(record, "content", "") or "").strip()
        if not content:
            continue

        pair = (record_type, content)
        # 聚合时也要去重，避免重复病状被多次拼进 user_profile。
        if pair in seen:
            continue

        seen.add(pair)
        grouped.setdefault(record_type, []).append(content)

    segments = []
    for record_type, label in MEDICAL_PROFILE_RECORD_TYPE_LABELS.items():
        values = grouped.get(record_type) or []
        if values:
            # 同一分类下多条内容用中文分号拼接；
            # 不同分类之间也用中文分号拼接，保持输出风格统一。
            segments.append(f"{label}: {'；'.join(values)}")

    return "；".join(segments)
