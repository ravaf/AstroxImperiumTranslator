---csv
Translate all player-facing text into Japanese.

Rules:
- Preserve all formatting, HTML tags, variables, IDs, placeholders, and special characters.
- Do not translate filenames.
- Do not translate text enclosed in parentheses such as (ITEM), (S), and (Doc).
- Use natural Japanese suitable for a science fiction space simulation game.
- Keep terminology consistent across all files.
- Output only the translated content.
- Do not add explanations or comments.
- Never use semicolons (;).
- Return valid JSON in the required format: {"translation":[{"id":1,"text":"翻訳文"}]}.
- Preserve each input item's id and return one translated item for each input item.

Terminology:
Ship = 艦船
Cargo = 貨物
Station = ステーション
Sector = セクター
Faction = 勢力
Contract = 契約
<<<end

---html
Translate all player-facing text into Japanese.

Rules:
- Preserve HTML tags, attributes, variables, placeholders, IDs, and special characters.
- Do not translate filenames.
- Do not translate text enclosed in parentheses such as (ITEM), (S), and (Doc).
- Use natural Japanese suitable for a science fiction space simulation game.
- Keep terminology consistent across all files.
- Output only the translated content.
- Do not add explanations or comments.
- Never use semicolons (;).

Terminology:
Ship = 艦船
Cargo = 貨物
Station = ステーション
Sector = セクター
Faction = 勢力
Contract = 契約
<<<end