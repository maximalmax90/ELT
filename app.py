from fileio import load_json, save_json, conversion, json_to_csv, save_csv
from dicts import dict_update, dict_compare, dict_apply_diffs, dict_convert, dict_update_group
from ai import tune_llm, translate_allm, translate_openai
from datetime import timedelta
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget,
                             QTabWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QFileDialog, QGroupBox, QLineEdit, QCheckBox, QMessageBox, QComboBox,
                             QTextEdit, QGridLayout, QSlider, QProgressBar, QListWidget, QTextBrowser, QSpinBox)
from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QColor, QFont, QPalette
from timeit import default_timer as timer
import sys, os

# Разукрашиваем лог
colors = {"[INFO]":QColor("LemonChiffon"),"[WARN]":QColor("Orange"),"[ OK ]":QColor("LimeGreen"),"[FAIL]":QColor("Tomato"),"[PASS]":QColor("Silver"),"[DONE]":QColor("PaleGreen"),"[SKIP]":QColor("#7fb3d5")}
file_types = ["Localization", "Dialogues", "PDA"]
# Обработка внешних ссылок для howto
class TextBrowser(QTextBrowser):
    def __init__(self):
        super().__init__()
        self.setOpenExternalLinks(True)  # Внешние ссылки открываются в браузере
        self.anchorClicked.connect(self.handle_link_click)

    def handle_link_click(self, url: QUrl):
        if url.isRelative():
            self.setSource(url)

    def setSource(self, url: QUrl):
        if url.isRelative():  # Только для внутренних ссылок
            super().setSource(url)

# Подтягиваем страницу с howto
def load_html_from_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return html_content
    except Exception as e:
        return ""
# Для перехвата print() и перенаправления в лог
class OutputRedirector(QObject):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
    def write(self, data):
        stripped_data = data.rstrip('\n')
        if stripped_data:
            self.text_widget.addItem(stripped_data)
            last = self.text_widget.count() - 1
            for color in colors:
                if color in stripped_data:
                    self.text_widget.item(last).setBackground(colors[color])
                    break
            self.text_widget.scrollToBottom()
    def flush(self):
        pass
# Инициализируем тред
ai_thread = None
ai_worker_instance = None
# Воркер для ИИ перевода
class AIWorker(QObject):
    log_signal = pyqtSignal(str)  # Сигнал для передачи строк логов
    progress_signal = pyqtSignal(int)  # Сигнал для обновления текущего значения прогресса
    set_max_progress_signal = pyqtSignal(int)  # Сигнал для установки максимального значения прогресса
    finished_signal = pyqtSignal()  # Сигнал завершения работы
    reset_progress_signal = pyqtSignal()

    def __init__(self, headers, work_dict, file_type, force, multi_count, multi_queue, exit_button, group_dict):
        super().__init__()
        self._running = True
        self.headers = headers
        self.work_dict = work_dict
        self.file_type = file_type
        self.force = force
        self.multi_count = multi_count
        self.multi_queue = multi_queue
        self.exit_button = exit_button
        self.group_dict = group_dict

    def run(self):
        try:
            self.log_signal.emit(f"[INFO] Запущен процесс перевода...")
            count = 0
            key_number = self.multi_queue - 1
            offset = self.multi_count
            self.progress_signal.emit(0)  # Установить прогресс на 0
            slug = "keytranslate"
            if self.group_dict is not None:
                total = len(self.group_dict)
                self.set_max_progress_signal.emit(total)  # Установить максимальное значение прогресса
                for elem in self.group_dict:
                    if self._running:
                        if key_number == count:
                            key_number += offset
                            save_flag = True
                            for lang in config['USE_LANGS']:
                                if lang not in elem:
                                    elem[lang] = ""
                                if self.force or len(elem[lang]) == 0:
                                    gen_start = timer()
                                    request = f"Translate text to {lang}: {elem['English']}"
                                    if config['AI_DEFAULT'] == "ALLM":
                                        response = translate_allm(config['AI']['ALLM']['API_URL'], self.headers, config['AI']['ALLM']['WORKER'].lower(), slug, request)
                                    if config['AI_DEFAULT'] == "OPENAI":
                                        response = translate_openai(config['AI']['OPENAI']['API_URL'], self.headers, config['AI']['OPENAI']['TUNE'], config['AI']['OPENAI']['WORKER'], config['AI']['OPENAI']['TEMPERATURE'], request)
                                    gen_end = timer()
                                    if "[TRANSLATIONFAIL]" in response:
                                        elem[lang] = ""
                                        self.log_signal.emit(f"[WARN] Ошибка перевода группы {elem['KEYS']} на {lang}: {response.split('[TRANSLATIONFAIL]')[1]}")
                                    else:
                                        elem[lang] = response
                                        self.log_signal.emit(f"[DONE] Перевод группы {elem['KEYS']} на {lang}, занял {timedelta(seconds=gen_end - gen_start)} сек.")
                                        for key in elem['KEYS']: self.work_dict[key][lang] = elem[lang]
                                else:
                                    self.log_signal.emit(f"[PASS] Пропуск группы {elem['KEYS']} для {lang}")
                        else:
                            save_flag = False
                            self.log_signal.emit(f"[SKIP] Пропуск группы {elem['KEYS']} - вне очереди")
                        count += 1
                        self.progress_signal.emit(count)  # Обновить прогресс
                        if save_flag:
                            save_json(f"{os.path.join(config['DATA_DIR'],config['BUILD'],self.file_type)}_group_intermediate.json", self.group_dict)
                            save_json(f"{os.path.join(config['DATA_DIR'],config['BUILD'],self.file_type)}_intermediate.json", self.work_dict)
            else:
                total = len(self.work_dict)
                self.set_max_progress_signal.emit(total)  # Установить максимальное значение прогресса
                for key in self.work_dict:
                    if self._running:
                        if key_number == count:
                            key_number += offset
                            save_flag = True
                            for lang in config['USE_LANGS']:
                                if lang not in self.work_dict[key]:
                                    self.work_dict[key][lang] = ""
                                if self.force or len(self.work_dict[key][lang]) == 0:
                                    gen_start = timer()
                                    request = f"Translate text to {lang}: {self.work_dict[key]['English']}"
                                    if config['AI_DEFAULT'] == "ALLM":
                                        response = translate_allm(config['AI']['ALLM']['API_URL'], self.headers, config['AI']['ALLM']['WORKER'].lower(), slug, request)
                                    if config['AI_DEFAULT'] == "OPENAI":
                                        response = translate_openai(config['AI']['OPENAI']['API_URL'], self.headers, config['AI']['OPENAI']['TUNE'], config['AI']['OPENAI']['WORKER'], config['AI']['OPENAI']['TEMPERATURE'], request)
                                    gen_end = timer()
                                    if "[TRANSLATIONFAIL]" in response:
                                        self.work_dict[key][lang] = ""
                                        self.log_signal.emit(f"[WARN] Ошибка перевода {key} на {lang}: {response.split('[TRANSLATIONFAIL]')[1]}")
                                    else:
                                        self.work_dict[key][lang] = response
                                        self.log_signal.emit(f"[DONE] Перевод {key} на {lang}, занял {timedelta(seconds=gen_end - gen_start)} сек.")
                                else:
                                    self.log_signal.emit(f"[PASS] Пропуск {key} для {lang}")
                        else:
                            save_flag = False
                            self.log_signal.emit(f"[SKIP] Пропуск {key} - вне очереди")
                        count += 1
                        self.progress_signal.emit(count)  # Обновить прогресс
                        if save_flag:
                            save_json(f"{os.path.join(config['DATA_DIR'],config['BUILD'],self.file_type)}_intermediate.json", self.work_dict)
            result = dict_convert(self.work_dict, "ToList")
            save_json(f"{os.path.join(config['DATA_DIR'],config['BUILD'],self.file_type)}_translated{self.multi_queue if self.multi_count > 1 else ""}.json", result)
            self.exit_button.setText("Выход")
            self.finished_signal.emit()  # Сообщить о завершении
            self.reset_progress_signal.emit()
            self.log_signal.emit(f"[INFO] Процесс перевода завершен")
        except Exception as e:
            self.log_signal.emit(f"[FAIL] {str(e)}")
            self.finished_signal.emit()
    def stop(self):
        self._running = False

