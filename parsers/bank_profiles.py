# bank_profiles.py

BANK_PROFILES = {
    "MACRO": {
        "layout": {
            "date_x":    (0,   70),
            "desc_x":    (70,  215),   # descripción hasta justo antes de referencias
            "ref_x":     (215, 280),   # calibrado con DEBUG-XY
            "debit_x":   (275, 410),   # rango real de débitos
            "credit_x":  (410, 495),   # rango real de créditos
            "balance_x": (495, 625)    # rango real de saldos
        },
        "flags": {
            "es_layout_invertido": True,
            "usa_referencia": True,
            "omite_totales": True,
            "saldo_arranca_en_fila_1": True
        },
        "excluir_si_contiene": [
            "SALDO FINAL", "TOTAL COBRADO", "SALDO ULTIMO"
        ],
        "buscar_desde_pagina": 0
    },

    "GALICIA": {
        "layout": {
            "date_x":    (0, 60),
            "desc_x":    (60, 280),
            "ref_x":     (280, 360),
            "debit_x":   (360, 440),
            "credit_x":  (440, 520),
            "balance_x": (520, 680)
        },
        "flags": {
            "es_layout_invertido": False,
            "usa_referencia": False,
            "omite_totales": False,
            "saldo_arranca_en_fila_1": True
        },
        "excluir_si_contiene": [
            "TOTAL DE OPERACIONES", "SALDO DISPONIBLE"
        ],
        "buscar_desde_pagina": 1
    }
}