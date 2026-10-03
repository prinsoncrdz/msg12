import re

lines = [
    'EL90256KNPTA105JD-STOCK 1 THREADOLET 1/2" X 3", 6000#, A350 GR. LF2 CL1',
    'BL25150RFA105/A350LF2ST&H-STOCK 10000 1.00 pcs FLANGE 2", 150#, BLIND RF',
    '3/4", SPECTACLE BLIND, 300LB, RF, ASTM A350 Gr.LF2 - Machined from S.40',
    'UNION 1", 6000# Offered 1/2" NPT',
    'ELBOW 2", 3000# Modified from 3000# to 6000#',
    'Made from plate'
]

REMARK_PATTERN = re.compile(r'\b(machined(?:\s+from)?|modified(?:\s+from)?|offered|made\s+from|fabricated(?:\s+from)?|locally)\b.*', re.IGNORECASE)

for l in lines:
    has_stock = bool(re.search(r'[-_\s/]?STOCK\b', l, re.IGNORECASE))
    m = REMARK_PATTERN.search(l)
    remark = m.group(0).strip() if m else ''
    clean_desc = REMARK_PATTERN.sub('', l).strip() if m else l
    print(f'Line: {l}')
    print(f' -> STOCK: {has_stock} | Remark: "{remark}" | Clean: "{clean_desc}"')
    print('-'*50)