# Прямая запись в лог
def append_to_log(log_edit, message):
    log_edit.addItem(message)
    last = log_edit.count() - 1
    for color in colors:
        if color in message:
            log_edit.item(last).setBackground(colors[color])
            break
    log_edit.scrollToBottom()
# Корректно завершаем процесс перевода
def finish_ai_thread(exit_button):
    global ai_thread, ai_worker_instance
    #ai_thread.deleteLater()
    ai_thread = None
    ai_worker_instance = None
    exit_button.setEnabled(True)
# Запускаем процесс перевода
def start_ai_thread(headers, work_dict, file_type, force, progress_bar, tab, log_edit, multi_count, multi_queue, exit_button, group_dict):
    global ai_thread, ai_worker_instance
    if not ai_thread:
        exit_button.setText("Прервать")
        ai_thread = QThread()
        ai_worker = AIWorker(headers, work_dict, file_type, force, multi_count, multi_queue, exit_button, group_dict)
        ai_worker_instance = ai_worker
        ai_worker.moveToThread(ai_thread)
        # Сигналы
        ai_worker.log_signal.connect(lambda msg: append_to_log(log_edit, msg))  # Обновление логов через слот
        ai_worker.progress_signal.connect(progress_bar.setValue)  # Обновление текущего значения прогресса
        ai_worker.set_max_progress_signal.connect(progress_bar.setMaximum)  # Установка максимального значения прогресса
        ai_worker.finished_signal.connect(lambda: tab.setEnabled(True))  # Разблокировка вкладки
        ai_worker.finished_signal.connect(ai_thread.quit)  # Завершение потока
        ai_worker.finished_signal.connect(ai_worker.deleteLater)  # Удаление объекта
        ai_thread.finished.connect(lambda: finish_ai_thread(exit_button)) # Корректно завершение процесса
        ai_thread.started.connect(ai_worker.run) # Запуск процесса
        ai_worker.reset_progress_signal.connect(progress_bar.reset) # Сброс прогресса
        ai_thread.start()
# Сохраняем лог в файл
def save_log(text):
    file_path, _ = QFileDialog.getSaveFileName(filter="Log-файлы (*.log)")
    if file_path:
        full_file_path = f"{file_path.split('.log')[0]}.log"
        try:
            with open(full_file_path, "w", encoding='utf-8') as file:
                data = ""
                items = text.findItems("", Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive)
                for item in items:
                    data += f"{item.text()}\n"
                file.write(data)
        except Exception as e:
            QMessageBox.critical(None, "Ошибка", f"Не удалось сохранить файл: {str(e)}")
        else:
            QMessageBox.information(None, "Информация", "Файл успешно сохранен!")
# Выбор директории
def select_directory(edit):
    directory = QFileDialog.getExistingDirectory()
    if directory:
        if os.path.exists(directory):
            edit.setText(directory)
# Выбираем файл
def select_file(edit_field, file_type: str):
    file_path = QFileDialog.getOpenFileName(filter=f"{file_type.upper()}-файлы (*.{file_type})")
    if file_path[0]:
        edit_field.setText(file_path[0])
