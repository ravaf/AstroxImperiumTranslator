# Script Translation for Astrox Imperium

This project provides a Python script to automate the translation of game files for the game Astrox Imperium. It uses a configurable AI language model to translate text found in various game files, primarily focusing on `.txt` files that contain HTML-like content or follow a CSV structure.

## Features

-   Translates text content from game files into a specified language.
-   Handles different file formats, including files with HTML-style tags and complex CSV files.
-   Configurable AI model endpoint and API key via an `.env` file.
-   Saves translation progress in `progress.json` to avoid re-processing files.
-   Caches translated strings in `dictionary.json` to reduce redundant API calls.
-   Allows interactive selection of specific save game folders for translation.

## Requirements

-   Python 3.x
-   The dependencies listed in `requirements.txt`:
	-   `pandas`
	-   `pick`
	-   `aiohttp`
	-   `tqdm`
	-   `python-dotenv`

## Setup

1.  **Clone the repository:**
	```bash
	git clone https://github.com/danielvscs/AstroxImperiumTranslator.git
	cd AstroxImperiumTranslator
	```

2.  **Install dependencies:**
	```bash
	pip install -r requirements.txt
	```

3.  **Configure environment variables:**
	Create a `.env` file in the root of the project by copying the `.env.example` file.

	```bash
	copy .env.example .env
	```

	Edit the `.env` file with your specific configuration:

	-   `MOD_PATH`: The absolute path to your mod's folder within the Astrox Imperium game data. For example: `C:\...\Astrox Imperium\Astrox Imperium_Data\MOD_NAME`.
	-   `API_KEY`: Your API key for the translation service you are using (e.g., OpenAI, Google Gemini).
	-   `ENDPOINT_AI`: The base URL (endpoint for cURL) for the AI provider's chat completions API.
	-   `HIGH_MODEL` / `MIDDLE_MODEL`: The specific model names you want to use for different translation tasks.

## Usage

1. **Set system instructions:**

	Edit `instructions.md`
	**Consider these guidelines for writing the instruction:**

	* **Format Preservation:** It is strictly required to preserve any special formatting present within the text, as the dialogue engine is highly sensitive to changes.
	* **Non-Translation Rule:** Do not translate file names or specific text tokens such as `lorem_ipsum` or `lorem_ipsum.txt`.
	* **Goal:** Translate the visible player-facing text within a provided HTML document.
	* **Code Preservation:** Exactly the same HTML code structure must be maintained. Only the visible text should be modified. File names, variables, embedded formats, and other code elements must remain intact.
	* **Token Preservation:** Any text enclosed in parentheses (e.g., `(ITEM)`, `(S)`, `(Doc)`) must remain untranslated.
	* **Output Format:** The response must solely consist of the translated HTML text, with no additional comments or surrounding text.


	* **Forbidden Character (only csv):** Absolutely do not use the semicolon (`;`).

2.  **Run the script:**
	```bash
	python translator.py
	```

3.  **Select Save Folders:**
	The script will scan the `saves` directory inside your `MOD_PATH` and prompt you to select which save folders you want to translate. Use the `space` key to select and `enter` to confirm.

4.  **Translation Process:**
	The script will then iterate through the files in the specified directories. It reads the content, sends it to the AI for translation based on the rules defined, and saves the translated content back to the files or a progress log.

## Explanation of `CSV_RULES`

The `CSV_RULES` dictionary, located in `translator.py`, is crucial for correctly extracting text from the game's various `.txt` files that are structured like CSVs (using `;` as a delimiter).

-   **What it is:** `CSV_RULES` is a dictionary where keys are partial file paths and values are the rules for how to extract translatable text from those files.

-   **How it works:** When the script processes a file, it checks if the file's path matches any key in `CSV_RULES`. If a match is found, it applies the corresponding extraction rule.

### Rule Types

1.  **`ROW:ID`**
	-   **Example:** `["ROW:EVENT", [2, 12]]`
	-   **Explanation:** This rule applies to rows where the first value (column 0) is exactly `EVENT`. For each such row, it extracts the text from columns 2 and 12 for translation.

2.  **`ROWS:ID1|ID2`**
	-   **Example:** `['ROWS:STRUCTURE|desc', [2]]`
	-   **Explanation:** This rule applies to rows where the first two columns are `STRUCTURE` and `desc`, respectively. It then extracts the text from the 3rd column (index 2).

3.  **`COLUMN:HEADER`**
	-   **Example:** `["COLUMN:VALUE 1", "stop_value:null", 'codiction:COMMAND|IN|["TEXT", "OPTION", ...]`
	-   **Explanation:** This is a more complex rule for files where translatable text appears in a sequence down a column.
		-   `COLUMN:VALUE 1`: It finds the column named `VALUE 1`.
		-   `codiction:...`: It applies a filter. In this case, it only processes rows where the value in the `COMMAND` column is one of the specified values (like `TEXT`, `OPTION`, etc.).
		-   It then reads all values in the `VALUE 1` column and subsequent columns until it hits a value specified by `stop_value:null`.

These rules allow the script to precisely target only the text that needs translation, avoiding fixed game data, IDs, or script commands.

### Note
-   うまく動作しなかったため、Google公式の google-genai SDK（google-genai パッケージ）を使用した動作に書き換えました。
	```bash
	pip install google-genai pydantic
	```
-   Google AI Studio のAPIキーを取得し、`.env`ファイルに設定してください。
-   MODフォルダは、`MOD_JAPANESE` として実行結果をいれてありますが、テキストのみとなっています。
	- 翻訳結果のみを利用した場合は、MODフォルダをコピーして、`MOD_JAPANESE` をコピーしたMODフォルダに上書きしてください。
	- 個人利用を目的として作成したものであるため、何かしらの不都合があった場合は公開停止する場合があります。ご了承ください。
-   Build 0.0158 日本語化の実行結果として、`dictionary.json`,`progress.json`,`text_list.json`が生成されています。再度翻訳を行う際には、これらのファイルを削除してから実行してください。
-   ゲームでのMOD適用は、`MOD TOOLS` -> `MOD MANAGER` -> AVAILABLE MODSから `MOD_JAPANESE` を選択して、CONFIRM CHANGEを押すことで適用されます。