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
- Preserve all formatting, HTML tags, attributes, variables, IDs, placeholders, and special characters.
- Preserve every line break and blank line in its original position.
- Do not translate filenames.
- Preserve metadata keys exactly, including scan_title, scan_image, and scan_sector.
- Do not change the value of scan_image.
- Translate player-facing metadata values, titles, headings, and paragraphs into Japanese.
- Do not translate text enclosed in parentheses such as (ITEM), (S), and (Doc).
- Use natural Japanese suitable for a science fiction space simulation game.
- Keep terminology consistent across all files.
- Preserve semicolons that are part of the file structure. Do not add semicolons to translated prose.
- Return the complete translated file, including metadata lines.
- Output only the translated content.
- Do not add explanations or comments.

Terminology:
Ship = 艦船
Cargo = 貨物
Station = ステーション
Sector = セクター
Faction = 勢力
Contract = 契約
<<<end