# -*- coding: utf-8 -*-
"""Sordland / Valgsland / Wehlen place names (maps T_Map_Sordland_*, T_Map_World_02/03, the Sordland part of T_Map_RumburgWar_*).
English -> Chinese.  Names that already have a rendering in the translated text are in names_established.py or come from the
entity text (map_names.ENTITY) and are not repeated here.  Everything below is a sound transliteration (Xinhua name tables)."""
NAMES = {
    # --- Sordland_01
    "Midsbourgh": "米兹堡", "Dessax": "德萨克斯", "Willems": "威廉姆斯", "Rueston": "鲁斯顿", "Younghaven": "扬黑文",
    "Tzarsbourgh": "察尔斯堡", "Cafeth": "卡费斯", "Aethelrad": "埃瑟尔拉德", "Killblair": "基尔布莱尔", "Alferdon": "阿尔弗登",
    "Rachaster": "拉彻斯特", "Mougwer": "莫格韦尔", "Crimsrad": "克里姆斯拉德", "Merdon": "梅尔登", "Halgen": "哈尔根",
    "Ralm": "拉尔姆", "Rivol": "里沃尔", "Vale": "维尔", "Soulery": "苏勒里", "Arno": "阿尔诺", "Vasqel": "瓦斯凯尔",
    "Sunor": "苏诺尔", "Tarantim": "塔兰蒂姆", "Holbel": "霍尔贝尔", "Rizen": "里曾", "Terely": "泰雷利", "Lards": "拉兹",
    "Letamer": "莱塔默", "Rengerin": "伦格林", "Burda": "布尔达", "Manoly": "马诺利", "Faimer": "费默", "Jeloren": "耶洛伦",
    "Iliat": "伊利亚特", "Benisord": "贝尼索德", "Benisorc": "贝尼索德", "Moular": "穆拉尔", "Lem": "莱姆",
    "Lotherg": "洛森博格", "Lotherberg": "洛森博格",
    "TRANQUIL SEA": "宁静海", "TRANQUILSEA": "宁静海", "Gulf of Nargis": "纳尔吉斯湾", "Lenkurg Bay": "伦库尔湾", "RUMBURG": "伦堡",
    "REPUBLIK DEI SORDLAND": "索德兰共和国",
    # --- Sordland_02
    "Merritown": "梅里敦", "Marassen": "马拉森", "Lude": "卢德", "Redjurk": "雷德尤尔克", "Hoolten": "霍尔滕",
    "Torreic": "托雷克", "Gelbja": "格尔比亚", "Gelbja Island": "格尔比亚岛", "Biberuc": "比贝鲁克", "Margni": "马格尼",
    "Tolrin": "托尔林", "Verhol": "维尔霍尔", "Nermen": "内尔门", "Temeriot": "特梅里奥特", "Aben": "阿本",
    "Felksort": "费尔克斯洛特", "Maale": "马勒", "Duru Island": "杜鲁岛",
    # --- Sordland_03
    "Locet": "洛塞特", "Kusumer": "库苏默", "Mavalaven": "马瓦拉文", "Mayalaven": "马瓦拉文", "Vissimar": "维西马尔",
    "Gelre": "盖尔雷", "Tos": "托斯", "Bert": "贝特", "Perzi": "佩尔齐", "Talen": "塔伦", "Zymna": "济姆纳", "Narel": "纳雷尔",
    "Arnut": "阿尔努特", "Marisat": "马里萨特", "Passae": "帕萨埃", "Passa": "帕萨", "Vernica": "韦尔尼察", "Etnissa": "埃特尼萨",
    "Loca Benolia": "洛卡贝诺利亚", "Benolia": "贝诺利亚", "Galt": "加尔特", "Zicek": "齐切克", "Conia": "科尼亚",
    "Derten": "德滕", "Mord": "莫德", "Wizen": "维岑", "Yena": "耶纳", "Kilsaren": "基尔萨伦", "Kastza": "卡斯扎",
    "Lova Verna": "洛瓦韦尔纳", "Igirera": "伊吉雷拉", "Czerna": "切尔纳", "Luco": "卢科", "Lake Luco": "卢科湖",
    "Sant Cezra": "圣切兹拉", "Mizen": "米岑", "Witsima": "维齐马", "Marlino": "马里诺", "Welsk": "韦尔斯克",
    "Veno Rebia": "维诺雷比亚", "Kratsna": "克拉茨纳", "Warno": "瓦尔诺", "Lerlow": "勒洛", "Artsnan": "阿尔茨南",
    "San Mantua": "圣曼图亚", "San Montua": "圣曼图亚", "San Momtua": "圣曼图亚", "Smol": "斯莫尔", "Gjalm": "加尔姆",
    # --- Sordland_04
    "Bronia": "布罗尼亚", "Rock of Maradune": "马拉杜内岩", "RockofMaradune": "马拉杜内岩", "Morrain": "莫雷恩", "Selvin": "塞尔温",
    "Anri": "安里", "Olben": "奥尔本", "Stagert": "斯塔格特", "Wemna": "韦姆纳", "Silcen": "西尔岑", "Bendam": "本达姆",
    "Morger": "莫尔格", "Tactern": "塔克特恩", "Ordibel": "奥迪贝尔", "Allten": "阿尔滕", "Selmec": "塞尔梅克",
    "Porzar": "波尔扎", "Varhem": "瓦尔赫姆", "Norin": "诺林", "Fresin": "弗雷辛", "Alwoll": "阿尔沃尔", "Ecliat": "埃克利亚特",
    "Loulatt": "卢拉特", "Leliac": "勒利亚克", "Menswol": "门斯沃尔", "Kibenord": "基贝诺德", "Vesial": "韦西亚尔",
    "Girder": "吉尔德", "Beriat": "贝里亚特", "Annim": "安尼姆", "Boinar": "博伊纳尔", "Ismic": "伊斯米克", "Leviso": "莱维索",
    "Canari": "卡纳里", "Gios Bay": "吉奥斯湾",
}
