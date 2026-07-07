import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any

DB_PATH = "cga_data.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            id_questao INTEGER,
            numero_original INTEGER,
            tema TEXT,
            codigo TEXT,
            objetivo TEXT,
            resposta TEXT,
            correta TEXT,
            acertou INTEGER,
            origem TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS estado (
            chave TEXT PRIMARY KEY,
            valor TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_historico(historico: List[Dict[str, Any]]):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM historico")
    for reg in historico:
        c.execute('''
            INSERT INTO historico (
                data, id_questao, numero_original, tema, codigo, objetivo,
                resposta, correta, acertou, origem
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            reg.get('data'),
            reg.get('id'),
            reg.get('numero_original'),
            reg.get('tema'),
            reg.get('codigo'),
            reg.get('objetivo'),
            reg.get('resposta'),
            reg.get('correta'),
            1 if reg.get('acertou') else 0,
            reg.get('origem')
        ))
    conn.commit()
    conn.close()

def load_historico() -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT data, id_questao, numero_original, tema, codigo, objetivo,
               resposta, correta, acertou, origem
        FROM historico
        ORDER BY id ASC
    ''')
    rows = c.fetchall()
    conn.close()
    historico = []
    for row in rows:
        historico.append({
            'data': row[0],
            'id': row[1],
            'numero_original': row[2],
            'tema': row[3],
            'codigo': row[4],
            'objetivo': row[5],
            'resposta': row[6],
            'correta': row[7],
            'acertou': bool(row[8]),
            'origem': row[9]
        })
    return historico

def save_estado(estado: Dict[str, Any]):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Chaves a persistir (incluindo leitner)
    chaves_persistir = [
        'modo', 'filtro_tema_atual', 'filtro_objetivo_atual',
        'questao_atual', 'respondido', 'resposta_usuario',
        'simulado_questoes', 'simulado_respostas', 'simulado_i',
        'simulado_ativo', 'simulado_finalizado', 'simulado_registrado',
        'inicio_simulado', 'duracao_simulado_min',
        'revisao_lista', 'revisao_i', 'revisao_concluida',
        'confirmar_finalizar',
        'leitner_niveis',      # NOVO
        'leitner_proxima'      # NOVO
    ]
    estado_filtrado = {k: estado.get(k) for k in chaves_persistir if k in estado}
    # Salvar erros como ids
    estado_filtrado['erros_ids'] = [e['id'] for e in estado.get('erros', [])]
    estado_filtrado['acertos_ids'] = estado.get('acertos', [])
    json_str = json.dumps(estado_filtrado, default=str)
    c.execute("REPLACE INTO estado (chave, valor) VALUES (?, ?)", ('state', json_str))
    conn.commit()
    conn.close()

def load_estado() -> Dict[str, Any]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT valor FROM estado WHERE chave = ?", ('state',))
    row = c.fetchone()
    conn.close()
    if row is None:
        return {}
    try:
        return json.loads(row[0])
    except:
        return {}

def load_erros(questoes: List[Dict]) -> List[Dict]:
    estado = load_estado()
    erros_ids = estado.get('erros_ids', [])
    mapa = {q['id']: q for q in questoes}
    erros = [mapa[eid] for eid in erros_ids if eid in mapa]
    return erros
