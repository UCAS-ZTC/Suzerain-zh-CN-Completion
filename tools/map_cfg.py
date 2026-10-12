"""Map textures that carry English place names (pristine game).  Shared by map_* scripts."""

BIG = (
    [f"T_Map_World_0{i}" for i in range(1, 7)]
    + [f"T_Map_Sordland_0{i}" for i in range(1, 5)]
    + [f"T_Map_Rizia_0{i}" for i in range(1, 5)]
    + [f"T_Map_RumburgWar_0{i}" for i in range(1, 3)]
    + [f"T_Map_Pales_0{i}" for i in range(1, 7)]
)
OVERLAY = ["pales_big", "pales_divided", "pales_rizia", "zille_brenas", "zille_ownstate",
           "Heljiland_Agnolia", "Heljiland_Default", "Heljiland_Invaded", "Heljiland_Valgsland"]
LABELS = ["world_fortales_text", "world_pales_Text", "world_heljiland_agnolia", "world_heljiland_valgsland",
          "world_pales_rizia", "world_pales_big", "world_pales_split"]
CODEX = ["c_agnlandregion", "c_bergiaregion", "c_brenasregion", "c_cardessemontaklarregion", "c_gelslandregion",
         "c_greaterholsordregion", "c_gruniregion", "c_lorrenregion", "c_nargisregion", "c_pales",
         "c_palesadmindistrictregion", "c_palescity", "c_riziaimperiiregion", "c_valenqirisregion", "c_zille"]
ALL = BIG + OVERLAY + LABELS + CODEX
