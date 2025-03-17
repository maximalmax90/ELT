import csv
import json
import yaml
import os

def load_json(file_path: str) -> dict:
    content = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = json.load(file)
    except json.JSONDecodeError as e:
        print(f"[FAIL] Ошибка при чтении файла {file_path}: {e}")
    finally:
        return content

def load_ecf(file_path: str) -> dict:
    skip_var = ["/*","Execute","Variable","If","Functions","#"]
    text_var = ["NPCName","Output","Option_"]
    dial_var = ["Next_"]
    data = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as file: lines = file.readlines()
        dialog = ""
        for line in lines:
            if '{ +' in line:
                value = line.split("Dialogue Name:")
                dialog = value[1].strip()
                data[dialog] = {}
                data[dialog]['text'] = []
                data[dialog]['chain'] = []
            elif '}' in line and len(line.strip()) == 1: continue
            elif any(word in line for word in skip_var):
                check = line.split(":")
                if any(word in check[0].strip() for word in skip_var): continue
                else:
                     if dialog != "":
                         values = line.strip().split(":")
                         if len(values) > 2:
                             if "param1" in values[1].strip():
                                 value = values[1].strip().split(",")
                                 if any(word in values[0] for word in text_var): data[dialog]['text'].append(value[0].strip())
                                 elif any(word in values[0] for word in dial_var): data[dialog]['chain'].append(value[0].strip())
                             else:
                                 #print(f"ERROR: {values}")
                                 #break
                                 continue
                         elif values[1].strip() == "End": continue
                         elif any(word in values[0] for word in text_var): data[dialog]['text'].append(values[1].strip())
                         elif any(word in values[0] for word in dial_var): data[dialog]['chain'].append(values[1].strip())
            else:
                if dialog != "":
                     values = line.strip().split(":")
                     if len(values) > 2:
                         if "param1" in values[1].strip():
                             value = values[1].strip().split(",")
                             if any(word in values[0] for word in text_var): data[dialog]['text'].append(value[0].strip())
                             elif any(word in values[0] for word in dial_var): data[dialog]['chain'].append(value[0].strip())
                         else:
                             continue
                     elif values[1].strip() == "End": continue
                     elif any(word in values[0] for word in text_var): data[dialog]['text'].append(values[1].strip())
                     elif any(word in values[0] for word in dial_var): data[dialog]['chain'].append(values[1].strip())
    except Exception as e:
        print(f"[FAIL] Ошибка при чтении файла {file_path}: {e}")
    finally:
        return data

def load_csv(file_path: str) -> tuple:
    content = None
    headers = None
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = []
            reader = csv.reader(file)
            headers = next(reader)
            for row in reader:
                content.append(row)
    except Exception as e:
        print(f"[FAIL] Ошибка при чтении файла {file_path}: {e}")
    return headers, content

def save_json(file_path: str, content: list) -> bool:
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(content, file, indent=4, ensure_ascii=False,)
            return True
    except Exception as e:
        print(f"[FAIL] Ошибка при записи файла {file_path}: {e}")
        return False

def save_csv(file_path: str, content: list) -> bool:
    try:
        with open(file_path, 'w', encoding='utf-8', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(content)
            return True
    except Exception as e:
        print(f"[FAIL] Ошибка при записи файла {file_path}: {e}")
        return False

def ecf_to_json(data: dict) -> list:
    processed_dict = {
        k: {"text": list(v["text"]), "chain": list(v["chain"])}
        for k, v in data.items()
    }
    result = []
    processed_nodes = set()
    def recursive_process(node_name):
        if node_name in processed_nodes: return
        if node_name not in processed_dict: return
        processed_nodes.add(node_name)
        current_node = processed_dict[node_name]
        dependencies = current_node["chain"]
        collected_texts = set(current_node["text"])
        for dep in dependencies:
            if dep in processed_dict and dep not in processed_nodes:
                recursive_process(dep)
                collected_texts.update(processed_dict[dep]["text"])
        current_node["text"] = list(collected_texts)
        current_node["chain"] = []
    for node_name in processed_dict: recursive_process(node_name)
    for key in processed_dict: result.append(processed_dict[key]['text'])
    return result

def csv_to_json(dataset: tuple, languages: list, clean: bool) -> list:
    data = []
    reader = dataset[1]
    headers = dataset[0]
    for row in reader:
        key_id = row[0]
        language_values = {}
        for lang in languages:
            idx = headers.index(lang)
            """Очередной костыль"""
            if idx > len(row)-1 or (lang != "English" and clean):
                language_values[lang] = ""
            else:
                language_values[lang] = row[idx]
        data.append({key_id: language_values})
    return data

def yaml_to_json(file_path) -> list:
    data = []
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)
    except Exception as e:
        print(f"[FAIL] Ошибка при чтении файла {file_path}: {e}")
    return data

