"""Перевод словаря в список и обратно"""
def dict_convert(src: dict, direction: str) -> None:
    dst = []
    if direction == "ToDict":
        dst = {}
        for elem in src:
            for key in elem:
                dst[key] = {}
                dst[key] = elem[key]
    elif direction == "ToList":
        dst = []
        for key in src:
            elem = {}
            elem[key] = src[key]
            dst.append(elem)
    return dst

"""Обновление существующих ключей в dst значениями из src при условии, что English значения совпадают"""
def dict_update(src: dict, dst: dict, langs: list) -> None:
    dict_a = dict_convert(src,"ToDict")
    dict_b = dict_convert(dst, "ToDict")
    count = 0
    for key in dict_b:
        for lang in langs:
            if lang not in dict_b[key]:
                dict_b[key][lang] = ""
            if key in dict_a:
                key_updated = False
                if dict_b[key]['English'] == dict_a[key]['English']:
                    for lang in langs:
                        if lang in dict_a[key]:
                            if dict_a[key][lang] != "":
                                dict_b[key][lang] = dict_a[key][lang]
                                key_updated = True
                if key_updated: count += 1
    dict_c = dict_convert(dict_b,"ToList")
    print(f"[INFO] Ключей обновлено: {count}")
    return dict_c

"""Обновление существующих ключей в dst значениями из группы в src при условии, что English значения совпадают"""
def dict_update_group(src: dict, dst: dict, langs: list) -> None:
    dict_b = dict_convert(dst, "ToDict")
    count = 0
    for elem in src:
        for key in elem['KEYS']:
            if key in dict_b:
                key_updated = False
                if dict_b[key]['English'] == elem['English']:
                    for lang in langs:
                        if lang in elem:
                            if elem[lang] != "":
                                key_updated = True
                                dict_b[key][lang] = elem[lang]
            if key_updated: count += 1
    dict_c = dict_convert(dict_b,"ToList")
    print(f"[INFO] Ключей обновлено: {count}")
    return dict_c

"""Сравнение cur_dict с new_dict"""
def dict_compare(cur_dict: dict, new_dict: dict, langs: list) -> dict:
    dict_a = dict_convert(cur_dict,"ToDict")
    dict_b = dict_convert(new_dict, "ToDict")
    diffs = {}
    diffs['Deleted'] = []
    diffs['Added'] = []
    diffs['Changed'] = []
    for key in dict_a:
        if key in dict_b:
            if dict_a[key]['English'] != dict_b[key]['English']:
                data = {}
                data[key] = {}
                data[key]['Cur'] = dict_a[key]['English']
                data[key]['New'] = dict_b[key]['English']
                diffs['Changed'].append(data)
        else:
            data = {}
            data[key] = dict_a[key]
            diffs['Deleted'].append(data)
    print(f"[INFO] Ключей удалено: {len(diffs['Deleted'])}")
    print(f"[INFO] Ключей изменено: {len(diffs['Changed'])}")
    for key in dict_b:
        if key not in dict_a:
            data = {}
            data[key] = dict_b[key]
            diffs['Added'].append(data)
    print(f"[INFO] Ключей добавлено: {len(diffs['Added'])}")
    return diffs

"""Применение разницы diffs_dict, полученной через сравнение, к cur_dict"""
def dict_apply_diffs(cur_dict: dict, diffs_dict: dict) -> dict:
    dict_a = dict_convert(cur_dict,"ToDict")
    for elem in diffs_dict['Added']:
        for key in elem:
            dict_a[key] = {}
            dict_a[key] = elem[key]
    for elem in diffs_dict['Changed']:
        for key in elem:
            dict_a[key]['English'] = elem[key]['New']
            for lang in dict_a[key]:
                if lang != "English":
                    dict_a[key][lang] = ""
    for elem in diffs_dict['Deleted']:
        for key in elem:
            dict_a.pop(key, None)
    print(f"[INFO] Всего сделано изменений: {len(diffs_dict['Added']) + len(diffs_dict['Changed']) + len(diffs_dict['Deleted'])}")
    return dict_a