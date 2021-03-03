
def translate(s):
    return s.translate(str.maketrans("ğĞıİöÖüÜşŞçÇ", "gGiIoOuUsScC")).lower()


def clean_title(t):
    t = translate(t)
    title_list = t.split()
    for i in range(len(title_list)):
        if "-" in title_list[i]:
            if title_list[i].replace("-", "").isdigit():
                title_list[i] = title_list[i]
            else:
                title_list[i] = title_list[i].replace("-", " ")
    t = " ".join([str(elem) for elem in title_list])
    t = t.replace(".", "")
    t = t.replace(",", "")
    t = t.replace("(", " ")
    t = t.replace(")", " ")
    t = t.replace("[", " ")
    t = t.replace("]", " ")
    t = t.replace("+", "")
    return t


def parameters(data, params):
    return [
        i
        for i in data
        if params.decode("utf-8") in translate(i.get("link"))
        or params.decode("utf-8").replace("-", " ")
        in clean_title(i.get("title"))
        or i.get("epey_color") == params.decode("utf-8")
    ]


def no_parameters(data, params):
    return [
        i
        for i in data
        if params not in translate(i.get("link"))
        and params.replace("-", " ") not in clean_title(i.get("title"))
        and i.get("variant_color") != params
        and i.get("epey_color") != params
    ]