def pda_chain_to_json(data: dict) -> list:
    content = []
    try:
        for chapter in data['Chapters']:
            chapter_array = []
            if "ChapterTitle" in chapter: chapter_array.append(chapter['ChapterTitle'])
            if "StartMessage" in chapter:
                messages = chapter['StartMessage'].split("|")
                for message in messages:
                    if ";" not in message and len(message) > 0: chapter_array.append(message)
            if "SkipMessage" in chapter: chapter_array.append(chapter['SkipMessage'])
            if "Description" in chapter: chapter_array.append(chapter['Description'])
            if "Group" in chapter: chapter_array.append(chapter['Group'])
            if "ActivateChapterOnCompletion" in chapter: chapter_array.append(chapter['ActivateChapterOnCompletion'])
            if "CompletedMessage" in chapter:
                messages = chapter['CompletedMessage'].split("|")
                for message in messages:
                    if ";" not in message and len(message) > 0: chapter_array.append(message)
            if "RewardedChapters" in chapter:
                for key in chapter["RewardedChapters"]: chapter_array.append(key)
            if "Tasks" in chapter:
                for task in chapter['Tasks']:
                    if "TaskTitle" in task: chapter_array.append(task['TaskTitle'])
                    if "StartMessage" in task:
                        messages = task['StartMessage'].split("|")
                        for message in messages:
                            if ";" not in message and len(message) > 0: chapter_array.append(message)
                    if "Actions" in task:
                        for action in task['Actions']:
                            if "ActionTitle" in action: chapter_array.append(action['ActionTitle'])
                            if "Description" in action: chapter_array.append(action['Description'])
                            if "CompletedMessage" in action:
                                messages = action['CompletedMessage'].split("|")
                                for message in messages:
                                    if ";" not in message and len(message) > 0: chapter_array.append(message)
            content.append(chapter_array)
    except Exception as e:
        print(f"[FAIL] Ошибка обработки цепочки: {e}")
    return content

def json_to_csv(data: dict, languages: list) -> list:
    headers = ['KEY'] + languages
    content = [headers]
    for item in data:
        key_id = next(iter(item))
        row = [key_id]
        for lang in languages:
            if lang in item[key_id]:
                row.append(item[key_id][lang])
            else:
                row.append('')
        content.append(row)

    return content

""" При соблюдении структуры таблицы, не пришлось бы заниматься подобным """
def csv_checker(dataset: tuple) -> list:
    content = []
    keys = []
    reader = dataset[1]
    headers = dataset[0]
    for index, row in enumerate(reader):
        if len(row) != len(headers):
            """И это тоже костыль, если в строке 2 элемента, то забиваем, 
            скорее всего там только ключ и english значение, а если нет - помянем, точнее руками правим"""
            if len(row) != 2 or row[0] == "":
                text = row[0] if row[0] != "" else ","
                content.append(f"({text}): элементов {len(row)}/{len(headers)}")
            else: keys.append(row[0])
        else: keys.append(row[0])
    duplicates = [i for i in set(keys) if keys.count(i) > 1]
    return [len(keys), duplicates, content]

def group_keys(data: dict, langs: list) -> list:
    main_dict = {}
    group_key = {}
    group_list = []
    for elem in data:
        for key in elem:
            main_dict[key] = {}
            main_dict[key]['English'] = elem[key]['English']
            if elem[key]['English'] in group_key:
                group_key[elem[key]['English']].append(key)
            else:
                group_key[elem[key]['English']] = [key]
    for val in group_key:
        elem = {'KEYS': group_key[val]}
        for lang in langs:
            elem[lang] = ""
        elem['English'] = val
        group_list.append(elem)
    return group_list

def conversion(csv_path: str, spec_path: str, build_dir: str, file_type: str, langs: list, clean: bool, group: bool):
    langs.insert(0,"English")
    dataset = load_csv(f"{csv_path}")
    if not None in dataset:
        data_check = csv_checker(dataset)
        if len(data_check[1]) > 0 or len(data_check[2]) > 0:
            print(f"[ OK ] Анализ и обработка структуры CSV-файла")
            if len(data_check[2]) > 0: print(f"[FAIL] {csv_path}, следующие строки ({len(data_check[2])}) содержат ошибки: {data_check[2]}")
            if len(data_check[1]) > 0: print(f"[FAIL] {csv_path}, дублирующиеся ключи ({len(data_check[1])}): {data_check[1]}")
        elif data_check[0] == 0: pass
        else:
            data = csv_to_json(dataset,langs,clean)
            if data is not None:
                print(f"[ OK ] Перевод CSV в JSON")
                if(save_json(f"{os.path.join(build_dir,file_type)}_decompiled.json",data)):
                    print(f"[ OK ] {os.path.join(build_dir,file_type)}_decompiled.json сохранен, количество ключей: {len(data)}")
                if group:
                    group_data = group_keys(data,langs)
                    if len(group_data)>0:
                        print(f"[ OK ] Формирование группы")
                        if (save_json(f"{os.path.join(build_dir, file_type)}_group.json", group_data)):
                            print(f"[ OK ] {os.path.join(build_dir, file_type)}_group.json сохранен, количество групп: {len(group_data)}")
    langs.remove("English")
    if file_type == "PDA" and spec_path != "":
        data = yaml_to_json(f"{spec_path}")
        if len(data) > 0:
            print(f"[ OK ] Парсинг YAML")
            chain_list = pda_chain_to_json(data)
            if len(chain_list) > 0:
                print(f"[ OK ] Формирование цепочек")
                chains = [x for x in chain_list if x != []]
                if(save_json(f"{os.path.join(build_dir,file_type)}_chains.json",chains)):
                    print(f"[ OK ] {os.path.join(build_dir,file_type)}_chains.json сохранен, количество цепочек: {len(chains)}")
        else:
            print(f"[INFO] Цепочки не обнаружены")
    if file_type == "Dialogues" and spec_path != "":
        data = load_ecf(f"{spec_path}")
        if len(data) > 0:
            print(f"[ OK ] Парсинг EFC")
            chain_list = ecf_to_json(data)
            print(f"[ OK ] Формирование цепочек")
            chains = [x for x in chain_list if x != []]
            print(f"[ OK ] Удаление пустых цепочек")
            if(save_json(f"{os.path.join(build_dir,file_type)}_chains.json",chains)):
                print(f"[ OK ] {os.path.join(build_dir,file_type)}_chains.json сохранен, количество цепочек: {len(chains)}")
        else:
            print(f"[INFO] Цепочки не обнаружены")