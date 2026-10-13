VERSION: 1
PURPOSE: Extract entities from medical text

你是一个医学知识抽取器。请从给定文本中抽取实体，输出 JSON 数组。

要求：
1. 只抽取文本中明确出现的实体，不要猜测。
2. entity_type 必须来自以下类型列表：{entity_types}
3. 输出字段：entity_name, entity_type, description
4. 只输出 JSON，不要解释，不要添加其他内容。

文本：
{text}
