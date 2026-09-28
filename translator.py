import os
from dotenv import load_dotenv
import re
import json
import pandas as pd
from io import StringIO
from typing import List, Dict, Optional, Any
from tqdm import tqdm
from pathlib import Path
import asyncio
import logging
from pick import pick
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

load_dotenv()

# ログ設定およびグローバル変数の初期化
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
ORIGINAL_MOD_PATH = os.path.abspath(os.getenv("MOD_PATH")) if os.getenv("MOD_PATH") else None
MOD_PATH = ORIGINAL_MOD_PATH
PROGRESS_FILE = "progress.json"
DICTIONARY_FILE = "dictionary.json"
TEXT_LIST_FILE = "text_list.json"

# JSON出力用Pydanticスキーマの定義
class TranslationItem(BaseModel):
    id: int
    text: str

class TranslationResponse(BaseModel):
    translation: List[TranslationItem]

class ApiClient:
    """Gemini API用の非同期クライアントクラス"""

    def __init__(self, config: Dict):
        self.config = config
        self.client = genai.Client(api_key=config["api_key"])
        self.semaphore = asyncio.Semaphore(1)

    async def api_call(self, model_config: Dict, text: str, instruction: str, json_output: bool = False) -> Optional[str]:
        async with self.semaphore:
            await asyncio.sleep(3)

            # GenerateContentConfig に tools=[] および AFC無効化オプションを指定
            gen_config = types.GenerateContentConfig(
                system_instruction=instruction,
                temperature=0.0,
                tools=[],  # ツール利用を明示的に空にする
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True  # 自動関数呼び出し（AFC）を無効化
                )
            )

            if json_output:
                gen_config.response_mime_type = "application/json"
                gen_config.response_schema = TranslationResponse

            try:
                response = await self.client.aio.models.generate_content(
                    model=model_config["name"],
                    contents=text,
                    config=gen_config
                )
                return response.text
            except Exception as e:
                logging.error(f"API呼び出し中に例外が発生しました: {e}")
                return None

class ConfigLoader:
    """Loads configuration from environment variables and files."""

    def __init__(self):
        self.config = {
            "api_key": os.getenv("API_KEY"),
            "model": {
                "high": {
                    "name": os.getenv("HIGH_MODEL", "gemini-3.5-flash-lite"),
                    "max_input_tokens": int(os.getenv("HIGH_MODEL_MAX_TOKENS", "2000")),
                },
                "middle": {
                    "name": os.getenv("MIDDLE_MODEL", "gemini-3.1-flash-lite"),
                    "max_input_tokens": int(os.getenv("MIDDLE_MODEL_MAX_TOKENS", "1500")),
                }
            },
            "system_instruction": self._load_instructions()
        }
        if not self.config["api_key"]:
            raise ValueError("API_KEY environment variable is not set. Ensure your .env file is correct.")

    def _load_instructions(self) -> Dict[str, str]:
        """Loads instructions from the markdown file."""
        filepath = "instructions.md"
        if not os.path.exists(filepath):
            logging.warning(f"{filepath} not found. Returning empty instructions.")
            return {}

        data = {}
        current_key = None
        current_value = []
        in_block = False
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if '//comment' in line:
                    line = line.split('//comment')[0]
                line = line.strip()
                if not line:
                    continue
                start_match = re.match(r'^---(\w+)$', line)
                if start_match:
                    if in_block and current_key:
                        data[current_key] = "\n".join(current_value).strip()
                    current_key = start_match.group(1)
                    current_value = []
                    in_block = True
                    continue
                if line == '<<<end':
                    if in_block and current_key:
                        data[current_key] = "\n".join(current_value).strip()
                    current_key = None
                    current_value = []
                    in_block = False
                    continue
                if in_block:
                    current_value.append(line)
            if in_block and current_key and current_value:
                data[current_key] = "\n".join(current_value).strip()

        return data

