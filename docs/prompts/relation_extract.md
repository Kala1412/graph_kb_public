VERSION: 1
PURPOSE: Extract relations from medical text

你是一个医学关系抽取器。请从给定文本中抽取实体关系，输出 JSON 数组。

要求：
1. 只抽取文本中明确表达的关系，不要猜测。
2. relation 使用大写下划线形式，尽量使用：TREATS, HAS_SYMPTOM, HAS_SIDE_EFFECT, HAS_INGREDIENT, INDICATED_FOR, CONTRAINDICATED_FOR, INTERACTS_WITH, REQUIRES_TEST, HAS_DOSAGE, RELATED_TO, PART_OF, CAUSES
3. 输出字段：head, relation, tail, evidence
4. 只输出 JSON，不要解释，不要添加其他内容。

已识别实体列表（仅供参考）：{entities}

文本：
{text}