# Декомпиляция
def decompile_start(csv_file, spec_file, file_type, tab, key_clean, key_group, key_chain):
    tab.setEnabled(False)
    try:
        os.makedirs(os.path.join(config['DATA_DIR'],config['BUILD']), exist_ok=True)
        if os.path.exists(f"{os.path.join(config['DATA_DIR'],config['BUILD'],file_type)}_decompiled.json"):
            reply = QMessageBox.question(None, 'Вопрос',
                                         f'Файл {file_type}_decompiled.json уже существует, перезаписать?',
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Cancel:
                tab.setEnabled(True)
                return
        if key_chain and os.path.exists(f"{os.path.join(config['DATA_DIR'],config['BUILD'],file_type)}_chains.json"):
            reply = QMessageBox.question(None, 'Вопрос',
                                         f'Файл {file_type}_chains.json уже существует, перезаписать?',
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Cancel:
                tab.setEnabled(True)
                return
        if key_group and os.path.exists(f"{os.path.join(config['DATA_DIR'],config['BUILD'],file_type)}_group.json"):
            reply = QMessageBox.question(None, 'Вопрос',
                                         f'Файл {file_type}_group.json уже существует, перезаписать?',
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Cancel:
                tab.setEnabled(True)
                return
        conversion(csv_file, spec_file, os.path.join(config['DATA_DIR'],config['BUILD']), file_type, config['USE_LANGS'],key_clean,key_group)
    except Exception as e:
        QMessageBox.critical(None, "Ошибка", f"{e}")
    tab.setEnabled(True)
# Обновление
def update_start(src_file, dst_file, file_type, tab, log_edit, group):
    tab.setEnabled(False)
    try:
        os.makedirs(f"{os.path.join(config['DATA_DIR'],config['BUILD'])}", exist_ok=True)
        if os.path.exists(f"{os.path.join(config['DATA_DIR'],config['BUILD'],file_type)}_updated.json"):
            reply = QMessageBox.question(None, 'Вопрос',
                                         f'Файл {file_type}_updated.json уже существует, перезаписать?',
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Cancel:
                tab.setEnabled(True)
                return

        dst = load_json(dst_file)
        if os.path.isdir(src_file):
            all_items = os.listdir(src_file)
            files = [f for f in all_items if f.endswith(".json") and os.path.isfile(os.path.join(src_file, f))]
            result = []
            for file in files:
                append_to_log(log_edit, f"[INFO] Обновляем ключи из источника: {os.path.join(src_file,file)}")
                src = load_json(os.path.join(src_file,file))
                if len(result) == 0:
                    result = dict_update(src, dst, config['USE_LANGS'])
                else:
                    result = dict_update(src, result, config['USE_LANGS'])
        else:
            if not group:
                append_to_log(log_edit, f"[INFO] Обновляем ключи из источника: {src_file}")
                src = load_json(src_file)
                result = dict_update(src, dst, config['USE_LANGS'])
            else:
                append_to_log(log_edit, f"[INFO] Обновляем ключи из группы: {src_file}")
                src = load_json(src_file)
                result = dict_update_group(src, dst, config['USE_LANGS'])
        save_json(f"{os.path.join(config['DATA_DIR'],config['BUILD'],file_type)}_updated.json", result)
    except Exception as e:
        QMessageBox.critical(None, "Ошибка", f"{e}")
    tab.setEnabled(True)
# Сравнение
def compare_start(current_file, new_file, file_type, tab):
    tab.setEnabled(False)
    try:
        os.makedirs(os.path.join(config['DATA_DIR'],config['BUILD']), exist_ok=True)
        if os.path.exists(f"{os.path.join(config['DATA_DIR'],config['BUILD'],file_type)}_diffs.json"):
            reply = QMessageBox.question(None, 'Вопрос',
                                         f'Файл {file_type}_diffs.json уже существует, перезаписать?',
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Cancel:
                tab.setEnabled(True)
                return
        current = load_json(current_file)
        new = load_json(new_file)
        result = dict_compare(current, new, config['USE_LANGS'])
        save_json(f"{os.path.join(config['DATA_DIR'],config['BUILD'],file_type)}_diffs.json", result)
    except Exception as e:
        QMessageBox.critical(None, "Ошибка", f"{e}")
    tab.setEnabled(True)
# Применение изменений
def apply_start(current_file, diffs_file, file_type, tab):
    tab.setEnabled(False)
    try:
        os.makedirs(os.path.join(config['DATA_DIR'],config['BUILD']), exist_ok=True)
        if os.path.exists(f"{os.path.join(config['DATA_DIR'],config['BUILD'],file_type)}_applied.json"):
            reply = QMessageBox.question(None, 'Вопрос',
                                         f'Файл {file_type}_applied.json уже существует, перезаписать?',
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Cancel:
                tab.setEnabled(True)
                return
        current = load_json(current_file)
        diffs = load_json(diffs_file)
        result = dict_apply_diffs(current, diffs)
        save_json(f"{os.path.join(config['DATA_DIR'],config['BUILD'],file_type)}_applied.json", result)
    except Exception as e:
        QMessageBox.critical(None, "Ошибка", f"{e}")
    tab.setEnabled(True)
# ИИ перевод
def ai_translate_start(main_file, file_type, force, tab, progress_bar, log_edit, multi_count, multi_queue, exit_button):
    tab.setEnabled(False)
    exist_intermediate = False
    exist_group = False
    exist_group_intermediate = False
    try:
        os.makedirs(os.path.join(config['DATA_DIR'],config['BUILD']), exist_ok=True)
        if os.path.exists(f"{os.path.join(config['DATA_DIR'],config['BUILD'],file_type)}_translated{multi_queue if multi_count > 1 else ""}.json"):
            reply = QMessageBox.question(None, 'Вопрос',
                                         f'Файл {file_type}_translated{multi_queue if multi_count > 1 else ""}.json уже существует, перезаписать?',
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Cancel:
                tab.setEnabled(True)
                return
        if os.path.exists(f"{os.path.join(config['DATA_DIR'],config['BUILD'],file_type)}_group.json"):
             exist_group = True
        if os.path.exists(f"{os.path.join(config['DATA_DIR'],config['BUILD'],file_type)}_intermediate.json") and not force:
             exist_intermediate = True
        if os.path.exists(f"{os.path.join(config['DATA_DIR'],config['BUILD'],file_type)}_group_intermediate.json") and not force:
             exist_group_intermediate = True
        headers = {
            'accept': 'application/json',
            'Authorization': f'Bearer {config["AI"][config["AI_DEFAULT"]]["API_KEY"]}',
            'Content-Type': 'application/json; charset=utf-8'
        }
        if not exist_intermediate:
            main_dict = load_json(main_file)
            work_dict = dict_convert(main_dict, "ToDict")
        else:
            work_dict = load_json(f"{os.path.join(config['DATA_DIR'],config['BUILD'],file_type)}_intermediate.json")
        if exist_group and not exist_group_intermediate:
            group_dict = load_json(f"{os.path.join(config['DATA_DIR'],config['BUILD'],file_type)}_group.json")
        elif exist_group and exist_group_intermediate:
            group_dict = load_json(f"{os.path.join(config['DATA_DIR'],config['BUILD'],file_type)}_group_intermediate.json")
        else:
            group_dict = None

        ai_tune = tune_llm(config['AI_DEFAULT'], config['AI'][config['AI_DEFAULT']]['API_URL'], headers, config['AI'][config['AI_DEFAULT']]['WORKER'].lower(), config['AI'][config['AI_DEFAULT']]['TUNE'],
                            config['AI'][config['AI_DEFAULT']]['TEMPERATURE'])
        if ai_tune:
            start_ai_thread(headers, work_dict, file_type, force, progress_bar, tab, log_edit, multi_count, multi_queue, exit_button, group_dict)
        else:
            tab.setEnabled(True)
            return
    except Exception as e:
        QMessageBox.critical(None, "Ошибка", f"{e}")
# Компиляция
def compile_start(json_file, file_type, tab):
    tab.setEnabled(False)
    try:
        os.makedirs(os.path.join(config['DATA_DIR'],config['BUILD']), exist_ok=True)
        if os.path.exists(f"{os.path.join(config['DATA_DIR'],config['BUILD'],file_type)}_prepared.csv"):
            reply = QMessageBox.question(None, 'Вопрос',
                                         f'Файл {file_type}_prepared.csv уже существует, перезаписать?',
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Cancel:
                tab.setEnabled(True)
                return
        main_dict = load_json(json_file)
        result = json_to_csv(main_dict, config['ALL_LANGS'])
        if save_csv(f"{os.path.join(config['DATA_DIR'],config['BUILD'],file_type)}_prepared.csv", result):
            print(f"[ OK ] {os.path.join(config['DATA_DIR'],config['BUILD'],file_type)}_prepared.csv скомпилирован, количество строк: {len(result)}")
    except Exception as e:
        QMessageBox.critical(None, "Ошибка", f"{e}")
    tab.setEnabled(True)

# Промпт для ALLM по умолчанию, для OPENAI можно исключить п3:
"""
You are a professional translator. Your task is to translate text into the language specified by the user. **Follow these rules strictly and without exceptions:**

1. **Do not translate or modify the following elements:**
- BBCode (e.g., `[b]`, `[i]`, `[url]`, etc.).
- HTML tags (e.g., `<div>`, `<p>`, `<br>`, etc.).
- Special characters (e.g., `@`, `#`, `$`, `%`, `&`, `*`, etc.).
- Character sequences (e.g., `@n`, `@w`, `@p`, `@q`, etc.).
- Variables enclosed in curly braces `{}` (e.g., `{variable_name}`).
- Escaped newline characters (`\n`).

2. **Do not add or remove any extra characters, spaces, or line breaks.** Preserve the original structure of the text.

3. If a glossary is provided, follow its format strictly:
```
{'Abbreviations': {'ABBR': {'Meaning': '', 'LANGUAGE': 'VALUE', ...}},
    'Words': {'WORD': {'LANGUAGE': 'VALUE', ...}},
    'Skip': ['Word', 'or words']}
```
- Use the glossary to translate specific words or abbreviations (case-insensitive).
- Leave words or phrases untranslated if they are listed in the "Skip" section.
- Always prioritize the glossary when translating terms or abbreviations it contains.

4. **Maintain the case (uppercase or lowercase) of all letters as in the original text.**

5. **Ensure the translation adheres to the grammatical and syntactical rules of the target language.** The translated text must read fluently and naturally.

6. **Contextual Note:** The text may involve themes of space, survival, harsh conditions, or an alien galaxy. Keep this context in mind to ensure the translation aligns with the intended tone and meaning.

**Important:** If any part of the text matches the elements listed in Rule 1 (e.g., BBCode, HTML tags, variables, etc.), leave it **exactly as it is** without any changes or translation.

Your response must contain **only the translated text** without any explanations, notes, or additional comments.
"""

config = load_json("config.json")
if len(config) == 0:
    config = {
        "DATA_DIR": f"{os.getcwd()}",
        "BUILD": "0",
        "USE_LANGS": [],
        "ALL_LANGS": [
            "English",
            "Deutsch",
            "Français",
            "Italiano",
            "Spanish",
            "Portuguese (Euro)",
            "Portuguese (Brazil)",
            "Polish",
            "Russian",
            "Japanese",
            "Chinese (simplified)",
            "Chinese (traditional)",
            "Korean",
            "Turkish",
            "Greek",
            "Dutch",
            "Vietnamese"
        ],
        "AI": {
            "ALLM": {
                "TUNE": "You are a professional translator. Your task is to translate text into the language specified by the user. **Follow these rules strictly and without exceptions:**\n\n1. **Do not translate or modify the following elements:**\n   - BBCode (e.g., `[b]`, `[i]`, `[url]`, etc.).\n   - HTML tags (e.g., `<div>`, `<p>`, `<br>`, etc.).\n   - Special characters (e.g., `@`, `#`, `$`, `%`, `&`, `*`, etc.).\n   - Character sequences (e.g., `@n`, `@w`, `@p`, `@q`, etc.).\n   - Variables enclosed in curly braces `{}` (e.g., `{variable_name}`).\n   - Escaped newline characters (`\\n`).\n\n2. **Do not add or remove any extra characters, spaces, or line breaks.** Preserve the original structure of the text.\n\n3. If a glossary is provided, follow its format strictly:\n   ```\n   {'Abbreviations': {'ABBR': {'Meaning': '', 'LANGUAGE': 'VALUE', ...}},\n    'Words': {'WORD': {'LANGUAGE': 'VALUE', ...}},\n    'Skip': ['Word', 'or words']}\n   ```\n   - Use the glossary to translate specific words or abbreviations (case-insensitive).\n   - Leave words or phrases untranslated if they are listed in the \"Skip\" section.\n   - Always prioritize the glossary when translating terms or abbreviations it contains.\n\n4. **Maintain the case (uppercase or lowercase) of all letters as in the original text.**\n\n5. **Ensure the translation adheres to the grammatical and syntactical rules of the target language.** The translated text must read fluently and naturally.\n\n6. **Contextual Note:** The text may involve themes of space, survival, harsh conditions, or an alien galaxy. Keep this context in mind to ensure the translation aligns with the intended tone and meaning.\n\n**Important:** If any part of the text matches the elements listed in Rule 1 (e.g., BBCode, HTML tags, variables, etc.), leave it **exactly as it is** without any changes or translation.\n\nYour response must contain **only the translated text** without any explanations, notes, or additional comments.",
                "API_URL": "http://localhost:3001/api/v1",
                "API_KEY": "apikey",
                "TEMPERATURE": 0.0,
                "WORKER": "ELT",
                "WORKER_TITLE": "Рабочее пространство:"
            },
            "OPENAI": {
                "TUNE": "You are a professional translator. Your task is to translate text into the language specified by the user. **Follow these rules strictly and without exceptions:**\n\n1. **Do not translate or modify the following elements:**\n   - BBCode (e.g., `[b]`, `[i]`, `[url]`, etc.).\n   - HTML tags (e.g., `<div>`, `<p>`, `<br>`, etc.).\n   - Special characters (e.g., `@`, `#`, `$`, `%`, `&`, `*`, etc.).\n   - Character sequences (e.g., `@n`, `@w`, `@p`, `@q`, etc.).\n   - Variables enclosed in curly braces `{}` (e.g., `{variable_name}`).\n   - Escaped newline characters (`\\n`).\n\n2. **Do not add or remove any extra characters, spaces, or line breaks.** Preserve the original structure of the text.\n\n3. **Maintain the case (uppercase or lowercase) of all letters as in the original text.**\n\n4. **Ensure the translation adheres to the grammatical and syntactical rules of the target language.** The translated text must read fluently and naturally.\n\n5. **Contextual Note:** The text may involve themes of space, survival, harsh conditions, or an alien galaxy. Keep this context in mind to ensure the translation aligns with the intended tone and meaning.\n\n**Important:** If any part of the text matches the elements listed in Rule 1 (e.g., BBCode, HTML tags, variables, etc.), leave it **exactly as it is** without any changes or translation.\n\nYour response must contain **only the translated text** without any explanations, notes, or additional comments.",
                "API_URL": "http://localhost:1234/v1",
                "API_KEY": "apikey",
                "TEMPERATURE": 0.0,
                "WORKER": "gpt-4",
                "WORKER_TITLE": "Модель:"
            }
        },
        "AI_DEFAULT": "ALLM"
    }

def main_form():
    global config
    # Отслеживаем изменения
    def on_DecompileTextChanged():
        if decompile_type_combobox.currentText() == "Localization":
            if decompile_csv_edit.text().strip():
                decompile_button.setEnabled(True)
            else:
                decompile_button.setEnabled(False)
        else:
            if (decompile_chain_checkbox.isChecked() and
                    decompile_csv_edit.text().strip() and
                    decompile_spec_edit.text().strip()):
                decompile_button.setEnabled(True)
            elif (not decompile_chain_checkbox.isChecked() and
                  decompile_csv_edit.text().strip()):
                decompile_button.setEnabled(True)
            else:
                decompile_button.setEnabled(False)
    def on_DecompileListChanged():
        if decompile_type_combobox.currentText() == "Localization":
            decompile_chain_checkbox.setEnabled(False)
            decompile_chain_checkbox.setChecked(False)
            decompile_spec_group.hide()
        else:
            decompile_chain_checkbox.setEnabled(True)
            if decompile_type_combobox.currentText() == "Dialogues": decompile_spec_group.setTitle("ECF-файл:")
            else: decompile_spec_group.setTitle("YAML-файл:")
        decompile_spec_edit.setText("")
        decompile_csv_edit.setText("")
        on_DecompileTextChanged()
    def on_DecompileTypeChecked():
        on_DecompileTextChanged()
        if decompile_chain_checkbox.isChecked() and "Localization" not in decompile_type_combobox.currentText():
            decompile_spec_group.show()
        else:
            decompile_spec_group.hide()
    def on_DictsTextChanged(edit1, edit2, combo, button):
        for file_type in file_types:
            if file_type in edit1.text():
                combo.setCurrentText(file_type)
                break
        if edit2 is not None:
            if edit1.text().strip() and edit2.text().strip():
                button.setEnabled(True)
            else:
                button.setEnabled(False)
        else:
            if edit1.text().strip():
                button.setEnabled(True)
            else:
                button.setEnabled(False)
    def on_AiTranslateCountChange(queue):
        queue.setMaximum(ai_translate_count_spinbox.value())
        if queue.value()>ai_translate_count_spinbox.value():
            queue.setValue(ai_translate_count_spinbox.value())
    def on_CompileTextChanged():
        if compile_json_edit.text().strip():
            compile_button.setEnabled(True)
        else:
            compile_button.setEnabled(False)
    def on_SettingsTextChanged():
        if (settings_datadir_edit.text().strip() and settings_build_edit.text().strip()
                and ai_settings_apiurl_edit.text().strip() and ai_settings_apikey_edit.text().strip()
                and ai_settings_worker_edit.text().strip()):
            settings_button.setEnabled(True)
        else:
            settings_button.setEnabled(False)
    def on_SettingsSlider():
        value = float(ai_settings_temperature_slider.value() / 10)
        config['AI'][ai_settings_apiprovider_combobox.currentText()]['TEMPERATURE'] = value
        on_SettingsTextChanged()
        ai_settings_temperature_slider_label.setText(str(value))
    def ai_layout_set():
        ai_settings_apiurl_edit.setText(config['AI'][ai_settings_apiprovider_combobox.currentText()]['API_URL'])
        ai_settings_apiurl_edit.setText(config['AI'][ai_settings_apiprovider_combobox.currentText()]['API_URL'])
        ai_settings_apikey_edit.setText(config['AI'][ai_settings_apiprovider_combobox.currentText()]['API_KEY'])
        ai_settings_worker_edit.setText(config['AI'][ai_settings_apiprovider_combobox.currentText()]['WORKER'])
        ai_settings_worker_group.setTitle(config['AI'][ai_settings_apiprovider_combobox.currentText()]['WORKER_TITLE'])
        ai_settings_temperature_slider.setValue(int(config['AI'][ai_settings_apiprovider_combobox.currentText()]['TEMPERATURE'] * 10))
        ai_settings_temperature_slider_label.setText(str(config['AI'][ai_settings_apiprovider_combobox.currentText()]['TEMPERATURE']))
        ai_settings_tune_edit.setText(config['AI'][ai_settings_apiprovider_combobox.currentText()]['TUNE'])
    def on_SettingsApiPrivider():
        ai_layout_set()
    def on_LangChecked(state, lang):
        if state == Qt.Checked:
            if lang not in config['USE_LANGS']:
                config['USE_LANGS'].append(lang)
        else:
            if lang in config['USE_LANGS']:
                config['USE_LANGS'].remove(lang)
        on_SettingsTextChanged()
    def on_exitClicked():
        if ai_thread and ai_thread.isRunning():
            exit_button.setText("Выход")
            exit_button.setEnabled(False)
            if ai_worker_instance:
                ai_worker_instance.stop()
            ai_thread.finished.connect(lambda: finish_ai_thread(exit_button))
        else:
            window.close()

    # Сохраняем конфиг
    def save_config():
        config['DATA_DIR'] = settings_datadir_edit.text()
        config['BUILD'] = settings_build_edit.text()
        config['AI_DEFAULT'] = ai_settings_apiprovider_combobox.currentText()
        config['AI'][ai_settings_apiprovider_combobox.currentText()]['API_KEY'] = ai_settings_apikey_edit.text()
        config['AI'][ai_settings_apiprovider_combobox.currentText()]['API_URL'] = ai_settings_apiurl_edit.text()
        config['AI'][ai_settings_apiprovider_combobox.currentText()]['WORKER'] = ai_settings_worker_edit.text()
        config['AI'][ai_settings_apiprovider_combobox.currentText()]['TUNE'] = ai_settings_tune_edit.toPlainText()
        config['AI'][ai_settings_apiprovider_combobox.currentText()]['TEMPERATURE'] = float(ai_settings_temperature_slider.value() / 10)
        if save_json("config.json", config):
            QMessageBox.information(None, "Информация", "Файл успешно сохранен!")
        else:
            QMessageBox.critical(None, "Ошибка", "Не удалось сохранить файл!")

    app = QApplication(sys.argv)

    window = QMainWindow()
    window_palette = QPalette()
    #window_palette.setColor(window_palette.Background, QColor("LightGrey"))
    window_palette.setColor(QPalette.ColorRole.Window, QColor("LightGrey"))

    window.setPalette(window_palette)
    window.setFixedSize(796, 676)

    progress = QProgressBar()
    progress.setFixedHeight(16)
    progress.setFormat("%v/%m")

    tab_widget = QTabWidget()

    window_widget = QWidget()
    window_layout = QVBoxLayout(window_widget)

    tabs = ["?","Декомпиляция", "Обновление", "Сравнение", "Применение изменений", "ИИ Перевод", "Компиляция", "Настройки"]
    # Да, по сути лишний цикл, но захотелось так
    for title in tabs:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        if title == "Декомпиляция":
            decompile_type_group = QGroupBox("Тип файла:")
            decompile_type_layout = QHBoxLayout(decompile_type_group)
            decompile_type_combobox = QComboBox()
            decompile_type_combobox.addItems(file_types)
            decompile_type_combobox.setFixedSize(100, 20)
            decompile_chain_checkbox = QCheckBox('Сформировать цепочку ключей')
            decompile_chain_checkbox.setEnabled(False)
            decompile_group_checkbox = QCheckBox('Сформировать группу ключей')
            #decompile_group_checkbox.setChecked(True)
            decompile_clear_checkbox = QCheckBox('Очистить ключи')
            decompile_type_layout.addWidget(decompile_type_combobox)
            decompile_type_layout.addWidget(decompile_chain_checkbox)
            decompile_type_layout.addWidget(decompile_group_checkbox)
            decompile_type_layout.addWidget(decompile_clear_checkbox, alignment=Qt.AlignmentFlag.AlignRight)

            decompile_csv_group = QGroupBox("CSV-файл:")
            decompile_csv_layout = QHBoxLayout(decompile_csv_group)
            decompile_csv_edit = QLineEdit()
            decompile_csv_edit.setFixedHeight(20)
            decompile_csv_edit.setReadOnly(True)
            decompile_csv_button = QPushButton("...")
            decompile_csv_button.setFixedSize(20, 20)
            decompile_csv_layout.addWidget(decompile_csv_edit)
            decompile_csv_layout.addWidget(decompile_csv_button)

            decompile_spec_group = QGroupBox()
            decompile_spec_layout = QHBoxLayout(decompile_spec_group)
            decompile_spec_edit = QLineEdit()
            decompile_spec_edit.setFixedHeight(20)
            decompile_spec_edit.setReadOnly(True)
            decompile_spec_button = QPushButton("...")
            decompile_spec_button.setFixedSize(20, 20)
            decompile_spec_layout.addWidget(decompile_spec_edit)
            decompile_spec_layout.addWidget(decompile_spec_button)
            decompile_spec_group.hide()

            decompile_button = QPushButton("Начать")
            decompile_button.setFixedSize(50, 20)
            decompile_button.setEnabled(False)

            decompile_layout = QVBoxLayout()
            decompile_layout.addWidget(decompile_type_group)
            decompile_layout.addWidget(decompile_csv_group)
            decompile_layout.addWidget(decompile_spec_group)
            decompile_layout.addStretch()
            decompile_layout.addWidget(decompile_button, alignment=Qt.AlignmentFlag.AlignRight)

            layout.addLayout(decompile_layout)
            # Обработчики
            decompile_csv_edit.textChanged.connect(on_DecompileTextChanged)
            decompile_spec_edit.textChanged.connect(on_DecompileTextChanged)
            decompile_type_combobox.currentTextChanged.connect(on_DecompileListChanged)
            decompile_chain_checkbox.toggled.connect(on_DecompileTypeChecked)
            decompile_csv_button.clicked.connect(lambda: select_file(decompile_csv_edit, "csv"))
            decompile_spec_button.clicked.connect(lambda: select_file(decompile_spec_edit,
                                                                      "ecf" if decompile_type_combobox.currentText() == "Dialogues" else "yaml"))
            decompile_button.clicked.connect(lambda: decompile_start(decompile_csv_edit.text(),
                                                                     decompile_spec_edit.text(),
                                                                     decompile_type_combobox.currentText(), tab_widget, decompile_clear_checkbox.isChecked(), decompile_group_checkbox.isChecked(), decompile_chain_checkbox.isChecked()))
        if title == "Обновление":
            update_type_group = QGroupBox("Тип файла:")
            update_type_layout = QHBoxLayout(update_type_group)
            update_type_combobox = QComboBox()
            update_type_combobox.addItems(file_types)
            update_type_combobox.setFixedSize(100, 20)
            update_type_checkbox = QCheckBox('Источник - файлы из директории')
            update_group_checkbox = QCheckBox('Источник - файл групп')
            update_type_layout.addWidget(update_type_combobox, alignment=Qt.AlignmentFlag.AlignLeft)
            update_type_layout.addWidget(update_group_checkbox)
            update_type_layout.addWidget(update_type_checkbox)

            update_src_group = QGroupBox("Источник значений ключей:")
            update_src_layout = QHBoxLayout(update_src_group)
            update_src_edit = QLineEdit()
            update_src_edit.setFixedHeight(20)
            update_src_edit.setReadOnly(True)
            update_src_button = QPushButton("...")
            update_src_button.setFixedSize(20, 20)
            update_src_layout.addWidget(update_src_edit)
            update_src_layout.addWidget(update_src_button)

            update_dst_group = QGroupBox("Приемник значений ключей:")
            update_dst_layout = QHBoxLayout(update_dst_group)
            update_dst_edit = QLineEdit()
            update_dst_edit.setFixedHeight(20)
            update_dst_edit.setReadOnly(True)
            update_dst_button = QPushButton("...")
            update_dst_button.setFixedSize(20, 20)
            update_dst_layout.addWidget(update_dst_edit)
            update_dst_layout.addWidget(update_dst_button)

            update_button = QPushButton("Начать")
            update_button.setFixedSize(50, 20)
            update_button.setEnabled(False)

            update_layout = QVBoxLayout()
            update_layout.addWidget(update_type_group)
            update_layout.addWidget(update_src_group)
            update_layout.addWidget(update_dst_group)
            update_layout.addStretch()
            update_layout.addWidget(update_button, alignment=Qt.AlignmentFlag.AlignRight)

            layout.addLayout(update_layout)
            # Обработчики
            update_src_button.clicked.connect(lambda: select_file(update_src_edit, "json") if (not update_type_checkbox.isChecked() or update_group_checkbox.isChecked()) else select_directory(update_src_edit))
            update_dst_button.clicked.connect(lambda: select_file(update_dst_edit, "json"))
            update_type_checkbox.stateChanged.connect(lambda :update_src_edit.setText(""))
            update_group_checkbox.stateChanged.connect(lambda: update_type_checkbox.setEnabled(False) if update_group_checkbox.isChecked() else update_type_checkbox.setEnabled(True))
            update_src_edit.textChanged.connect(lambda: on_DictsTextChanged(update_dst_edit, update_src_edit, update_type_combobox, update_button))
            update_dst_edit.textChanged.connect(lambda: on_DictsTextChanged(update_dst_edit, update_src_edit, update_type_combobox, update_button))
            update_button.clicked.connect(lambda: update_start(update_src_edit.text(),
                                                               update_dst_edit.text(),
                                                               update_type_combobox.currentText(), tab_widget, log_edit, update_group_checkbox.isChecked()))
        if title == "Сравнение":
            compare_type_group = QGroupBox("Тип файла:")
            compare_type_layout = QHBoxLayout(compare_type_group)
            compare_type_combobox = QComboBox()
            compare_type_combobox.addItems(file_types)
            compare_type_combobox.setFixedSize(100, 20)
            compare_type_layout.addWidget(compare_type_combobox, alignment=Qt.AlignmentFlag.AlignLeft)

            compare_current_group = QGroupBox("Текущий словарь:")
            compare_current_layout = QHBoxLayout(compare_current_group)
            compare_current_edit = QLineEdit()
            compare_current_edit.setFixedHeight(20)
            compare_current_edit.setReadOnly(True)
            compare_current_button = QPushButton("...")
            compare_current_button.setFixedSize(20, 20)
            compare_current_layout.addWidget(compare_current_edit)
            compare_current_layout.addWidget(compare_current_button)

            compare_new_group = QGroupBox("Новый словарь:")
            compare_new_layout = QHBoxLayout(compare_new_group)
            compare_new_edit = QLineEdit()
            compare_new_edit.setFixedHeight(20)
            compare_new_edit.setReadOnly(True)
            compare_new_button = QPushButton("...")
            compare_new_button.setFixedSize(20, 20)
            compare_new_layout.addWidget(compare_new_edit)
            compare_new_layout.addWidget(compare_new_button)

            compare_button = QPushButton("Начать")
            compare_button.setFixedSize(50, 20)
            compare_button.setEnabled(False)

            compare_layout = QVBoxLayout()
            compare_layout.addWidget(compare_type_group)
            compare_layout.addWidget(compare_current_group)
            compare_layout.addWidget(compare_new_group)
            compare_layout.addStretch()
            compare_layout.addWidget(compare_button, alignment=Qt.AlignmentFlag.AlignRight)

            layout.addLayout(compare_layout)
            # Обработчики
            compare_current_button.clicked.connect(lambda: select_file(compare_current_edit, "json"))
            compare_new_button.clicked.connect(lambda: select_file(compare_new_edit, "json"))
            compare_current_edit.textChanged.connect(lambda: on_DictsTextChanged(compare_current_edit, compare_new_edit, compare_type_combobox, compare_button))
            compare_new_edit.textChanged.connect(lambda: on_DictsTextChanged(compare_current_edit, compare_new_edit, compare_type_combobox, compare_button))
            compare_button.clicked.connect(lambda: compare_start(compare_current_edit.text(),
                                                                 compare_new_edit.text(),
                                                                 compare_type_combobox.currentText(), tab_widget))
        if title == "Применение изменений":
            apply_type_group = QGroupBox("Тип файла:")
            apply_type_layout = QHBoxLayout(apply_type_group)
            apply_type_combobox = QComboBox()
            apply_type_combobox.addItems(file_types)
            apply_type_combobox.setFixedSize(100, 20)
            apply_type_layout.addWidget(apply_type_combobox, alignment=Qt.AlignmentFlag.AlignLeft)

            apply_current_group = QGroupBox("Текущий словарь:")
            apply_current_layout = QHBoxLayout(apply_current_group)
            apply_current_edit = QLineEdit()
            apply_current_edit.setFixedHeight(20)
            apply_current_edit.setReadOnly(True)
            apply_current_button = QPushButton("...")
            apply_current_button.setFixedSize(20, 20)
            apply_current_layout.addWidget(apply_current_edit)
            apply_current_layout.addWidget(apply_current_button)

            apply_diffs_group = QGroupBox("Словарь с изменениями:")
            apply_diffs_layout = QHBoxLayout(apply_diffs_group)
            apply_diffs_edit = QLineEdit()
            apply_diffs_edit.setFixedHeight(20)
            apply_diffs_edit.setReadOnly(True)
            apply_diffs_button = QPushButton("...")
            apply_diffs_button.setFixedSize(20, 20)
            apply_diffs_layout.addWidget(apply_diffs_edit)
            apply_diffs_layout.addWidget(apply_diffs_button)

            apply_button = QPushButton("Начать")
            apply_button.setFixedSize(50, 20)
            apply_button.setEnabled(False)

            apply_layout = QVBoxLayout()
            apply_layout.addWidget(apply_type_group)
            apply_layout.addWidget(apply_current_group)
            apply_layout.addWidget(apply_diffs_group)
            apply_layout.addStretch()
            apply_layout.addWidget(apply_button, alignment=Qt.AlignmentFlag.AlignRight)

            layout.addLayout(apply_layout)
            # Обработчики
            apply_current_button.clicked.connect(lambda: select_file(apply_current_edit, "json"))
            apply_diffs_button.clicked.connect(lambda: select_file(apply_diffs_edit, "json"))
            apply_current_edit.textChanged.connect(lambda: on_DictsTextChanged(apply_current_edit, apply_diffs_edit, apply_type_combobox, apply_button))
            apply_diffs_edit.textChanged.connect(lambda: on_DictsTextChanged(apply_current_edit, apply_diffs_edit, apply_type_combobox, apply_button))
            apply_button.clicked.connect(lambda: apply_start(apply_current_edit.text(),
                                                             apply_diffs_edit.text(),
                                                             apply_type_combobox.currentText(), tab_widget))
        if title == "ИИ Перевод":
            ai_translate_type_group = QGroupBox("Тип файла:")
            ai_translate_type_layout = QHBoxLayout(ai_translate_type_group)
            ai_translate_type_combobox = QComboBox()
            ai_translate_type_combobox.addItems(file_types)
            ai_translate_type_combobox.setFixedSize(100, 20)
            ai_translate_forced_checkbox = QCheckBox('Заменять существующий перевод')

            ai_translate_type_layout.addWidget(ai_translate_type_combobox)
            ai_translate_type_layout.addStretch()
            ai_translate_type_layout.addWidget(ai_translate_forced_checkbox,
                                               alignment=Qt.AlignmentFlag.AlignRight)

            ai_translate_src_group = QGroupBox("Словарь:")
            ai_translate_src_layout = QHBoxLayout(ai_translate_src_group)
            ai_translate_src_edit = QLineEdit()
            ai_translate_src_edit.setFixedHeight(20)
            ai_translate_src_edit.setReadOnly(True)
            ai_translate_src_button = QPushButton("...")
            ai_translate_src_button.setFixedSize(20, 20)
            ai_translate_src_layout.addWidget(ai_translate_src_edit)
            ai_translate_src_layout.addWidget(ai_translate_src_button)

            ai_translate_multi_group = QGroupBox("Параллельный перевод:")
            ai_translate_multi_layout = QHBoxLayout(ai_translate_multi_group)

            ai_translate_count_group = QGroupBox("Количество человек:")
            ai_translate_count_layout = QHBoxLayout(ai_translate_count_group)
            ai_translate_count_spinbox = QSpinBox()
            ai_translate_count_spinbox.setRange(1, 99)
            ai_translate_count_spinbox.setValue(1)
            ai_translate_count_spinbox.setFixedSize(100, 20)
            ai_translate_count_layout.addWidget(ai_translate_count_spinbox)

            ai_translate_queue_group = QGroupBox("Позиция:")
            ai_translate_queue_layout = QHBoxLayout(ai_translate_queue_group)
            ai_translate_queue_spinbox = QSpinBox()
            ai_translate_queue_spinbox.setRange(1, 1)
            ai_translate_queue_spinbox.setValue(1)
            ai_translate_queue_spinbox.setFixedSize(100, 20)
            ai_translate_queue_layout.addWidget(ai_translate_queue_spinbox)

            ai_translate_multi_layout.addWidget(ai_translate_count_group)
            ai_translate_multi_layout.addWidget(ai_translate_queue_group)
            ai_translate_multi_layout.addStretch()

            ai_translate_button = QPushButton("Начать")
            ai_translate_button.setFixedSize(50, 20)
            ai_translate_button.setEnabled(False)

            ai_translate_layout = QVBoxLayout()
            ai_translate_layout.addWidget(ai_translate_type_group)
            ai_translate_layout.addWidget(ai_translate_src_group)
            ai_translate_layout.addWidget(ai_translate_multi_group)
            ai_translate_layout.addStretch()
            ai_translate_layout.addWidget(ai_translate_button, alignment=Qt.AlignmentFlag.AlignRight)
            layout.addLayout(ai_translate_layout)
            # Обработчики
            ai_translate_src_button.clicked.connect(lambda: select_file(ai_translate_src_edit, "json"))
            ai_translate_src_edit.textChanged.connect(lambda: on_DictsTextChanged(ai_translate_src_edit, None, ai_translate_type_combobox, ai_translate_button))
            ai_translate_count_spinbox.valueChanged.connect(lambda: on_AiTranslateCountChange(ai_translate_queue_spinbox))
            ai_translate_button.clicked.connect(lambda: ai_translate_start(ai_translate_src_edit.text(),
                                                                           ai_translate_type_combobox.currentText(),
                                                                           ai_translate_forced_checkbox.isChecked(),
                                                                           tab_widget, progress, log_edit,
                                                                           ai_translate_count_spinbox.value(),
                                                                           ai_translate_queue_spinbox.value(),exit_button))
        if title == "Компиляция":
            compile_type_group = QGroupBox("Тип файла:")
            compile_type_layout = QHBoxLayout(compile_type_group)
            compile_type_combobox = QComboBox()
            compile_type_combobox.addItems(file_types)
            compile_type_combobox.setFixedSize(100, 20)
            compile_type_layout.addWidget(compile_type_combobox, alignment=Qt.AlignmentFlag.AlignLeft)

            compile_json_group = QGroupBox("Декомпилированный словарь:")
            compile_json_layout = QHBoxLayout(compile_json_group)
            compile_json_edit = QLineEdit()
            compile_json_edit.setFixedHeight(20)
            compile_json_edit.setReadOnly(True)
            compile_json_button = QPushButton("...")
            compile_json_button.setFixedSize(20, 20)
            compile_json_layout.addWidget(compile_json_edit)
            compile_json_layout.addWidget(compile_json_button)

            compile_button = QPushButton("Начать")
            compile_button.setFixedSize(50, 20)
            compile_button.setEnabled(False)

            compile_layout = QVBoxLayout()
            compile_layout.addWidget(compile_type_group)
            compile_layout.addWidget(compile_json_group)
            compile_layout.addStretch()
            compile_layout.addWidget(compile_button, alignment=Qt.AlignmentFlag.AlignRight)

            layout.addLayout(compile_layout)
            # Обработчики
            compile_json_button.clicked.connect(lambda: select_file(compile_json_edit, "json"))
            compile_json_edit.textChanged.connect(on_CompileTextChanged)
            compile_button.clicked.connect(lambda: compile_start(compile_json_edit.text(),
                                                                 compile_type_combobox.currentText(), tab_widget))
        if title == "Настройки":
            subtab_widget = QTabWidget()
            settings_tab_layout = QVBoxLayout()
            subtabs = ["Основные", "ИИ"]
            for subtitle in subtabs:
                subtab = QWidget()
                sub_layout = QVBoxLayout(subtab)
                if subtitle == "Основные":
                    settings_path_group = QGroupBox()
                    settings_path_layout = QHBoxLayout(settings_path_group)

                    settings_datadir_group = QGroupBox("Рабочая директория:")
                    settings_datadir_layout = QHBoxLayout(settings_datadir_group)
                    settings_datadir_edit = QLineEdit()
                    settings_datadir_edit.setFixedHeight(20)
                    settings_datadir_edit.setText(config['DATA_DIR'])
                    settings_datadir_edit.setReadOnly(True)
                    settings_datadir_layout.addWidget(settings_datadir_edit)
                    settings_datadir_button = QPushButton("...")
                    settings_datadir_button.setFixedSize(20, 20)
                    settings_datadir_layout.addWidget(settings_datadir_button)

                    settings_langs_group = QGroupBox("Языки:")
                    settings_langs_layout = QVBoxLayout(settings_langs_group)
                    settings_langs_grid_layout = QGridLayout()

                    row = 0
                    col = 4
                    for i, lang in enumerate(config['ALL_LANGS']):
                        settings_langs_checkbox = QCheckBox(lang)
                        if lang == "English":
                            settings_langs_checkbox.setChecked(True)
                            settings_langs_checkbox.setEnabled(False)
                        else:
                            if lang in config['USE_LANGS']:
                                settings_langs_checkbox.setChecked(True)
                            else:
                                settings_langs_checkbox.setChecked(False)
                            # Обработчик для каждого чекбокса
                            settings_langs_checkbox.stateChanged.connect(lambda state, l=lang: on_LangChecked(state, l))

                        if i % col == 0 and i != 0: row += 1
                        settings_langs_grid_layout.addWidget(settings_langs_checkbox, row, i % col)

                    for j in range(col):
                        settings_langs_grid_layout.setColumnStretch(j, 1)
                    settings_langs_layout.addLayout(settings_langs_grid_layout)
                    settings_langs_group.setLayout(settings_langs_layout)

                    settings_build_group = QGroupBox("Билд:")
                    settings_build_layout = QHBoxLayout(settings_build_group)
                    settings_build_edit = QLineEdit()
                    settings_build_edit.setText(config['BUILD'])
                    settings_build_edit.setFixedSize(140, 20)
                    settings_build_layout.addWidget(settings_build_edit)

                    settings_path_layout.addWidget(settings_build_group, alignment=Qt.AlignmentFlag.AlignLeft)
                    settings_path_layout.addWidget(settings_datadir_group)

                    settings_layout = QVBoxLayout()
                    settings_layout.addWidget(settings_path_group)
                    settings_layout.addWidget(settings_langs_group)

                    sub_layout.addLayout(settings_layout)
                if subtitle == "ИИ":
                    ai_settings_api_group = QGroupBox()
                    ai_settings_api_layout = QHBoxLayout(ai_settings_api_group)

                    ai_settings_apiprovider_group = QGroupBox("API:")
                    ai_settings_apiprovider_layout = QHBoxLayout(ai_settings_apiprovider_group)
                    ai_settings_apiprovider_combobox = QComboBox()
                    for api_provider in config['AI']:
                        ai_settings_apiprovider_combobox.addItem(api_provider)
                    ai_settings_apiprovider_combobox.setCurrentText(config['AI_DEFAULT'])
                    ai_settings_apiprovider_combobox.setFixedHeight(20)
                    ai_settings_apiprovider_layout.addWidget(ai_settings_apiprovider_combobox)

                    ai_settings_apiurl_group = QGroupBox("URL:")
                    ai_settings_apiurl_layout = QHBoxLayout(ai_settings_apiurl_group)
                    ai_settings_apiurl_edit = QLineEdit()
                    ai_settings_apiurl_edit.setFixedHeight(20)
                    ai_settings_apiurl_layout.addWidget(ai_settings_apiurl_edit)

                    ai_settings_apikey_group = QGroupBox("KEY:")
                    ai_settings_apikey_layout = QHBoxLayout(ai_settings_apikey_group)
                    ai_settings_apikey_edit = QLineEdit()
                    ai_settings_apikey_edit.setFixedHeight(20)
                    ai_settings_apikey_layout.addWidget(ai_settings_apikey_edit)

                    ai_settings_api_layout.addWidget(ai_settings_apiprovider_group)
                    ai_settings_api_layout.addWidget(ai_settings_apiurl_group)
                    ai_settings_api_layout.addWidget(ai_settings_apikey_group)

                    ai_settings_slider_group = QGroupBox()
                    ai_settings_slider_layout = QHBoxLayout(ai_settings_slider_group)

                    ai_settings_slider_subgroup = QGroupBox()
                    ai_settings_slider_sublayout = QVBoxLayout(ai_settings_slider_subgroup)

                    ai_settings_worker_group = QGroupBox()
                    ai_settings_worker_layout = QHBoxLayout(ai_settings_worker_group)
                    ai_settings_worker_edit = QLineEdit()
                    ai_settings_worker_edit.setFixedSize(220, 20)
                    ai_settings_worker_layout.addWidget(ai_settings_worker_edit)

                    ai_settings_temperature_group = QGroupBox("Температура:")
                    ai_settings_temperature_layout = QHBoxLayout(ai_settings_temperature_group)
                    ai_settings_temperature_slider = QSlider(Qt.Orientation.Horizontal)
                    ai_settings_temperature_slider.setMinimum(0)
                    ai_settings_temperature_slider.setMaximum(20)
                    ai_settings_temperature_slider.setSingleStep(1)
                    ai_settings_temperature_slider.setFixedWidth(190)
                    ai_settings_temperature_slider_label = QLabel()
                    ai_settings_temperature_layout.addWidget(ai_settings_temperature_slider)
                    ai_settings_temperature_layout.addWidget(ai_settings_temperature_slider_label,
                                                             alignment=Qt.AlignmentFlag.AlignRight)

                    ai_settings_tune_group = QGroupBox("Системный запрос:")
                    ai_settings_tune_layout = QHBoxLayout(ai_settings_tune_group)
                    ai_settings_tune_edit = QTextEdit()
                    ai_settings_tune_edit.setAcceptRichText(False)
                    ai_settings_tune_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
                    ai_settings_tune_edit.setFixedHeight(100)
                    ai_settings_tune_layout.addWidget(ai_settings_tune_edit)

                    ai_settings_slider_sublayout.addWidget(ai_settings_worker_group)
                    ai_settings_slider_sublayout.addWidget(ai_settings_temperature_group)
                    ai_settings_slider_layout.addWidget(ai_settings_tune_group)
                    ai_settings_slider_layout.addWidget(ai_settings_slider_subgroup,
                                                        alignment=Qt.AlignmentFlag.AlignRight)

                    ai_layout_set()

                    ai_settings_layout = QVBoxLayout()
                    ai_settings_layout.addWidget(ai_settings_api_group)
                    ai_settings_layout.addWidget(ai_settings_slider_group)

                    sub_layout.addLayout(ai_settings_layout)
                subtab.setLayout(sub_layout)
                subtab_widget.addTab(subtab, subtitle)

            settings_button = QPushButton("Применить/Сохранить")
            settings_button.setFixedSize(150, 20)
            settings_button.setEnabled(False)
            settings_button.clicked.connect(save_config)

            settings_tab_layout.addWidget(subtab_widget)
            settings_tab_layout.addStretch()
            settings_tab_layout.addWidget(settings_button, alignment=Qt.AlignmentFlag.AlignRight)

            layout.addLayout(settings_tab_layout)
            # Обработчики
            settings_datadir_button.clicked.connect(lambda: select_directory(settings_datadir_edit))
            settings_datadir_edit.textChanged.connect(on_SettingsTextChanged)
            settings_build_edit.textChanged.connect(on_SettingsTextChanged)
            ai_settings_apiprovider_combobox.currentTextChanged.connect(on_SettingsApiPrivider)
            ai_settings_temperature_slider.valueChanged[int].connect(on_SettingsSlider)
            ai_settings_apiurl_edit.textChanged.connect(on_SettingsTextChanged)
            ai_settings_apikey_edit.textChanged.connect(on_SettingsTextChanged)
            ai_settings_worker_edit.textChanged.connect(on_SettingsTextChanged)
            ai_settings_tune_edit.textChanged.connect(on_SettingsTextChanged)
        if title == "?":
            howto_edit_group = QGroupBox("Как пользоваться:")
            howto_edit_layout = QHBoxLayout(howto_edit_group)
            howto_edit = TextBrowser()
            howto_edit.setReadOnly(True)
            howto_edit_layout.addWidget(howto_edit)
            howto_edit.setStyleSheet("""
                QTextBrowser {
                    border: 0px;
                    background-color: #f0f0f0;
                    outline: none;
                }
            """)
            howto_text = load_html_from_file("howto.html")
            howto_edit.setHtml(howto_text)

            howto_layout = QVBoxLayout()
            howto_layout.addWidget(howto_edit_group)

            layout.addLayout(howto_layout)
        tab.setLayout(layout)
        tab_widget.addTab(tab, title)

    window.setWindowTitle("Empyrion Localization Tool")
    window_layout.addWidget(tab_widget)

    log_group = QGroupBox("Лог:")
    log_layout = QHBoxLayout(log_group)
    log_edit = QListWidget()
    log_edit.setFont(QFont("monospace"))
    log_layout.addWidget(log_edit, alignment=Qt.AlignmentFlag.AlignBottom)
    sys.stdout = OutputRedirector(log_edit)
    window_layout.addWidget(log_group)

    main_button_group = QGroupBox()
    main_button_layout = QHBoxLayout(main_button_group)

    save_log_button = QPushButton("Сохранить лог в файл")
    save_log_button.setFixedSize(150, 20)
    save_log_button.clicked.connect(lambda: save_log(log_edit))
    main_button_layout.addWidget(save_log_button, alignment=Qt.AlignmentFlag.AlignLeft)

    main_button_layout.addWidget(progress)

    exit_button = QPushButton("Выход", window)
    exit_button.setFixedSize(60, 20)
    main_button_layout.addWidget(exit_button, alignment=Qt.AlignmentFlag.AlignRight)
    exit_button.clicked.connect(on_exitClicked)

    window_layout.addWidget(main_button_group)
    window.setCentralWidget(window_widget)

    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main_form()