class ProgressManager:
    """Manages saving and loading progress in JSON."""

    def __init__(self, progress_file: str):
        self.progress_file = progress_file

    def save(self, data: Dict[str, Optional[str]]):
        """Saves the progress dictionary to a JSON file."""
        with open(self.progress_file, "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=4)
       
    def load(self) -> Dict[str, Optional[str]]:
        """Loads the progress dictionary from a JSON file."""
        if os.path.exists(self.progress_file):
            with open(self.progress_file, "r", encoding="utf-8") as fp:
                return json.load(fp)

        return {}

class FileHandler:
    """Handles file retrieval in a directory."""

    @staticmethod
    def get_files(folder_path: str, extension: str = "txt") -> List[str]:
        """Retrieves a list of files with a specific extension."""
        file_list = []
        target_suffix = f".{extension.lower()}"
        if not folder_path or not os.path.isdir(folder_path):
            logging.error(f"Invalid directory: '{folder_path}'")
            return []
        for root, _, files in os.walk(folder_path):
            for filename in files:
                if filename.lower().endswith(target_suffix):
                    absolute_path = os.path.join(root, filename)
                    file_list.append(absolute_path)
        return file_list

class Translator:
    """Main class for handling translations."""

    def __init__(self, config: Dict, progress_manager: ProgressManager, api_client: ApiClient):
        self.config = config
        self.progress_manager = progress_manager
        self.api_client = api_client
        self.all_text_list: List[str] = []

    async def html_translation(self, file_path: str) -> Optional[str]:
        """Translates files with HTML-like format."""
        logging.info(f"Processing file: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        if not content.strip():
            logging.warning(f"Empty file: {file_path}. Skipping translation.")
            return ""
        model_to_use = self.config["model"]["middle"]
        instruction_text = self.config["system_instruction"].get("html", "")
        if not instruction_text:
            logging.error("Missing 'html' instruction in instructions.md")
            return None
        logging.info(f"Sending {len(content)} characters to API for translation...")
        translated_content = await self.api_client.api_call(
            model_to_use, content, instruction_text, json_output=False
        )
        if translated_content is None:
            logging.error(f"Translation failed for {file_path}")
            return None
        logging.info(f"Translation completed for {file_path}")
        return translated_content

    def _script_texts(self, file_path: str) -> List[str]:
        """SCRIPT形式から翻訳対象の文章だけを抽出する。"""
        allowed_commands = {
            "TEXT", "OPTION", "NPC_CHAT", "NPC_ATTACK",
            "ADJ_CREDITS", "GET_DOCUMENT", "BUY_ITEM",
            "NPC_RETREAT", "MENU", "ADJ_FACTION",
        }
        texts = []

        with open(file_path, "r", encoding="utf-8", newline="") as fp:
            for row in csv.reader(fp, delimiter=";"):
                cells = [cell.strip() for cell in row]
                if len(cells) < 13 or cells[0] != "SCRIPT":
                    continue
                if cells[3] not in allowed_commands:
                    continue

                # インデックス5～12がVALUE 1～VALUE 8
                for cell in cells[5:13]:
                    if not cell or cell.lower() == "null":
                        continue

                    # 選択肢リンク: filename>id>表示文言
                    if ">" in cell:
                        label = cell.rsplit(">", 1)[-1].strip()
                        if label:
                            texts.append(label)
                    else:
                        texts.append(cell)

        return texts

    def _replace_script_texts(self, file_path: str, dictionary: Dict[str, str]) -> None:
        """翻訳辞書を使い、SCRIPT行のVALUE欄だけを書き換える。"""
        allowed_commands = {
            "TEXT", "OPTION", "NPC_CHAT", "NPC_ATTACK",
            "ADJ_CREDITS", "GET_DOCUMENT", "BUY_ITEM",
            "NPC_RETREAT", "MENU", "ADJ_FACTION",
        }
        output = []

        with open(file_path, "r", encoding="utf-8", newline="") as fp:
            for row in csv.reader(fp, delimiter=";"):
                if len(row) < 13 or row[0].strip() != "SCRIPT":
                    output.append(row)
                    continue

                cells = [cell.strip() for cell in row]
                if cells[3] not in allowed_commands:
                    output.append(row)
                    continue

                for i in range(5, 13):
                    cell = cells[i]
                    if not cell or cell.lower() == "null":
                        continue

                    if ">" in cell:
                        prefix, label = cell.rsplit(">", 1)
                        translated = dictionary.get(label.strip())
                        if isinstance(translated, str):
                            cells[i] = f"{prefix}>{translated}"
                    else:
                        translated = dictionary.get(cell)
                        if isinstance(translated, str):
                            cells[i] = translated

                output.append(cells)

        with open(file_path, "w", encoding="utf-8", newline="") as fp:
            writer = csv.writer(fp, delimiter=";", lineterminator="\n")
            writer.writerows(output)

    def csv_translation(self, file_path: str) -> Optional[str]:
        """Extracts texts from CSV files for translation."""
        relative_path = os.path.relpath(file_path, MOD_PATH).replace(os.path.sep, '/')

        # SCRIPTファイルは専用処理で抽出
        if relative_path.startswith("scripting/") and not relative_path.startswith("scripting/npcs"):
            self.all_text_list.extend(self._script_texts(file_path))
            return None

        rules = next((CSV_RULES[csvrule] for csvrule in CSV_RULES if csvrule in relative_path), None)
        if not rules:
            logging.info(f"No rule for {relative_path}")
            return None
        with open(file_path, "r", encoding="utf-8") as fp:
            csv_content = fp.read()

        column_rule = "// SCRIPT;" if rules[0][0].startswith("COLUMN:") else None

        csv_content = self._parse_csv(csv_content, column_names_start=column_rule)
        df = pd.read_csv(StringIO(csv_content), delimiter=";", skip_blank_lines=True, header=None, engine='python')
        for rule in rules:
            if rule[0].startswith("ROW:"):
                self.all_text_list.extend(self._row_csv_rule(df, rule))
            elif rule[0].startswith("COLUMN:"):
                self.all_text_list.extend(self._column_csv_rule(df, rule))
            elif rule[0].startswith("ROWS:"):
                self.all_text_list.extend(self._multi_row_rule(df, rule))
        if os.path.exists(DICTIONARY_FILE):
            with open(DICTIONARY_FILE, "r", encoding="utf-8") as fp:
                dictionary: Dict = json.load(fp)
                values_to_exclude = set(text.strip() for text in dictionary.values() if isinstance(text, str))
                self.all_text_list = [item for item in self.all_text_list if str(item).strip() not in values_to_exclude]
                self.all_text_list = [item for item in self.all_text_list if str(item)!="nan" and not re.fullmatch(r'[-\.\d+]+', str(item))]
        return None

    def _parse_csv(self, csv_content: str, column_names_start: Optional[str]) -> str:
        """Removes comments and tags from CSV content."""
        head_names = ";".join([str(i) for i in range(1, 30)]) + "\n"
        parse_output = head_names
        for line in csv_content.splitlines():
            line = line.strip()
            if column_names_start and line.startswith(column_names_start):
                parse_output += line + "\n"
                continue
            if line.startswith("//") or line.startswith("--") or line.startswith("<") or not line:
                continue
            parse_output += line + "\n"
        return parse_output

    def _row_csv_rule(self, df: pd.DataFrame, rule: List) -> List[str]:
        """Applies row rule to extract texts from CSV."""
        text_list = []
        for _, row in df.iterrows():
            row_values = row.values
            row_target = rule[0].replace("ROW:", "")
            if row_values[0] == row_target:
                for r in rule[1]:
                    if r < len(row_values):
                        text_list.append(str(row_values[r]))
        return text_list

    def _multi_row_rule(self, df: pd.DataFrame, rule: List) -> List[str]:
        """Applies multi-row rule to extract texts from CSV."""
        text_list = []
        for _, row in df.iterrows():
            row_values = row.values
            rows_target = rule[0].replace("ROWS:", "").split("|")
            if (row_values[:len(rows_target)] == rows_target).all():
                for r in rule[1]:
                    if r < len(row_values):
                        text_list.append(str(row_values[r]))
        return text_list

    def _column_csv_rule(self, df: pd.DataFrame, rule: List) -> List[str]:
        """Applies column rule to extract texts from CSV."""
        columns_names = df.iloc[1].fillna("").astype(str).tolist()
        columns_names = [_name.strip() for _name in columns_names]
        
        target_name = rule[0].replace("COLUMN:", "").strip()
        if target_name not in columns_names:
            return []
        idx_column_target = columns_names.index(target_name)
        condition_parts = rule[2].replace("codiction:", "").split("|")
        cond_name = condition_parts[0].strip()
        if cond_name not in columns_names:
            return []
        idx_column_condition = columns_names.index(cond_name)
        text_list = []
        def is_skip(row_values):
            if condition_parts[1] == "IN":
                include_values = json.loads(condition_parts[2])
                return str(row_values[idx_column_condition]).strip() not in include_values
            return False
        for _, row in df.iterrows():
            row_values = row.values
            if is_skip(row_values):
                continue
            for val in row_values[idx_column_target:]:
                val_str = str(val).strip()
                if not val_str or val_str == rule[1].replace("stop_value:", ""):
                    break
                text_list.append(val_str)
        return text_list

    def _get_chunks(self, string_list: List[str], max_characters: int) -> List[List[str]]:
        """Splits list into chunks without exceeding character limit."""
        if max_characters <= 0:
            return [string_list]
        chunks: List[List[str]] = []
        current_chunk: List[str] = []
        current_chunk_length: int = 0
        for item in string_list:
            item_length = len(item)
            if item_length > max_characters:
                logging.warning(f"Item length ({item_length}) exceeds max_characters ({max_characters}). Truncating for chunking.")
                item = item[:max_characters]
                item_length = len(item)
            if current_chunk_length + item_length <= max_characters:
                current_chunk.append(item)
                current_chunk_length += item_length
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = [item]
                current_chunk_length = item_length
        if current_chunk:
            chunks.append(current_chunk)
        return chunks

    async def _translate_chunk(self, chunk_list: List[str]) -> Dict[str, str]:
        """Translates a chunk of texts."""
        data_text = self._list_to_dict(chunk_list)
        text_translation = await self.api_client.api_call(
            self.config["model"]["high"],
            json.dumps(data_text, indent=0, ensure_ascii=False),
            self.config["system_instruction"].get("csv", ""),
            json_output=True
        )
        if text_translation is None:
            return {}
        try:
            data_translation = json.loads(text_translation)
            translation_map = {}
            for source_item, translated_item in zip(data_text, data_translation.get("translation", [])):
                source_text = str(source_item.get("text", "")).strip()
                translated_text = str(translated_item.get("text", "")).strip()
                if source_text:
                    translation_map[source_text] = translated_text
            return translation_map
        except Exception as e:
            logging.error(f"Failed to parse json response: {e}")
            return {}

    def _list_to_dict(self, chunk_list: List[str]) -> List[Dict[str, Any]]:
        """Converts list to dict structure for JSON."""
        return [{"id": index, "text": text_chunk} for index, text_chunk in enumerate(chunk_list, start=1)]

    async def translate_text_list(self, string_list: List[str]) -> Dict[str, Optional[str]]:
        """Translates list of texts using cache and asynchrony."""
        json_cache_path = Path(DICTIONARY_FILE)
        translation_data: Dict[str, Optional[str]] = dict.fromkeys(string_list)
        if json_cache_path.exists():
            with open(json_cache_path, "r", encoding="utf-8") as f:
                translation_data_cache: Dict[str, str] = json.load(f)
                translation_data.update(translation_data_cache)
        untranslated_keys = [
			key for key, value in translation_data.items()
			if value is None or value == key
		]
        if not untranslated_keys:
            logging.info("All strings already translated in cache.")
            return translation_data
        max_tokens = self.config["model"]["high"]["max_input_tokens"] * 3
        chunks: List[List[str]] = self._get_chunks(untranslated_keys, max_tokens)
        logging.info(f"Translating {len(untranslated_keys)} strings in {len(chunks)} chunks...")
        
        tasks = [self._translate_chunk(chunk) for chunk in chunks]
        for future in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Translation progress"):
            chunk_response = await future
            translation_data.update(chunk_response)
            with open(json_cache_path, "w", encoding="utf-8") as fp:
                json.dump(translation_data, fp, ensure_ascii=False, indent=2)

        return translation_data

    async def process_files(self):
        """Processes all files."""
        files = FileHandler.get_files(MOD_PATH)
        progress_data = self.progress_manager.load()
        for text_file in files:
            relative_path = os.path.relpath(text_file, MOD_PATH).replace(os.path.sep, '/')

            if progress_data.get(text_file) is not None:
                logging.info(f"Skipping already processed file: {relative_path}")
                continue
            handled = False
            print(text_file)
            for pattern, handler in TRANSLATION_INSTRUCTIONS.items():
                if relative_path.startswith(pattern):
                    if handler is False:
                        logging.info(f"Skip rule for: {relative_path}")
                        handled = True
                        break
                    if handler == "html":
                        result = await self.html_translation(text_file)
                    elif handler == "csv":
                        result = self.csv_translation(text_file)
                    else:
                        continue
                    progress_data[text_file] = result
                    self.progress_manager.save(progress_data)
                    handled = True
                    break
            if not handled:
                logging.info(f"No handler for {relative_path}")
        self.all_text_list = [item.strip() for item in self.all_text_list if isinstance(item, str)]
        with open(TEXT_LIST_FILE, "w", encoding="utf-8") as fp:
            json.dump(self.all_text_list, fp, ensure_ascii=False, indent=0)
        logging.info("Starting list translation")
        await self.translate_text_list(self.all_text_list)

CSV_RULES = {
    "events_background": [["ROW:EVENT", [2, 12]]],
    "factions_database": [["ROW:FACTION", [7]]],
    "items_database": [
        ["ROW:ITEM", [2, 22]],
        ["ROW:MODULE", [2, 22]],
        ["ROW:PMODULE", [2, 22]]
    ],
    "medals_database": [["ROW:MEDAL", [2, 12]]],
    "missions_database": [["ROW:MISSION", [2, 13, 14]]],
    "service_manager_database": [["ROW:MANAGER", [3, 10]]],
    "special_items": [["ROW:SPECIAL", [8]]],
    "special_ship_bunuses": [["ROW:SPECIAL", [3]]],
    "station_entertainment": [["ROW:ENTERTAINMENT", [7]]],
    "professions_database": [["ROW:PROFESSION", [11]]],
    "sandbox/_GM_": [["ROW:PRESET_desc", [1]]],
    "scripting/npcs": None,
    "scripting/": [[
        "COLUMN:VALUE 1",
        "stop_value:null",
        'codiction:COMMAND|IN|["TEXT", "OPTION", "NPC_CHAT", "NPC_ATTACK", "ADJ_CREDITS", "GET_DOCUMENT", "BUY_ITEM", "NPC_RETREAT", "MENU", "ADJ_FACTION"]'
    ]],
    "ships/ship_data_": [["ROW:SHIP_description", [1]]],
    "ships_npc/npc_ship_data_": [["ROW:SHIP_description", [1]]],
    "skills_database": [["ROW:SKILL", [22]]],
    "stations/sector_": [
        ["ROW:ENTERTAINMENT", [6]],
        ["ROW:OFFICE", [1]],
        ["ROW:MISSION", [6, 8]]
    ],
    "structures/": [['ROWS:STRUCTURE|desc', [2]]]
}

TRANSLATION_INSTRUCTIONS = {
    "documents/": "html",
    "events/": "csv",
    "factions/": "csv",
    "items/": "csv",
    "medals/": "csv",
    "missions/": "csv",
    "objets/intro_story": "html",
    "objets/": "csv",
    "professions/": "csv",
    "sandbox/game_modes/": "html",
    "sandbox/": "csv",
    "saves/": False,
    "scripting": "csv",
    "sectors/": False,
    "ship_parts/": False,
    "ships/new_ship": False,
    "ships/": "csv",
    "skills/": "csv",
    "stations/": "csv",
    "structures/": "csv",
}

import csv

def replace_csv_values(
    file_path: str,
    firts_rows_values: Optional[List[str]],
    replacement_idx: list[int|str],
    replacement_val: dict[str, str],
    delimiter: str = ";"
) -> None:
    """Replaces values in a CSV file based on rules."""
    new_content = ""
    with open(file_path, "r", encoding="utf-8", newline="") as fp:
        translated_text = {
            text.strip()
            for text in replacement_val.values()
            if isinstance(text, str)
        }
        for line in fp:
            stripped_line = line.strip()
            if not stripped_line or stripped_line.startswith(("-", "/", "<")):
                new_content += line
                continue
            content = csv.reader([line], delimiter=delimiter)
            row = next(content)
            if firts_rows_values and not row[:len(firts_rows_values)] == firts_rows_values:
                new_content += line
                continue
            is_modified = False
            modified_row = [text.strip() for text in row]
            for identifier in replacement_idx:
                if isinstance(identifier, str):
                    identifier = identifier.strip()
                    if identifier in modified_row:
                        idx = modified_row.index(identifier)
                        if identifier in replacement_val:
                            modified_row[idx] = replacement_val[identifier]
                            is_modified = True
                if isinstance(identifier, int):
                    if 0 <= identifier < len(modified_row) and modified_row[identifier].strip() not in translated_text:
                        try:
                            modified_row[identifier] = replacement_val[modified_row[identifier].strip()]
                            is_modified = True
                        except KeyError:
                            logging.warning(f"Key error: {modified_row[identifier].strip()}")
            if is_modified:
                new_content += ";".join(modified_row)+"\n"
            else:
                new_content += line
    with open(file_path , "w+", encoding="utf-8") as fp:
        new_content = "\n".join([line for line in new_content.splitlines() if line.strip()])
        fp.write(new_content)

def replace_text():
    """Replaces text in files using progress and dictionary data."""
    progress_path = Path(PROGRESS_FILE)
    dictionary_path = Path(DICTIONARY_FILE)

    if not progress_path.exists():
        logging.info("%s がないため、置換処理をスキップします。", PROGRESS_FILE)
        return

    with progress_path.open("r", encoding="utf-8") as fp:
        progress_data: Dict[str, Optional[str]] = json.load(fp)

    if not dictionary_path.exists():
        logging.info("%s がないため、置換処理をスキップします。", DICTIONARY_FILE)
        return

    with dictionary_path.open("r", encoding="utf-8") as fp:
        dictionary = json.load(fp)

    for file_path in progress_data.keys():
        if not Path(file_path).resolve().is_relative_to(Path(MOD_PATH).resolve()):
            continue

        print(file_path)
        if progress_data[file_path]:
            with open(file_path, "w", encoding="utf-8") as fp:
                fp.write(progress_data[file_path])
            continue

        relative_path = os.path.relpath(file_path, os.path.abspath(MOD_PATH))
        relative_path = relative_path.replace(os.path.sep, "/")

        if relative_path.startswith("scripting/") and not relative_path.startswith("scripting/npcs"):
            translator = Translator.__new__(Translator)
            translator._replace_script_texts(file_path, dictionary)
            continue

        rules = None
        for csvrule in CSV_RULES.keys():
            if csvrule in relative_path:
                rules = CSV_RULES[csvrule]
                break

        if not rules:
            continue

        for rule in rules:
            replace_csv_values(
                file_path,
                rule[0].split(":")[1].split("|")
                if rule[0].startswith("ROW")
                else None,
                rule[1]
                if rule[0].startswith("ROW")
                else list(dictionary.keys()),
                dictionary
            )

def translate_saves() -> None:
    global MOD_PATH

    if not MOD_PATH:
        logging.warning("MOD_PATH が設定されていないため、セーブ翻訳をスキップします。")
        return

    saves_path = Path(MOD_PATH) / "saves"

    if not saves_path.is_dir():
        logging.info("セーブフォルダーがないため、セーブ翻訳をスキップします: %s", saves_path)
        return

    saves_folders = [
        item.name for item in saves_path.iterdir()
        if item.is_dir()
    ]

    if not saves_folders:
        logging.info("セーブフォルダー内に対象フォルダーがありません。")
        return

    print(f"Found {len(saves_folders)} saves")
    title = "Please choose saves for translate (press SPACE to mark, ENTER to continue): "
    options = ["None", "All"] + saves_folders
    selected = pick(options, title, multiselect=True, min_selection_count=1)

    if 0 in [item[1] for item in selected]:
        print("No translate saves")
        return

    if 1 in [item[1] for item in selected]:
        print("All translate files")
        for folder in saves_folders:
            MOD_PATH = str(saves_path / folder)
            asyncio.run(main())
        return

    for folder, index in selected:
        if index >= 2:
            MOD_PATH = str(saves_path / folder)
            asyncio.run(main())

    return

async def main():
    config_loader = ConfigLoader()
    progress_manager = ProgressManager(PROGRESS_FILE)
    api_client = ApiClient(config_loader.config)
    translator = Translator(config_loader.config, progress_manager, api_client)
    await translator.process_files()
    replace_text()

if __name__ == "__main__":
    MOD_PATH = ORIGINAL_MOD_PATH
    asyncio.run(main())
    translate_saves()