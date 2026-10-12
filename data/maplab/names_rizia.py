# -*- coding: utf-8 -*-
"""Rizia / Pales / Zille / Lespia place names (T_Map_Rizia_*, T_Map_Pales_*, zille_*, pales_*, T_Map_World_05).  Sound transliteration;
Spanish / Italian spellings follow the usual rules (qu/q -> 克/卡, -ia -> 亚, -es -> 斯)."""
NAMES = {
    # --- Rizia_01
    "Releck": "雷莱克", "RELECK": "雷莱克", "ROZANAD": "罗扎纳德", "SARKE": "萨克", "Isor": "伊索尔", "ROTSLA": "罗茨拉",
    "Yol": "约尔", "Sudiseri Maraton": "苏迪塞里马拉顿", "Dapalle": "达帕勒", "Balle": "巴勒", "Jardim": "贾尔丁",
    "Qatrol": "卡特罗尔", "Marmelasse": "马尔梅拉塞", "Malce": "马尔切", "Vhadmiz": "瓦德米兹", "Selari": "塞拉里",
    "Muai": "穆艾", "Konvans": "孔万斯", "Viseum": "维塞乌姆", "Gfalas": "格法拉斯", "MaveNortus": "梅夫诺图斯",
    "REGNEO": "雷格内奥", "Verloa Bay": "维洛亚湾", "Gulf of Moridia": "莫里迪亚湾",
    # --- Rizia_02
    "Gefisa": "格菲萨", "Pelmo": "佩尔莫", "Mafino": "马菲诺", "Cilsi": "西尔西", "Drazon": "德拉松", "DR'AZON": "德拉松",
    "Leariz": "勒阿里兹", "Escaltaro": "埃斯卡尔塔罗", "MAFIS": "马菲斯", "VALENQIRIS": "瓦伦基里斯", "Valenqiris": "瓦伦基里斯",
    "Almergis": "阿尔梅吉斯", "LakeEvon": "埃冯湖", "Lake Evon": "埃冯湖",
    # --- Rizia_03
    "Furte Clatt": "富尔特克拉特", "Mervus": "梅尔武斯", "Folce Dat": "福尔切达特", "Alacara": "阿拉卡拉", "Jesmini": "杰斯米尼",
    "Stade": "斯塔德", "PointDarte": "达尔特角", "Point Darte": "达尔特角", "Flusso": "弗卢索", "Malmino": "马尔米诺",
    "Salamant": "萨拉曼特", "Sorbenne": "索邦", "Reznera": "雷兹内拉", "Stade Alma": "斯塔德阿尔马", "Favalta": "法瓦尔塔",
    "Solcette": "索尔塞特", "jSolcette": "索尔塞特", "Furte Leon": "富尔特莱昂", "Cyasses": "西亚塞斯", "Calezf": "卡莱兹夫",
    # --- Rizia_04
    "Senievon": "贝尼翁", "Sazanas": "萨扎纳斯", "Kalqiz": "卡尔奇兹", "Kanto": "坎托", "Fulmela": "富尔梅拉",
    "Mave Matus": "梅夫诺图斯", "Zoqisas": "佐基萨斯", "Fort Assa": "阿萨堡", "Salarazelle": "萨拉拉泽尔", "Nortecale": "诺尔特卡莱",
    "Sudorid": "苏多里德", "Calerick": "卡莱里克", "Stalorid": "斯塔洛里德", "Valgeris": "瓦尔盖里斯", "Bay of Matus": "马图斯湾",
    # --- Pales_01
    "Qan": "坎", "Mamolissa": "马莫利萨", "Korlis": "科尔利斯", "Saccarda": "萨卡尔达", "Flessa": "弗莱萨", "Arasamana": "阿拉萨马纳",
    "SALAMANTIO": "萨拉曼蒂奥", "Klesa": "克莱萨", "Molle": "莫勒", "Cisa": "西萨", "Alveda": "阿尔韦达", "Desderia": "德斯德里亚",
    "Sarpis": "萨尔皮斯", "Vile Nem": "内姆城", "Amis": "阿米斯", "Qalubri": "卡卢布里", "Iqsena": "伊克塞纳", "Pesalma": "佩萨尔马",
    "Amiq": "阿米克", "Illa": "伊利亚", "Pelselam": "佩尔塞拉姆", "Resne": "雷斯内", "Dalcid": "达尔西德", "Doleris": "多莱里斯",
    # --- Pales_02
    "Magnador": "马格纳多尔", "Zorbaba": "佐尔巴巴", "Corpagi": "科尔帕吉", "Aspana": "阿斯帕纳", "Talades": "塔拉德斯",
    "Galadas": "加拉达斯", "Vile Riveres": "里韦雷斯城", "Cilcille": "西尔西勒", "Alerazze": "阿莱拉泽", "Neresus": "内雷苏斯",
    "Sollepale": "索莱帕莱", "Heriyeres": "埃里耶雷斯", "Rosidia": "罗西迪亚", "Meniq": "梅尼克", "Helves": "赫尔韦斯",
    "Reznap": "雷兹纳普", "Carpica": "卡尔皮卡", "Bubule": "布布莱", "Oas": "奥阿斯", "Baltos": "巴尔托斯", "Pasqes": "帕斯克斯",
    "Trevegus": "特雷韦古斯", "Dagdelena": "达格德莱娜", "Beoha": "贝奥哈", "Meru": "梅鲁", "Yoct": "约克特", "Drelis": "德雷利斯",
    # --- Pales_03
    "Saman": "萨曼", "Morqi": "莫尔基", "Nortepale": "北帕雷", "Meridia": "梅里迪亚", "Jamanis": "贾马尼斯", "Meimis": "梅米斯",
    "Oricopale": "奥里科帕莱", "Estepale": "东帕雷", "Palecci Moricus": "帕莱奇莫里库斯", "Dardales": "达尔达莱斯",
    # --- Pales_04
    "Cafagi": "卡法吉", "Carma": "卡尔马", "Reiqus": "雷基斯", "Ametis": "阿梅蒂斯", "Dozmus": "多兹穆斯", "Teris": "泰里斯",
    "Lorema": "洛雷马", "Vile Salman": "萨勒曼城", "Mahsenna": "马赛纳", "Ipus": "伊普斯", "Syllon": "锡隆",
    # --- Pales_05
    "Cilon": "西隆", "Oanas": "奥阿纳斯", "Sarimasa": "萨里马萨", "Salda": "萨尔达", "Refisis": "雷菲西斯", "Dama": "达马",
    "Celbilm": "塞尔比尔姆", "Mardiqiz": "马尔迪奇兹", "Porte Rikardus": "里卡杜斯港", "Nilas": "尼拉斯", "Gelqit": "盖尔基特",
    "Vile Rum": "鲁姆城", "Ugdaci": "乌格达奇",
}
