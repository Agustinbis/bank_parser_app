# bank_profiles.py

BANK_PROFILES = {
    "MACRO": {
        "layout": {
            "date_x":    (0,   70),
            "desc_x":    (70,  215),   # descripción hasta justo antes de referencias
            "ref_x":     (215, 280),   # calibrado con DEBUG-XY
            "debit_x":   (275, 410),   # rango real de débitos
            "credit_x":  (410, 491),   # rango real de créditos
            "balance_x": (491, 625)    # rango real de saldos
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
    },

    "MUNICIPALROS": {
        "layout": {

            "date_x":    (10, 70),       # Fecha: x0 ≈ 20.1
            "ref_x":     (70, 100),      # Cantidad o código: x0 ≈ 86.1
            "desc_x":    (100, 400),     # Descripción: x0 ≈ 122.8 a 224.4
            "debit_x":   (410, 455),     # Débito: x0 ≈ 440.2
            "credit_x":  (455, 525),     # Crédito: x0 ≈ 525.0 (ajustable)
            "balance_x": (525, 600)      # Saldo: x0 ≈ 545.8
        },
        "flags": {
            "es_layout_invertido": True,
            "usa_referencia": False,
            "omite_totales": False,
            "saldo_arranca_en_fila_1": True
        },
        "excluir_si_contiene": [
            "TOTAL DE OPERACIONES", "SALDO DISPONIBLE"
        ],
        "buscar_desde_pagina": 1
    },

    "MACROctacte": {
        "layout": {
            "date_x":    (0,   70),
            "desc_x":    (70,  215),   # descripción hasta justo antes de referencias
            "ref_x":     (215, 270),   # calibrado con DEBUG-XY
            "debit_x":   (270, 380),   # rango real de débitos
            "credit_x":  (380, 490),   # rango real de créditos
            "balance_x": (490, 625)    # rango real de saldos
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

    "FRANCES": {
        "layout": {
            # Coordenadas aproximadas para el fallback por coordenadas X.
            # Ajustar con DEBUG-XY si el regex no cubre todos los casos.
            "date_x":    (0,   65),     # Fecha: DD/MM o DD/MM/AA
            "desc_x":    (65,  310),    # Descripción
            "debit_x":   (310, 420),    # Débito
            "credit_x":  (420, 510),    # Crédito
            "balance_x": (510, 650)     # Saldo
        },
        "flags": {
            "es_layout_invertido": True,  
            "usa_referencia": False,
            "omite_totales": False,
            "saldo_arranca_en_fila_1": True
        },
        "excluir_si_contiene": [
            "SALDO ANTERIOR", "SALDO FINAL", "TOTAL MOVIMIENTOS",
            "SALDO DISPONIBLE", "TOTAL DE OPERACIONES"
        ],
        "buscar_desde_pagina": 0
    },

# Notas Credicoop:
#   - El saldo solo aparece en la última línea de cada grupo diario
#   - es_layout_invertido = False: Crédito suma, Débito resta (lógica estándar)
#   - Una sola cuenta por PDF

    "CREDICOOP": {
        "layout": {
            # Referencia aproximada (el parser usa texto plano, no coordenadas)
            "date_x":    (0,   60),
            "desc_x":    (60,  320),
            "debit_x":   (320, 430),
            "credit_x":  (430, 530),
            "balance_x": (530, 650)
        },
        "flags": {
            "es_layout_invertido": True,
            "usa_referencia": False,
            "omite_totales": True,
            "saldo_arranca_en_fila_1": True
        },
        "excluir_si_contiene": [
            "IMPUESTO LEY 25413",
            "TOTAL IMPUESTO",
            "PERCIBIDO DEL",
            "CRE FISC",
            "IVA-ALIC",
            "IVA − ALICUOTA",
            "DEBITOS AUTOMATICOS",
            "EMPRESA",
            "CONTINUA EN PAGINA",
            "VIENE DE PAGINA"
        ],
        "buscar_desde_pagina": 0
    },
# Coordenadas X calibradas con PDF real del Santander (ancho=595)
#   Débito:  $ en x0≈358-384, importe en x0≈365-391
#   Crédito: $ en x0≈434-442, importe en x0≈441-449
#   Saldo:   $ en x0≈520-528, importe en x0≈527-535

    "SANTANDER": {
        "layout": {
            "date_x":    (0,   65),     # Fecha DD/MM/YY  (x0≈23)
            "desc_x":    (65,  355),    # Descripción     (x0≈65 comprobante, x0≈115 texto)
            "debit_x":   (355, 430),    # Débito          (x0≈365-391)
            "credit_x":  (430, 518),    # Crédito         (x0≈441-449)
            "balance_x": (518, 595)     # Saldo           (x0≈527-535)
        },
        "flags": {
            "es_layout_invertido": True,
            "usa_referencia": False,
            "omite_totales": True,
            "saldo_arranca_en_fila_1": True
        },
        "excluir_si_contiene": [
            "DETALLE IMPOSITIVO",
            "TOTAL RETENCION",
            "IMPORTE SUSCEPTIBLE",
            "TOTAL RETENCION REGIMEN",
            "TASAS DE ACUERDOS",
            "CAMBIO DE COMISIONES",
            "MOVIMIENTOS EN PESOS",
            "CUENTA CORRIENTE N"
        ],
        "buscar_desde_pagina": 1
    },
    
"NACION": {
        "layout": {
            # Coordenadas calibradas con PDF real (ancho=595.2pt)
            # Fecha "01/10/25" → x0=65.10   → rango empieza en 55
            # Descripción      → x0=108–210 → hasta antes del comprobante
            # Comprobante      → x0=237–266 → columna COMPROB.
            # Débitos          → x0=309–353 → columna DEBITOS (right-aligned, fin ≈405)
            # Créditos         → x0=405–420 → columna CREDITOS (right-aligned, fin ≈497)
            # Saldo            → x0=497–502 → columna SALDO
            "date_x":    (55,  105),     # Fecha DD/MM/YY
            "desc_x":    (105, 230),     # Movimientos / descripción
            "ref_x":     (230, 280),     # Comprobante
            "debit_x":   (280, 400),     # Débitos
            "credit_x":  (400, 497),     # Créditos
            "balance_x": (497, 600)      # Saldo
        },
        "flags": {
            "es_layout_invertido": True,   # saldo = prev + crédito - débito
            "usa_referencia": True,
            "omite_totales": True,
            "saldo_arranca_en_fila_1": True
        },
        "excluir_si_contiene": [
            "TOTAL GRAV",
            "TOTAL REG",
            "USTED PUEDE",
            "ESTIMAREMOS",
            "SIN PERJUICIO",
            "POR RAZONES",
            "HTTP",
            "DEPOSITOS DE TERCEROS",
            "COMPROBANTE",        # encabezado de la tabla de depósitos de terceros
            "FIN DE RESUMEN"
        ],
        "buscar_desde_pagina": 0
    },

    "COINAG": {
        "layout": {
            # Coordenadas calibradas con PDF real (ancho=595pt)
            # Fecha D/M/YYYY      → x0=68    → rango (48, 100)
            # Concepto            → x0=102   → rango (100, 290)  [incluye Comprob.]
            # Por Acreditar       → x0=352   → rango (290, 412)
            # Débito              → x0=427   → rango (412, 479)
            # Crédito             → x0=490   → rango (479, 530)
            # Saldo               → x0=534   → rango (530, 595)
            "date_x":         (48,  100),
            "desc_x":         (100, 290),
            "por_acreditar_x":(290, 412),
            "debit_x":        (412, 479),
            "credit_x":       (479, 530),
            "balance_x":      (530, 595),
        },
        "flags": {
            "es_layout_invertido":   True,   # saldo = anterior + crédito − débito
            "usa_referencia":        False,  # comprobante incluido en descripción
            "omite_totales":         True,
            "saldo_arranca_en_fila_1": True, # primera fila es base del saldo
        },
        "excluir_si_contiene": [
            "Transporte", "Fecha Concepto", "Detalle de Tributos",
            "Base Imponible", "Total:",
        ],
        "buscar_desde_pagina": 0,
    },

    "SANTAFE": {
        "layout": {
            # Coordenadas calibradas con PDF real (ancho=595pt)
            # Fecha D/MM/YYYY      → x0=42-46    → rango (38, 93)
            # Origen "CASA SA"     → x0=96-117   → rango (93, 130)
            # Concepto + ref       → x0=130-285  → rango (130, 315)
            # Débitos              → x0=331-353  → rango (315, 410)
            # Créditos             → x0=415-424  → rango (410, 492)
            # Saldo                → x0=495-512  → rango (492, 560)
            "date_x":    (38,  93),
            "origen_x":  (93,  130),
            "concepto_x":(130, 315),
            "debit_x":   (315, 410),
            "credit_x":  (410, 492),
            "balance_x": (492, 560),
        },
        "flags": {
            "es_layout_invertido": True,   # saldo = anterior + credito - debito
            "usa_referencia": False,       # ref va incluida en el concepto
            "omite_totales":  True,        # saltar líneas "Ley 25.413"
            "multi_periodo":  True,        # un PDF puede tener varios meses
            "saldo_negativo_sufijo": True, # negativos indicados con '-' al final
        },
        "excluir_si_contiene": [
            "Ley 25.413", "Ultimas chequeras", "Movimientos Detallado",
            "Consolidado de Cuentas", "Saldo Anterior Saldo Actual",
        ],
        "buscar_desde_pagina": 0,
    },
}